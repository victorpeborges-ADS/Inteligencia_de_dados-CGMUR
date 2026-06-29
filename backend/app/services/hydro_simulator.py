"""Simulação pluvial enriquecida com DEM SRTM: manchas por profundidade, curvas de nível e escoamento."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from sqlalchemy.orm import Session

from app.models import Bairro, CoberturaVegetalMapBiomas, Municipio
from app.services.dem_processor import (
    SLOPE_CRITICAL_DEG,
    _compute_slope_degrees,
    _flow_paths_geojson,
    _synthetic_dem,
    dem_dir,
    is_processed,
    load_meta,
    process_municipality_dem,
)

logger = logging.getLogger(__name__)

DEPTH_BANDS = (
    ("superficial", 0.05, 0.35, "Alagamento superficial (< 35 cm)"),
    ("moderada", 0.35, 0.80, "Alagamento moderado (35–80 cm)"),
    ("critica", 0.80, 999.0, "Alagamento crítico (> 80 cm)"),
)

FLOOD_COLORS = {
    "superficial": "#38bdf8",
    "moderada": "#0284c7",
    "critica": "#1e3a8a",
}


def _load_elevation_grid(
    db: Session,
    codigo_ibge: str,
    muni: Municipio,
) -> tuple[np.ndarray, float, float, float, float, dict[str, Any]] | None:
    tif = dem_dir(codigo_ibge) / "dem.tif"
    meta = load_meta(codigo_ibge)

    if not tif.exists():
        try:
            if not is_processed(codigo_ibge):
                process_municipality_dem(db, codigo_ibge)
            meta = load_meta(codigo_ibge) or {}
        except Exception as exc:
            logger.warning("DEM indisponível para %s: %s", codigo_ibge, exc)

    if tif.exists():
        try:
            import rasterio

            with rasterio.open(tif) as src:
                elev = src.read(1).astype(np.float64)
                west, south, east, north = src.bounds
                res_x = (east - west) / src.width
                res_y = (north - south) / src.height
                return elev, west, south, res_x, res_y, meta or {}
        except Exception as exc:
            logger.warning("Falha ao ler DEM %s: %s", tif, exc)

    try:
        geo = json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))
        west, south, east, north = shape(geo).bounds
        pad = max((east - west), (north - south)) * 0.05
        elev, res_x, res_y, west, south = _synthetic_dem(
            south - pad, north + pad, west - pad, east + pad,
        )
        rows, cols = elev.shape
        meta = {"dem_source": "synthetic (fallback)", "stats": {}}
        return elev, west, south, res_x, res_y, meta
    except Exception as exc:
        logger.warning("Fallback sintético falhou: %s", exc)
        return None


def _muni_raster_mask(
    elevation: np.ndarray,
    muni_geom,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
) -> np.ndarray:
    import rasterio.features
    from rasterio.transform import from_bounds

    rows, cols = elevation.shape
    north = south + rows * res_y
    east = west + cols * res_x
    transform = from_bounds(west, south, east, north, cols, rows)
    return rasterio.features.geometry_mask(
        [mapping(muni_geom)],
        (rows, cols),
        transform,
        invert=True,
    )


def contours_geojson(
    elevation: np.ndarray,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
    muni_mask: np.ndarray | None = None,
    interval_m: float = 5.0,
    max_levels: int = 8,
    max_features: int = 80,
) -> dict[str, Any]:
    """Gera isolinhas de cota a partir do raster de elevação."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    elev = np.nan_to_num(elevation.astype(np.float64), nan=np.nanmean(elevation))
    if muni_mask is not None:
        elev = np.where(muni_mask, elev, np.nan)

    valid = np.isfinite(elev)
    if not valid.any():
        return {"type": "FeatureCollection", "features": []}

    e_min = float(np.nanmin(elev))
    e_max = float(np.nanmax(elev))
    span = e_max - e_min
    interval_m = max(interval_m, span / max_levels) if span > 0 else interval_m

    start = np.floor(e_min / interval_m) * interval_m
    levels = np.arange(start, e_max + interval_m, interval_m)
    if len(levels) > max_levels:
        step = max(1, int(np.ceil(len(levels) / max_levels)))
        levels = levels[::step]

    rows, cols = elev.shape
    yy = south + np.arange(rows) * res_y
    xx = west + np.arange(cols) * res_x

    features: list[dict[str, Any]] = []
    fig = plt.figure(figsize=(2, 2), dpi=80)
    ax = fig.add_subplot(111)
    try:
        cs = ax.contour(xx, yy, elev, levels=levels)
        for level_idx, segs in enumerate(cs.allsegs):
            if len(features) >= max_features:
                break
            level = float(cs.levels[level_idx])
            for seg in segs:
                if len(seg) < 10:
                    continue
                step = max(1, len(seg) // 32)
                coords = [[round(float(x), 6), round(float(y), 6)] for x, y in seg[::step]]
                if len(coords) < 4:
                    continue
                features.append({
                    "type": "Feature",
                    "properties": {
                        "layer_type": "contour",
                        "elevation_m": round(level, 1),
                        "nome": f"Cota {level:.0f} m",
                        "interval_m": round(interval_m, 1),
                    },
                    "geometry": {"type": "LineString", "coordinates": coords},
                })
                if len(features) >= max_features:
                    break
    finally:
        plt.close(fig)

    return {"type": "FeatureCollection", "features": features}


def _vectorize_band(
    depth: np.ndarray,
    lo: float,
    hi: float,
    muni_mask: np.ndarray,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
) -> list:
    import rasterio.features
    from rasterio.transform import from_bounds

    rows, cols = depth.shape
    north = south + rows * res_y
    east = west + cols * res_x
    transform = from_bounds(west, south, east, north, cols, rows)
    mask = muni_mask & (depth >= lo) & (depth < hi)
    if not mask.any():
        return []

    shapes = []
    for geom, _ in rasterio.features.shapes(
        mask.astype(np.uint8),
        mask=mask,
        transform=transform,
    ):
        shapes.append(shape(geom))
    return shapes


def _iri_raster_for_municipio(
    db: Session,
    muni_id: int,
    muni_mask: np.ndarray,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
) -> np.ndarray:
    """Rasteriza IRI por bairro para modular profundidade de alagamento."""
    import rasterio.features
    from rasterio.transform import from_bounds

    from app.services.analytical_engine import AnalyticalEngine

    rows, cols = muni_mask.shape
    north = south + rows * res_y
    east = west + cols * res_x
    transform = from_bounds(west, south, east, north, cols, rows)

    iri_map = {
        item["bairro_nome"]: float(item.get("indice_risco_inundacao", 0.5))
        for item in AnalyticalEngine.calculate_flood_risk(db, muni_id)
    }
    shapes = []
    for b in db.query(Bairro).filter(Bairro.municipio_id == muni_id).all():
        geom = shape(json.loads(db.scalar(b.geom.ST_AsGeoJSON())))
        iri = iri_map.get(b.nome, 0.5)
        shapes.append((mapping(geom), iri))

    if not shapes:
        return np.full(muni_mask.shape, 0.5, dtype=np.float64)

    return rasterio.features.rasterize(
        shapes,
        out_shape=muni_mask.shape,
        transform=transform,
        fill=0.5,
        dtype=np.float64,
    )


def landslide_features_from_slope(
    elevation: np.ndarray,
    muni_geom,
    muni_mask: np.ndarray,
    precip_mm: float,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
    db: Session,
    muni_id: int,
) -> list[dict[str, Any]]:
    """Identifica zonas de deslizamento por declividade DEM (substitui lista hardcoded)."""
    lat_c = (muni_geom.bounds[1] + muni_geom.bounds[3]) / 2.0
    slope_deg = _compute_slope_degrees(elev := np.nan_to_num(elevation, nan=np.nanmean(elevation)), lat_c, res_x, res_y)

    # Limiar diminui com precipitação extrema (solo saturado)
    slope_threshold = max(12.0, SLOPE_CRITICAL_DEG - (precip_mm / 15.0))
    landslide_mask = muni_mask & (slope_deg >= slope_threshold)
    if not landslide_mask.any():
        return []

    shapes = _vectorize_band(
        landslide_mask.astype(np.float64),
        0.5,
        1.5,
        muni_mask,
        west,
        south,
        res_x,
        res_y,
    )
    if not shapes:
        return []

    merged = unary_union(shapes).intersection(muni_geom)
    if merged.is_empty:
        return []

    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni_id).all()
    features: list[dict[str, Any]] = []
    for b in bairros:
        b_geom = shape(json.loads(db.scalar(b.geom.ST_AsGeoJSON())))
        zone = merged.intersection(b_geom)
        if zone.is_empty or zone.area < 1e-10:
            continue
        pct_slope = float(np.nanmean(slope_deg[muni_mask & (slope_deg >= slope_threshold)]))
        features.append({
            "type": "Feature",
            "geometry": mapping(zone),
            "properties": {
                "name": f"Risco de deslizamento — {b.nome}",
                "layer_type": "landslide",
                "precipitation_mm": precip_mm,
                "slope_threshold_deg": round(slope_threshold, 1),
                "mean_slope_deg": round(pct_slope, 1),
                "description": (
                    f"Encosta com declividade ≥ {slope_threshold:.0f}° sob precipitação de {precip_mm:.0f} mm."
                ),
            },
        })

    if not features:
        features.append({
            "type": "Feature",
            "geometry": mapping(merged),
            "properties": {
                "name": "Risco de deslizamento — área crítica",
                "layer_type": "landslide",
                "precipitation_mm": precip_mm,
                "slope_threshold_deg": round(slope_threshold, 1),
            },
        })
    return features


