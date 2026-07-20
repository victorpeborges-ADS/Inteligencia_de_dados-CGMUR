"""Simulação pluvial enriquecida com DEM SRTM: manchas por profundidade, curvas de nível e escoamento."""
from __future__ import annotations

import json
import logging
import os
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
    _load_local_dem_geotiff,
    _meters_per_degree,
    _synthetic_dem,
    dem_dir,
    find_local_dem,
    is_processed,
    load_meta,
    process_municipality_dem,
)

# SRTM GL1 — resolução horizontal ~30 m; RMSE vertical típico ±16 m (NASA/USGS)
SRTM_HORIZONTAL_M = 30.0
SRTM_VERTICAL_RMSE_M = 16.0
HYDRO_MODEL_VERSION = "2.3"

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

MAX_FLOOD_POLYGONS_PER_BAND = 28
MIN_FLOOD_POLYGON_AREA_DEG2 = 1.5e-8
D8_OFFSETS = (
    (-1, 0),
    (1, 0),
    (0, -1),
    (0, 1),
    (-1, -1),
    (-1, 1),
    (1, -1),
    (1, 1),
)


def _compute_d8_accumulation(elevation: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Acúmulo de fluxo D8 — células a montante que drenam para cada pixel."""
    rows, cols = elevation.shape
    mean_elev = float(np.nanmean(elevation[mask])) if mask.any() else 0.0
    elev = np.where(mask, np.nan_to_num(elevation, nan=mean_elev), np.inf)

    acc = np.zeros((rows, cols), dtype=np.float64)
    acc[mask] = 1.0

    r_idx, c_idx = np.where(mask)
    order = np.argsort(-elev[r_idx, c_idx])

    for k in order:
        r, c = int(r_idx[k]), int(c_idx[k])
        if not mask[r, c]:
            continue
        cur = elev[r, c]
        best: tuple[int, int] | None = None
        best_drop = 0.0
        for dr, dc in D8_OFFSETS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and mask[nr, nc]:
                drop = cur - elev[nr, nc]
                if drop > best_drop:
                    best_drop = drop
                    best = (nr, nc)
        if best is not None:
            acc[best[0], best[1]] += acc[r, c]

    return acc


def _normalize_masked(values: np.ndarray, mask: np.ndarray, percentile: float = 98.0) -> np.ndarray:
    if not mask.any():
        return np.zeros_like(values)
    vmax = float(np.percentile(values[mask], percentile))
    if vmax <= 0:
        return np.zeros_like(values)
    return np.clip(values / vmax, 0.0, 1.0)


def _hydro_max_grid_dim() -> int:
    try:
        return max(128, int(os.getenv("HYDRO_MAX_GRID_DIM", "512")))
    except ValueError:
        return 512


def _downsample_elevation_grid(
    elev: np.ndarray,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
    max_dim: int | None = None,
) -> tuple[np.ndarray, float, float, float, float]:
    """Reduz grelha LiDAR/SRTM para o cálculo hidro (D8/manchas) sem perder o envelope."""
    limit = max_dim if max_dim is not None else _hydro_max_grid_dim()
    rows, cols = elev.shape
    if max(rows, cols) <= limit:
        return elev, west, south, res_x, res_y
    factor = int(np.ceil(max(rows, cols) / limit))
    new_rows = max(1, rows // factor)
    new_cols = max(1, cols // factor)
    trimmed = elev[: new_rows * factor, : new_cols * factor]
    block = trimmed.reshape(new_rows, factor, new_cols, factor)
    with np.errstate(all="ignore"):
        down = np.nanmean(block, axis=(1, 3))
    logger.info(
        "DEM hidro downsample %sx%s → %sx%s (factor=%s)",
        rows, cols, down.shape[0], down.shape[1], factor,
    )
    return down, west, south, res_x * factor, res_y * factor


def _load_elevation_grid(
    db: Session,
    codigo_ibge: str,
    muni: Municipio,
) -> tuple[np.ndarray, float, float, float, float, dict[str, Any]] | None:
    meta = load_meta(codigo_ibge)
    tif = dem_dir(codigo_ibge) / "dem.tif"

    # Preferir dem.tif já processado (evita re-clip do LiDAR a cada simulação fria)
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

    clip_bounds: tuple[float, float, float, float] | None = None
    try:
        geo = json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))
        west, south, east, north = shape(geo).bounds
        pad = max((east - west), (north - south)) * 0.05
        clip_bounds = (west - pad, south - pad, east + pad, north + pad)
    except Exception as exc:
        logger.debug("Bounds municipal indisponíveis: %s", exc)

    local_path = find_local_dem(codigo_ibge)
    if local_path and clip_bounds:
        loaded = _load_local_dem_geotiff(local_path, *clip_bounds)
        if loaded is not None:
            elev, res_x, res_y, west, south = loaded
            rows, cols = elev.shape
            meta = dict(meta or {})
            meta.setdefault("dem_source", "LiDAR/DSM local")
            meta["dem_resolution_m"] = _dem_resolution_m(res_x, res_y, south + rows * res_y / 2)
            return elev, west, south, res_x, res_y, meta

    if not tif.exists():
        try:
            if not is_processed(codigo_ibge):
                process_municipality_dem(db, codigo_ibge)
            meta = load_meta(codigo_ibge) or {}
            tif = dem_dir(codigo_ibge) / "dem.tif"
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


def _dem_resolution_m(res_x: float, res_y: float, lat_c: float) -> float:
    lon_m, lat_m = _meters_per_degree(lat_c)
    return float((abs(res_x) * lon_m + abs(res_y) * lat_m) / 2.0)


def _lat_grid(rows: int, south: float, res_y: float) -> np.ndarray:
    """Latitude por linha do raster (linha 0 = norte, padrão GeoTIFF)."""
    north = south + rows * res_y
    return north - (np.arange(rows) + 0.5) * res_y


def _lon_grid(cols: int, west: float, res_x: float) -> np.ndarray:
    return west + (np.arange(cols) + 0.5) * res_x


def _smooth_dem(elev: np.ndarray, mask: np.ndarray, passes: int = 2) -> np.ndarray:
    """Suaviza ruído do SRTM preservando o relevo geral (convolução vetorizada)."""
    if not mask.any():
        return elev
    mean_elev = float(np.nanmean(elev[mask]))
    work = np.where(mask, np.nan_to_num(elev, nan=mean_elev), mean_elev)
    k = np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=np.float64) / 16.0
    for _ in range(passes):
        padded = np.pad(work, 1, mode="edge")
        work = (
            k[0, 0] * padded[:-2, :-2]
            + k[0, 1] * padded[:-2, 1:-1]
            + k[0, 2] * padded[:-2, 2:]
            + k[1, 0] * padded[1:-1, :-2]
            + k[1, 1] * padded[1:-1, 1:-1]
            + k[1, 2] * padded[1:-1, 2:]
            + k[2, 0] * padded[2:, :-2]
            + k[2, 1] * padded[2:, 1:-1]
            + k[2, 2] * padded[2:, 2:]
        )
    return np.where(mask, work, np.nan)


def _adaptive_contour_interval(e_min: float, e_max: float, resolution_m: float) -> float:
    """Intervalo de cota proporcional ao desnível e à resolução do raster."""
    span = max(e_max - e_min, 0.0)
    if span <= 12:
        base = 2.0
    elif span <= 30:
        base = 5.0
    elif span <= 70:
        base = 10.0
    else:
        base = max(10.0, round(span / 14.0 / 5.0) * 5.0)
    # Intervalo mínimo compatível com resolução horizontal (≈1/15 da resolução)
    min_supported = max(2.0, resolution_m / 15.0)
    return float(max(min_supported, base))


def _simplify_line_coords(coords: list[list[float]], tolerance_deg: float) -> list[list[float]]:
    if len(coords) <= 6:
        return coords
    try:
        from shapely.geometry import LineString

        line = LineString(coords)
        simplified = line.simplify(max(tolerance_deg, 1e-7), preserve_topology=True)
        if simplified.is_empty:
            return coords
        if simplified.geom_type == "MultiLineString":
            longest = max(simplified.geoms, key=lambda g: g.length)
            return [[round(x, 6), round(y, 6)] for x, y in longest.coords]
        return [[round(x, 6), round(y, 6)] for x, y in simplified.coords]
    except Exception:
        return coords


def _is_index_contour(level: float, interval: float) -> bool:
    if interval <= 0:
        return False
    return int(round(level / interval)) % 5 == 0


def _contour_feature(
    level: float,
    coords: list[list[float]],
    interval_m: float,
    resolution_m: float,
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {
            "layer_type": "contour",
            "elevation_m": round(level, 1),
            "nome": f"Cota {level:.0f} m",
            "interval_m": round(interval_m, 1),
            "dem_resolution_m": round(resolution_m, 1),
            "index_contour": _is_index_contour(level, interval_m),
        },
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def contours_geojson(
    elevation: np.ndarray,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
    muni_mask: np.ndarray | None = None,
    interval_m: float | None = None,
    max_levels: int = 14,
    max_features: int = 140,
    lat_c: float | None = None,
) -> dict[str, Any]:
    """Gera isolinhas de cota a partir do raster de elevação (GeoTIFF north-up)."""
    rows, cols = elevation.shape
    lat_rows = _lat_grid(rows, south, res_y)
    lons = _lon_grid(cols, west, res_x)

    elev = elevation.astype(np.float64)
    if muni_mask is not None:
        elev = np.where(muni_mask, elev, np.nan)

    valid = np.isfinite(elev)
    if not valid.any():
        return {"type": "FeatureCollection", "features": []}

    elev_smooth = _smooth_dem(np.nan_to_num(elev, nan=float(np.nanmean(elev[valid]))), valid, passes=2)
    elev_smooth = np.where(valid, elev_smooth, np.nan)

    e_min = float(np.nanmin(elev_smooth))
    e_max = float(np.nanmax(elev_smooth))
    resolution_m = _dem_resolution_m(res_x, res_y, lat_c or float(lat_rows.mean()))
    if interval_m is None:
        interval_m = _adaptive_contour_interval(e_min, e_max, resolution_m)

    start = np.floor(e_min / interval_m) * interval_m
    levels = np.arange(start, e_max + interval_m * 0.5, interval_m)
    if len(levels) > max_levels:
        step = max(1, int(np.ceil(len(levels) / max_levels)))
        levels = levels[::step]

    features: list[dict[str, Any]] = []
    simplify_tol = max(abs(res_x), abs(res_y)) * 0.75

    try:
        import contourpy as cpy

        gen = cpy.contour_generator(lons, lat_rows, np.nan_to_num(elev_smooth, nan=e_min - interval_m))
        for level in levels:
            if len(features) >= max_features:
                break
            for seg in gen.lines(float(level)):
                if seg is None or len(seg) < 8:
                    continue
                coords = _simplify_line_coords(
                    [[round(float(x), 6), round(float(y), 6)] for x, y in seg],
                    simplify_tol,
                )
                if len(coords) < 4:
                    continue
                features.append(_contour_feature(level, coords, float(interval_m), resolution_m))
                if len(features) >= max_features:
                    break
    except Exception as exc:
        logger.warning("contourpy indisponível (%s) — fallback matplotlib", exc)
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        xx, yy = np.meshgrid(lons, lat_rows)
        fig = plt.figure(figsize=(2, 2), dpi=80)
        ax = fig.add_subplot(111)
        try:
            cs = ax.contour(xx, yy, np.nan_to_num(elev_smooth, nan=e_min - interval_m), levels=levels)
            for level_idx, segs in enumerate(cs.allsegs):
                if len(features) >= max_features:
                    break
                level = float(cs.levels[level_idx])
                for seg in segs:
                    if len(seg) < 8:
                        continue
                    coords = _simplify_line_coords(
                        [[round(float(x), 6), round(float(y), 6)] for x, y in seg],
                        simplify_tol,
                    )
                    if len(coords) < 4:
                        continue
                    features.append(_contour_feature(level, coords, float(interval_m), resolution_m))
                    if len(features) >= max_features:
                        break
        finally:
            plt.close(fig)

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "interval_m": round(float(interval_m), 1),
            "dem_resolution_m": round(resolution_m, 1),
            "vertical_accuracy_m": SRTM_VERTICAL_RMSE_M,
            "contour_count": len(features),
        },
    }


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


def _impermeability_raster_for_municipio(
    db: Session,
    muni_id: int,
    muni_mask: np.ndarray,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
) -> np.ndarray:
    """Rasteriza coeficiente de impermeabilização (0–1) a partir do MapBiomas."""
    import rasterio.features
    from rasterio.transform import from_bounds

    rows, cols = muni_mask.shape
    north = south + rows * res_y
    east = west + cols * res_x
    transform = from_bounds(west, south, east, north, cols, rows)

    class_to_imperm = {
        "Área Urbana": 0.88,
        "Área construída/outros": 0.82,
        "Corpo d'água": 0.05,
        "Vegetação / Floresta": 0.22,
    }
    shapes: list[tuple[Any, float]] = []
    coverages = (
        db.query(CoberturaVegetalMapBiomas.classe_uso, CoberturaVegetalMapBiomas.geom)
        .filter(CoberturaVegetalMapBiomas.municipio_id == muni_id)
        .all()
    )
    for row in coverages:
        geom = shape(json.loads(db.scalar(row.geom.ST_AsGeoJSON())))
        coef = class_to_imperm.get(row.classe_uso, 0.55)
        shapes.append((mapping(geom), coef))

    if not shapes:
        return np.full(muni_mask.shape, 0.65, dtype=np.float64)

    return rasterio.features.rasterize(
        shapes,
        out_shape=muni_mask.shape,
        transform=transform,
        fill=0.60,
        dtype=np.float64,
    )


def _river_depth_boost(
    depth: np.ndarray,
    muni_mask: np.ndarray,
    river_shapes: list,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
    precip_mm: float,
    flood_rise_m: float,
) -> np.ndarray:
    """Reforça profundidade ao longo de corpos d'água (buffer proporcional à chuva)."""
    if not river_shapes:
        return depth

    import rasterio.features
    from rasterio.transform import from_bounds

    rows, cols = depth.shape
    north = south + rows * res_y
    east = west + cols * res_x
    transform = from_bounds(west, south, east, north, cols, rows)
    buffer_deg = min(0.004, (precip_mm / 100.0) * 0.0008)
    combined = unary_union(river_shapes).buffer(buffer_deg)
    river_mask = rasterio.features.geometry_mask(
        [mapping(combined)],
        (rows, cols),
        transform,
        invert=True,
    )
    boost = flood_rise_m * (1.2 + min(precip_mm / 200.0, 0.8))
    return np.where(river_mask & muni_mask, np.maximum(depth, boost), depth)


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
    impermeability_raster: np.ndarray | None = None,
    slope_deg: np.ndarray | None = None,
    accumulation: np.ndarray | None = None,
) -> tuple[dict[str, Any], np.ndarray]:
    """Estima manchas de alagamento por profundidade com DEM, acúmulo D8 e impermeabilização."""
    muni_mask = _muni_raster_mask(elevation, muni_geom, west, south, res_x, res_y)
    elev = np.nan_to_num(elevation, nan=np.nanmean(elevation[muni_mask]) if muni_mask.any() else 0.0)

    muni_elev = elev[muni_mask]
    if muni_elev.size == 0:
        return {"type": "FeatureCollection", "features": []}, muni_mask

    if accumulation is None:
        accumulation = _compute_d8_accumulation(elev, muni_mask)
    if impermeability_raster is None:
        impermeability_raster = np.full(elev.shape, 0.60, dtype=np.float64)
    if slope_deg is None:
        lat_c = (muni_geom.bounds[1] + muni_geom.bounds[3]) / 2.0
        slope_deg = _compute_slope_degrees(elev, lat_c, res_x, res_y)

    runoff_coeff = 0.22 + 0.58 * np.clip(impermeability_raster, 0.0, 1.0)
    effective_rain_m = (precip_mm / 1000.0) * runoff_coeff
    flood_rise_m = effective_rain_m * (5.5 + min(precip_mm / 120.0, 1.5))

    muni_elev = elev[muni_mask]
    base_level = float(np.percentile(muni_elev, 10))
    mean_rise = float(np.mean(flood_rise_m[muni_mask]))
    acc_norm = _normalize_masked(accumulation, muni_mask)

    # Superfície d'água modulada por acúmulo D8 (vales e linhas de drenagem)
    water_surface = base_level + mean_rise * (1.0 + 0.75 * acc_norm)
    depth = np.maximum(0.0, water_surface - elev)
    depth = depth * (0.65 + 0.55 * effective_rain_m / max(float(np.mean(effective_rain_m[muni_mask])), 1e-6))
    depth = np.where(muni_mask, depth, 0.0)

    depth *= 1.0 + 1.6 * np.log1p(acc_norm * 6.0) / np.log(7.0)
    depth = np.where(muni_mask, depth, 0.0)

    slope_drain = np.clip(1.0 - slope_deg / 48.0, 0.22, 1.0)
    depth *= slope_drain
    depth = np.where(muni_mask, depth, 0.0)

    # Índice de umidade topográfica (TWI) — reforça baixadas e planícies
    twi = np.log1p(accumulation) - np.log1p(np.tan(np.radians(np.clip(slope_deg, 0.1, 60.0))))
    twi_norm = _normalize_masked(twi, muni_mask, percentile=96.0)
    depth *= 1.0 + 0.65 * twi_norm
    depth = np.where(muni_mask, depth, 0.0)

    if iri_raster is not None:
        depth = depth * (0.72 + 0.52 * np.clip(iri_raster, 0.0, 1.0))
        depth = np.where(muni_mask, depth, 0.0)

    depth = _river_depth_boost(
        depth, muni_mask, river_shapes, west, south, res_x, res_y, precip_mm, float(np.mean(flood_rise_m[muni_mask]))
    )
    depth = np.where(depth >= 0.04, depth, 0.0)
    depth = np.where(muni_mask, depth, 0.0)

    features: list[dict[str, Any]] = []
    for band_id, lo, hi, label in DEPTH_BANDS:
        shapes = _vectorize_band(depth, lo, hi, muni_mask, west, south, res_x, res_y)
        if not shapes:
            continue

        ranked = sorted(
            (s.intersection(muni_geom) for s in shapes if s.area >= MIN_FLOOD_POLYGON_AREA_DEG2),
            key=lambda g: g.area,
            reverse=True,
        )
        for idx, poly in enumerate(ranked[:MAX_FLOOD_POLYGONS_PER_BAND]):
            if poly.is_empty:
                continue
            geom = poly
            if geom.geom_type == "MultiPolygon" and len(geom.geoms) == 1:
                geom = geom.geoms[0]
            features.append({
                "type": "Feature",
                "geometry": mapping(geom),
                "properties": {
                    "layer_type": "flood_band",
                    "depth_band": band_id,
                    "patch_id": idx + 1,
                    "name": f"{label} — mancha {idx + 1}",
                    "precipitation_mm": precip_mm,
                    "water_level_m": round(float(np.mean(water_surface[muni_mask])), 2),
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
    elev, west, south, res_x, res_y = _downsample_elevation_grid(
        elev, west, south, res_x, res_y,
    )
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
    impermeability = _impermeability_raster_for_municipio(
        db, muni.id, muni_mask, west, south, res_x, res_y,
    )
    lat_c = (muni_geom.bounds[1] + muni_geom.bounds[3]) / 2.0
    slope_deg = _compute_slope_degrees(elev, lat_c, res_x, res_y)
    accumulation = _compute_d8_accumulation(elev, muni_mask)
    stats = meta.get("stats", {})
    resolution_m = _dem_resolution_m(res_x, res_y, lat_c)
    e_min = stats.get("altitude_min_m")
    e_max = stats.get("altitude_max_m")
    if e_min is None or e_max is None:
        muni_elev = elev[muni_mask]
        e_min = float(np.min(muni_elev)) if muni_elev.size else 0.0
        e_max = float(np.max(muni_elev)) if muni_elev.size else 50.0
    interval = _adaptive_contour_interval(float(e_min), float(e_max), resolution_m)

    flood_fc, depth_raster = flood_bands_geojson(
        elev, muni_geom, precip_mm, river_shapes, west, south, res_x, res_y,
        iri_raster=iri_raster,
        impermeability_raster=impermeability,
        slope_deg=slope_deg,
        accumulation=accumulation,
    )
    contours = contours_geojson(
        elev, west, south, res_x, res_y,
        muni_mask=muni_mask,
        interval_m=interval,
        lat_c=lat_c,
    )
    contour_props = contours.get("properties") or {}

    flow = load_flow_paths(muni.codigo_ibge)
    if not flow or not flow.get("features"):
        flow = _flow_paths_geojson(
            elev, west, south, res_x, res_y, max_paths=20, muni_mask=muni_mask,
        )

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
    crit_slope_pct = float(
        np.sum(muni_mask & (slope_deg >= SLOPE_CRITICAL_DEG)) / max(np.sum(muni_mask), 1) * 100.0
    )
    flood_features = [f for f in flood_fc.get("features", []) if f.get("properties", {}).get("layer_type") == "flood_band"]

    return {
        "flood_bands": {"type": "FeatureCollection", "features": all_flood_features},
        "contours": contours,
        "flow_paths": flow,
        "risk_context": risk_context,
        "simulation_meta": {
            "dem_available": True,
            "dem_source": meta.get("dem_source", "SRTM 30m"),
            "method": "dem_pluvial_d8_twi",
            "model_version": HYDRO_MODEL_VERSION,
            "iri_applied": True,
            "impermeability_applied": True,
            "flow_accumulation_applied": True,
            "twi_applied": True,
            "flood_patches": len(flood_features),
            "landslide_method": "dem_slope",
            "landslide_zones": len(landslide_features),
            "contour_interval_m": contour_props.get("interval_m", interval),
            "contour_count": contour_props.get("contour_count", len(contours.get("features", []))),
            "dem_resolution_m": contour_props.get("dem_resolution_m", round(resolution_m, 1)),
            "vertical_accuracy_m": SRTM_VERTICAL_RMSE_M,
            "altitude_min_m": stats.get("altitude_min_m"),
            "altitude_max_m": stats.get("altitude_max_m"),
            "altitude_media_m": stats.get("altitude_media_m"),
            "declividade_media_graus": stats.get("declividade_media_graus"),
            "pct_declividade_critica": round(crit_slope_pct, 2),
            "precipitation_mm": precip_mm,
            "max_depth_m": round(float(np.max(depth_raster[muni_mask])), 2) if muni_mask.any() else 0,
            "mean_impermeability": round(float(np.mean(impermeability[muni_mask])), 3) if muni_mask.any() else None,
            "max_flow_accumulation": int(np.max(accumulation[muni_mask])) if muni_mask.any() else 0,
            "precision_note": (
                f"DEM {meta.get('dem_source', 'SRTM 30m')} (~{round(resolution_m)} m); "
                f"isolinhas a cada {contour_props.get('interval_m', interval)} m; "
                f"incerteza vertical ±{SRTM_VERTICAL_RMSE_M:.0f} m."
            ),
        },
    }
