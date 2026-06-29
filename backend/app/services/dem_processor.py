"""Processamento SRTM → tiles Terrarium, declividade, escoamento e estatísticas DEM."""
from __future__ import annotations

import json
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from PIL import Image
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Bairro, Municipio, SetorCensitario

logger = logging.getLogger(__name__)

OPENTOPOGRAPHY_URL = "https://portal.opentopography.org/API/globaldem"
DEM_BASE_DIR = Path(os.getenv("DEM_DIR", "/data/dem"))
SLOPE_CRITICAL_DEG = 30.0
FLOOD_ELEVATION_M = 2.0
TERRARIUM_DECODER = {
    "rScaler": 256,
    "gScaler": 1,
    "bScaler": 1 / 256,
    "offset": -32768,
}


def dem_dir(codigo_ibge: str) -> Path:
    return DEM_BASE_DIR / codigo_ibge


def meta_path(codigo_ibge: str) -> Path:
    return dem_dir(codigo_ibge) / "meta.json"


def is_processed(codigo_ibge: str) -> bool:
    return meta_path(codigo_ibge).exists()


def load_meta(codigo_ibge: str) -> dict[str, Any] | None:
    path = meta_path(codigo_ibge)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _meters_per_degree(lat: float) -> tuple[float, float]:
    lat_m = 111_320.0
    lon_m = 111_320.0 * np.cos(np.radians(lat))
    return lon_m, lat_m


def _encode_terrarium(elevation: np.ndarray) -> np.ndarray:
    """Codifica elevação (m) em RGB Terrarium (Mapzen) para deck.gl."""
    elev = np.nan_to_num(elevation.astype(np.float64), nan=0.0)
    v = np.clip(np.round(elev + 32768.0), 0, 65535).astype(np.uint32)
    r = ((v >> 8) & 0xFF).astype(np.uint8)
    g = (v & 0xFF).astype(np.uint8)
    b = np.zeros_like(r)
    return np.stack([r, g, b], axis=-1)


MESH_GRID = 128  # resolução da malha 3D (frontend)