def build_bairro_risk_context(db: Session, muni_id: int) -> list[dict[str, Any]]:
    """Contexto IVC × IRI por bairro para análise interpretativa."""
    from app.services.analytical_engine import AnalyticalEngine

    ivc_map = {
        v["bairro_nome"]: v
        for v in AnalyticalEngine.calculate_climate_vulnerability(db, muni_id)
    }
    iri_map = {
        f["bairro_nome"]: f
        for f in AnalyticalEngine.calculate_flood_risk(db, muni_id)
    }
    names = sorted(set(ivc_map) | set(iri_map))
    rows: list[dict[str, Any]] = []

    for nome in names:
        ivc_row = ivc_map.get(nome, {})
        iri_row = iri_map.get(nome, {})
        ivc = float(ivc_row.get("indice_vulnerabilidade", 0.0))
        iri = float(iri_row.get("indice_risco_inundacao", 0.0))
        composite = round(ivc * 0.4 + iri * 0.6, 3)

        parts = []
        if ivc >= 0.6:
            parts.append("alta vulnerabilidade climática")
        if iri >= 0.6:
            parts.append("histórico/proximidade hídrica elevados")
        if float(iri_row.get("impermeabilizacao_score", 0)) >= 0.7:
            parts.append("alta impermeabilização")
        if not parts:
            parts.append("exposição moderada")

        rows.append({
            "bairro": nome,
            "ivc": ivc,
            "iri": iri,
            "composite_risk": composite,
            "exposicao": ivc_row.get("exposicao"),
            "s2id_score": iri_row.get("s2id_historico_score"),
            "impermeabilizacao": iri_row.get("impermeabilizacao_score"),
            "rationale": "; ".join(parts).capitalize() + ".",
        })

    return sorted(rows, key=lambda x: x["composite_risk"], reverse=True)