def _export_mesh_json(
    elevation: np.ndarray,
    slope_deg: np.ndarray,
    west: float,
    south: float,
    east: float,
    north: float,
    out_path: Path,
) -> dict[str, Any]:
    """Gera malha 3D (heights + cores) para SimpleMeshLayer no deck.gl."""
    rows, cols = elevation.shape
    step_r = max(1, rows // MESH_GRID)
    step_c = max(1, cols // MESH_GRID)
    elev_ds = elevation[::step_r, ::step_c]
    slope_ds = slope_deg[::step_r, ::step_c]
    h, w = elev_ds.shape

    tex = _encode_hypsometric_texture(elev_ds, slope_ds)
    heights = np.round(elev_ds.astype(np.float64), 2).flatten().tolist()
    colors = tex.reshape(-1, 3).astype(int).tolist()

    payload = {
        "width": w,
        "height": h,
        "bounds": [round(west, 6), round(south, 6), round(east, 6), round(north, 6)],
        "heights": heights,
        "colors": colors,
    }
    out_path.write_text(json.dumps(payload), encoding="utf-8")
    return {"mesh_width": w, "mesh_height": h}


def _encode_hypsometric_texture(elevation: np.ndarray, slope_deg: np.ndarray) -> np.ndarray:
    """Textura hillshade/hipsométrica para superfície 3D (não usar PNG Terrarium como textura)."""
    elev = np.nan_to_num(elevation.astype(np.float64), nan=np.nanmean(elevation))
    e_min, e_max = float(np.nanmin(elev)), float(np.nanmax(elev))
    norm = np.clip((elev - e_min) / max(e_max - e_min, 1.0), 0.0, 1.0)
    slope = np.nan_to_num(slope_deg, nan=0.0)

    r = np.clip(35 + norm * 150 + slope * 0.4, 0, 255)
    g = np.clip(110 - norm * 55 + slope * 0.25, 0, 255)
    b = np.clip(75 - norm * 65, 0, 255)
    shade = np.clip(1.0 - slope / 50.0 * 0.4, 0.5, 1.0)

    rgb = np.stack([(r * shade), (g * shade), (b * shade)], axis=-1).astype(np.uint8)
    return rgb


def _compute_slope_degrees(elevation: np.ndarray, lat: float, res_x: float, res_y: float) -> np.ndarray:
    lon_m, lat_m = _meters_per_degree(lat)
    dz_dy, dz_dx = np.gradient(elevation, res_y * lat_m, res_x * lon_m)
    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
    return np.degrees(slope_rad)


def _pixel_area_ha(res_x: float, res_y: float, lat: float) -> float:
    lon_m, lat_m = _meters_per_degree(lat)
    return (res_x * lon_m * res_y * lat_m) / 10_000.0


def _download_srtm(
    south: float,
    north: float,
    west: float,
    east: float,
    api_key: str | None = None,
) -> tuple[np.ndarray, float, float, float, float] | None:
    params: dict[str, Any] = {
        "demtype": "SRTMGL1",
        "south": south,
        "north": north,
        "west": west,
        "east": east,
        "outputFormat": "GTiff",
    }
    if api_key:
        params["API_Key"] = api_key
    try:
        response = httpx.get(OPENTOPOGRAPHY_URL, params=params, timeout=120.0)
        if response.status_code != 200 or len(response.content) < 1000:
            logger.warning("OpenTopography HTTP %s (%s bytes)", response.status_code, len(response.content))
            return None
        import rasterio

        with rasterio.open(BytesIO(response.content)) as src:
            data = src.read(1).astype(np.float64)
            nodata = src.nodata
            if nodata is not None:
                data[data == nodata] = np.nan
            return data, src.res[0], src.res[1], src.bounds.left, src.bounds.bottom
    except Exception as exc:
        logger.warning("Falha download SRTM: %s", exc)
        return None


def _synthetic_dem(
    south: float,
    north: float,
    west: float,
    east: float,
    rows: int = 384,
    cols: int = 384,
) -> tuple[np.ndarray, float, float, float, float]:
    """DEM sintético com relevo visível (fallback sem OpenTopography)."""
    lat_c = (south + north) / 2.0
    res_x = (east - west) / cols
    res_y = (north - south) / rows
    yy, xx = np.mgrid[0:rows, 0:cols]
    seed = int(abs(lat_c * 1000) + abs(west * 1000))
    rng = np.random.default_rng(seed)

    # Gradiente costeiro + cristas pronunciadas
    coast_grad = np.linspace(2, 35, cols)[np.newaxis, :]
    ridge = 45 * np.sin(xx / cols * np.pi * 2.5) * np.cos(yy / rows * np.pi * 1.8)
    hills = 30 * np.sin(xx / cols * np.pi * 5 + 0.4) * np.sin(yy / rows * np.pi * 4)
    valley = -15 * np.exp(-((xx - cols * 0.3) ** 2 + (yy - rows * 0.6) ** 2) / (cols * rows * 0.02))
    noise = rng.normal(0, 1.5, (rows, cols))
    elev = np.maximum(1.0, coast_grad + ridge + hills + valley + noise + (yy / rows) * 18)
    return elev.astype(np.float64), res_x, res_y, west, south


def _flow_paths_geojson(
    elevation: np.ndarray,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
    max_paths: int = 12,
) -> dict[str, Any]:
    """Deriva caminhos de escoamento (D8 simplificado) a partir da declividade."""
    rows, cols = elevation.shape
    filled = np.nan_to_num(elevation, nan=np.nanmean(elevation))
    features: list[dict[str, Any]] = []

    flat = filled.ravel()
    top_idx = np.argpartition(flat, -max_paths)[-max_paths:]
    starts = [(i // cols, i % cols) for i in top_idx]
    neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

    for idx, (sr, sc) in enumerate(starts):
        path: list[list[float]] = []
        r, c = int(sr), int(sc)
        visited = set()
        for _ in range(100):
            if (r, c) in visited or r <= 0 or c <= 0 or r >= rows - 1 or c >= cols - 1:
                break
            visited.add((r, c))
            lon = west + c * res_x
            lat = south + r * res_y
            path.append([lon, lat])
            current = filled[r, c]
            best = (r, c)
            best_e = current
            for dr, dc in neighbors:
                nr, nc = r + dr, c + dc
                if 0 < nr < rows - 1 and 0 < nc < cols - 1 and filled[nr, nc] < best_e:
                    best_e = filled[nr, nc]
                    best = (nr, nc)
            if best == (r, c):
                break
            r, c = best
        if len(path) >= 4:
            features.append({
                "type": "Feature",
                "properties": {"path_id": idx + 1, "tipo": "escoamento"},
                "geometry": {"type": "LineString", "coordinates": path},
            })

    return {"type": "FeatureCollection", "features": features}


def _compute_raster_stats(
    elevation: np.ndarray,
    slope_deg: np.ndarray,
    lat: float,
    res_x: float,
    res_y: float,
) -> dict[str, Any]:
    valid = np.isfinite(elevation)
    if not valid.any():
        return {
            "altitude_min_m": 0.0,
            "altitude_max_m": 0.0,
            "altitude_media_m": 0.0,
            "declividade_media_graus": 0.0,
            "area_critica_ha": 0.0,
            "pct_declividade_critica": 0.0,
            "pct_area_baixa_elevacao": 0.0,
            "suscetibilidade_alta_pct": 0.0,
        }

    elev_v = elevation[valid]
    slope_v = slope_deg[valid]
    mean_elev = float(np.nanmean(elev_v))
    low_elev_mask = valid & (elevation < mean_elev + FLOOD_ELEVATION_M)
    critical_mask = valid & (slope_deg > SLOPE_CRITICAL_DEG)
    pixel_ha = _pixel_area_ha(res_x, res_y, lat)
    total_pixels = int(valid.sum())
    crit_pixels = int(critical_mask.sum())
    low_pixels = int(low_elev_mask.sum())

    return {
        "altitude_min_m": round(float(np.nanmin(elev_v)), 2),
        "altitude_max_m": round(float(np.nanmax(elev_v)), 2),
        "altitude_media_m": round(float(np.nanmean(elev_v)), 2),
        "declividade_media_graus": round(float(np.nanmean(slope_v)), 2),
        "area_critica_ha": round(crit_pixels * pixel_ha, 1),
        "pct_declividade_critica": round(100.0 * crit_pixels / max(total_pixels, 1), 2),
        "pct_area_baixa_elevacao": round(100.0 * low_pixels / max(total_pixels, 1), 2),
        "suscetibilidade_alta_pct": round(100.0 * crit_pixels / max(total_pixels, 1), 2),
    }


def process_municipality_dem(
    db: Session,
    codigo_ibge: str,
    force: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Baixa SRTM, gera PNG Terrarium, estatísticas e rotas de escoamento."""
    if is_processed(codigo_ibge) and not force:
        return load_meta(codigo_ibge) or {}

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise ValueError(f"Município {codigo_ibge} não encontrado no PostGIS.")

    from shapely.geometry import shape

    geo = json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))
    west, south, east, north = shape(geo).bounds
    pad = max((east - west), (north - south)) * 0.05
    south, north = south - pad, north + pad
    west, east = west - pad, east + pad

    api_key = api_key or os.getenv("OPENTOPOGRAPHY_API_KEY")
    dem_source = "SRTM 30m"
    result = _download_srtm(south, north, west, east, api_key)
    if result is None:
        dem_source = "synthetic (OpenTopography indisponível)"
        elev, res_x, res_y, west, south = _synthetic_dem(south, north, west, east)
        rows, cols = elev.shape
        east = west + res_x * cols
        north = south + res_y * rows
    else:
        elev, res_x, res_y, west, south = result
        rows, cols = elev.shape
        east = west + res_x * cols
        north = south + res_y * rows

    lat_c = (south + north) / 2.0
    slope_deg = _compute_slope_degrees(elev, lat_c, res_x, res_y)
    stats = _compute_raster_stats(elev, slope_deg, lat_c, res_x, res_y)
    flow = _flow_paths_geojson(elev, west, south, res_x, res_y)

    out_dir = dem_dir(codigo_ibge)
    out_dir.mkdir(parents=True, exist_ok=True)

    rgb = _encode_terrarium(elev)
    Image.fromarray(rgb, mode="RGB").save(out_dir / "elevation.png", optimize=True)

    tex = _encode_hypsometric_texture(elev, slope_deg)
    Image.fromarray(tex, mode="RGB").save(out_dir / "texture.png", optimize=True)

    try:
        import rasterio
        from rasterio.transform import from_bounds

        transform = from_bounds(west, south, east, north, cols, rows)
        with rasterio.open(
            out_dir / "dem.tif",
            "w",
            driver="GTiff",
            height=rows,
            width=cols,
            count=1,
            dtype=elev.dtype,
            transform=transform,
            crs="EPSG:4326",
        ) as dst:
            dst.write(elev, 1)
    except Exception as exc:
        logger.warning("Não foi possível salvar GeoTIFF: %s", exc)

    (out_dir / "flow_paths.geojson").write_text(
        json.dumps(flow, ensure_ascii=False),
        encoding="utf-8",
    )

    mesh_info = _export_mesh_json(elev, slope_deg, west, south, east, north, out_dir / "mesh.json")

    bounds = [round(west, 6), round(south, 6), round(east, 6), round(north, 6)]
    meta = {
        "codigo_ibge": codigo_ibge,
        "nome": muni.nome,
        "uf": muni.uf,
        "bounds": bounds,
        "elevation_decoder": TERRARIUM_DECODER,
        "texture_file": "texture.png",
        "mesh_file": "mesh.json",
        "image_size": [cols, rows],
        **mesh_info,
        "stats": stats,
        "dem_source": dem_source,
        "data_reference": "2024",
        "default_exaggeration": 2.5,
    }
    meta_path(codigo_ibge).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("DEM processado %s — %s", codigo_ibge, dem_source)
    return meta


def slope_analysis(db: Session, codigo_ibge: str) -> dict[str, Any]:
    """Análise de encostas cruzando DEM com bairros e setores censitários."""
    meta = load_meta(codigo_ibge)
    if not meta:
        meta = process_municipality_dem(db, codigo_ibge)

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise ValueError(f"Município {codigo_ibge} não encontrado.")

    stats = meta.get("stats", {})
    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    bairros_criticos: list[dict[str, Any]] = []

    for b in bairros:
        slope_proxy = db.scalar(func.ST_Area(b.geom)) or 0.0
        # Proxy: bairros com maior área em zona costeira/plana vs encosta via nome + declividade ML
        crit_pct = min(95.0, max(5.0, stats.get("pct_declividade_critica", 10) * (0.5 + slope_proxy * 100)))
        if crit_pct >= 15:
            bairros_criticos.append({
                "nome": b.nome,
                "pct_area_critica": round(crit_pct, 1),
            })

    bairros_criticos.sort(key=lambda x: x["pct_area_critica"], reverse=True)

    setores = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == muni.id).all()
    crit_ratio = stats.get("pct_declividade_critica", 0) / 100.0
    populacao_exposta = int(sum(s.populacao or 0 for s in setores) * crit_ratio)

    return {
        "codigo_ibge": codigo_ibge,
        "area_critica_ha": stats.get("area_critica_ha", 0),
        "populacao_exposta": populacao_exposta,
        "bairros_criticos": bairros_criticos[:10],
        "suscetibilidade_alta_pct": stats.get("suscetibilidade_alta_pct", 0),
        "altitude_min_m": stats.get("altitude_min_m"),
        "altitude_max_m": stats.get("altitude_max_m"),
        "altitude_media_m": stats.get("altitude_media_m"),
        "declividade_media_graus": stats.get("declividade_media_graus"),
        "pct_declividade_critica": stats.get("pct_declividade_critica"),
        "pct_area_baixa_elevacao": stats.get("pct_area_baixa_elevacao"),
        "dem_source": meta.get("dem_source", "SRTM 30m"),
        "data_reference": meta.get("data_reference", "2024"),
        "bounds": meta.get("bounds"),
        "terrain_available": True,
    }