def flood_bands_geojson(
    elevation: np.ndarray,
    muni_geom,
    precip_mm: float,
    river_shapes: list,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
    iri_raster: np.ndarray | None = None,
) -> tuple[dict[str, Any], np.ndarray]:
    """Estima manchas de alagamento por profundidade com base em cota simulada + baixadas."""
    muni_mask = _muni_raster_mask(elevation, muni_geom, west, south, res_x, res_y)
    elev = np.nan_to_num(elevation, nan=np.nanmean(elevation))

    muni_elev = elev[muni_mask]
    if muni_elev.size == 0:
        return {"type": "FeatureCollection", "features": []}, muni_mask

    # Cota base: percentil 20 (vales) + incremento pluviométrico (mm → m, coef. escoamento)
    runoff_coeff = 0.35 + min(precip_mm / 500.0, 0.25)
    flood_rise_m = (precip_mm / 1000.0) * runoff_coeff * 8.0
    base_level = float(np.percentile(muni_elev, 20))
    water_level = base_level + flood_rise_m

    depth = np.maximum(0.0, water_level - elev)
    depth = np.where(muni_mask, depth, 0.0)

    # Modular profundidade pelo IRI local (bairros com maior risco acumulam mais água)
    if iri_raster is not None:
        depth = depth * (0.75 + 0.55 * np.clip(iri_raster, 0.0, 1.0))
        depth = np.where(muni_mask, depth, 0.0)

    # Reforço hidrográfico: expandir profundidade ao longo dos corpos d'água
    if river_shapes:
        from shapely.geometry import Point

        rows, cols = elevation.shape
        river_boost = np.zeros_like(depth)
        buffer_deg = (precip_mm / 100.0) * 0.0006
        combined = unary_union(river_shapes)
        river_zone = combined.buffer(buffer_deg)
        for r in range(0, rows, max(1, rows // 64)):
            for c in range(0, cols, max(1, cols // 64)):
                lon = west + c * res_x
                lat = south + r * res_y
                if river_zone.contains(Point(lon, lat)):
                    river_boost[r, c] = flood_rise_m * 1.4
        depth = np.maximum(depth, river_boost * muni_mask)

    features: list[dict[str, Any]] = []
    for band_id, lo, hi, label in DEPTH_BANDS:
        shapes = _vectorize_band(depth, lo, hi, muni_mask, west, south, res_x, res_y)
        if not shapes:
            continue
        merged = unary_union(shapes).intersection(muni_geom)
        if merged.is_empty:
            continue
        features.append({
            "type": "Feature",
            "geometry": mapping(merged),
            "properties": {
                "layer_type": "flood_band",
                "depth_band": band_id,
                "name": label,
                "precipitation_mm": precip_mm,
                "water_level_m": round(water_level, 2),
                "depth_min_m": lo,
                "depth_max_m": hi if hi < 900 else None,
                "fill_color": FLOOD_COLORS[band_id],
            },
        })

    return {"type": "FeatureCollection", "features": features}, depth


def load_flow_paths(codigo_ibge: str) -> dict[str, Any] | None:
    path = dem_dir(codigo_ibge) / "flow_paths.geojson"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def enrich_rainfall_simulation(
    db: Session,
    muni: Municipio,
    precip_mm: float,
) -> dict[str, Any]:
    """
    Retorna camadas auxiliares: manchas por profundidade (moduladas por IRI),
    deslizamento por declividade DEM, curvas de nível, escoamento e metadados.
    """
    risk_context = build_bairro_risk_context(db, muni.id)
    grid = _load_elevation_grid(db, muni.codigo_ibge, muni)
    if grid is None:
        return {
            "flood_bands": None,
            "contours": None,
            "flow_paths": None,
            "risk_context": risk_context,
            "simulation_meta": {"dem_available": False, "method": "heuristic", "iri_applied": False},
        }

    elev, west, south, res_x, res_y, meta = grid
    muni_geom = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))

    rivers = db.query(CoberturaVegetalMapBiomas.geom).filter(
        CoberturaVegetalMapBiomas.municipio_id == muni.id,
        CoberturaVegetalMapBiomas.classe_uso == "Corpo d'água",
    ).all()
    river_shapes = [
        shape(json.loads(db.scalar(r.geom.ST_AsGeoJSON())))
        for r in rivers
    ]

    muni_mask = _muni_raster_mask(elev, muni_geom, west, south, res_x, res_y)
    iri_raster = _iri_raster_for_municipio(db, muni.id, muni_mask, west, south, res_x, res_y)
    stats = meta.get("stats", {})
    interval = max(10.0, (stats.get("altitude_max_m", 50) - stats.get("altitude_min_m", 0)) / 8)

    flood_fc, depth_raster = flood_bands_geojson(
        elev, muni_geom, precip_mm, river_shapes, west, south, res_x, res_y,
        iri_raster=iri_raster,
    )
    contours = contours_geojson(
        elev, west, south, res_x, res_y, muni_mask=muni_mask, interval_m=interval,
    )

    flow = load_flow_paths(muni.codigo_ibge)
    if not flow or not flow.get("features"):
        flow = _flow_paths_geojson(elev, west, south, res_x, res_y, max_paths=16)

    for feat in flow.get("features", []):
        feat.setdefault("properties", {})["layer_type"] = "flow_path"

    landslide_features = landslide_features_from_slope(
        elev, muni_geom, muni_mask, precip_mm, west, south, res_x, res_y, db, muni.id,
    )
    all_flood_features = list(flood_fc.get("features", []))
    for ls in landslide_features:
        props = ls.setdefault("properties", {})
        props["layer_type"] = "landslide"
        props["fill_color"] = "#dc2626"
        all_flood_features.append(ls)

    lat_c = (muni_geom.bounds[1] + muni_geom.bounds[3]) / 2.0
    slope_deg = _compute_slope_degrees(elev, lat_c, res_x, res_y)
    crit_slope_pct = float(
        np.sum(muni_mask & (slope_deg >= SLOPE_CRITICAL_DEG)) / max(np.sum(muni_mask), 1) * 100.0
    )

    return {
        "flood_bands": {"type": "FeatureCollection", "features": all_flood_features},
        "contours": contours,
        "flow_paths": flow,
        "risk_context": risk_context,
        "simulation_meta": {
            "dem_available": True,
            "dem_source": meta.get("dem_source", "SRTM 30m"),
            "method": "dem_pluvial_proxy_iri",
            "iri_applied": True,
            "landslide_method": "dem_slope",
            "landslide_zones": len(landslide_features),
            "contour_interval_m": interval,
            "altitude_min_m": stats.get("altitude_min_m"),
            "altitude_max_m": stats.get("altitude_max_m"),
            "altitude_media_m": stats.get("altitude_media_m"),
            "declividade_media_graus": stats.get("declividade_media_graus"),
            "pct_declividade_critica": round(crit_slope_pct, 2),
            "precipitation_mm": precip_mm,
            "max_depth_m": round(float(np.max(depth_raster[muni_mask])), 2) if muni_mask.any() else 0,
        },
    }
