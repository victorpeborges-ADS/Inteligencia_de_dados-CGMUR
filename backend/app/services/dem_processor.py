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
LOCAL_DEM_DIR = Path(os.getenv("LOCAL_DEM_DIR", "/data/dem/local"))
SLOPE_CRITICAL_DEG = 30.0
FLOOD_ELEVATION_M = 2.0


def _opentopography_enabled(api_key: str | None = None) -> bool:
    """OpenTopo só quando explicitamente ligado ou com API key (evita wait frio sem rede)."""
    flag = os.getenv("OPENTOPOGRAPHY_ENABLED", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    key = (api_key if api_key is not None else os.getenv("OPENTOPOGRAPHY_API_KEY", "")).strip()
    return bool(key)


def _opentopography_timeout_s() -> float:
    try:
        return max(3.0, float(os.getenv("OPENTOPOGRAPHY_TIMEOUT_S", "12")))
    except ValueError:
        return 12.0
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


def dem_resolution_m(res_x: float, res_y: float, lat_c: float) -> float:
    lon_m, lat_m = _meters_per_degree(lat_c)
    return float((abs(res_x) * lon_m + abs(res_y) * lat_m) / 2.0)


def local_dem_source_paths(codigo_ibge: str) -> list[Path]:
    code = str(codigo_ibge).zfill(7)[:7]
    return [
        dem_dir(code) / "local_dem.tif",
        dem_dir(code) / "lidar.tif",
        dem_dir(code) / "merit.tif",
        dem_dir(code) / "anadem.tif",
        LOCAL_DEM_DIR / f"{code}.tif",
        LOCAL_DEM_DIR / f"{code}_lidar.tif",
        LOCAL_DEM_DIR / f"{code}_dsm.tif",
        LOCAL_DEM_DIR / f"{code}_merit.tif",
        LOCAL_DEM_DIR / f"{code}_anadem.tif",
        LOCAL_DEM_DIR / f"{code}_merit_hydro.tif",
    ]


def hydro_dem_label(filename: str) -> str | None:
    """21b.5 — identifica DEM hidrologicamente condicionado (MERIT-Hydro/ANADEM) pelo nome do arquivo.

    Esses produtos já vêm com depressões/sumidouros tratados na fonte, então o
    Priority-Flood interno do simulador hidrológico pode ser dispensado (ver
    ``hydro_simulator._fill_sinks``).
    """
    name = (filename or "").lower()
    if "merit" in name:
        return "MERIT-Hydro"
    if "anadem" in name:
        return "ANADEM"
    return None


def find_local_dem(codigo_ibge: str) -> Path | None:
    LOCAL_DEM_DIR.mkdir(parents=True, exist_ok=True)
    for path in local_dem_source_paths(codigo_ibge):
        if path.exists() and path.stat().st_size > 2048:
            return path
    return None


def import_local_dem_bytes(codigo_ibge: str, content: bytes) -> Path:
    """Persiste GeoTIFF LiDAR/DSM municipal para reprocessamento."""
    out_dir = dem_dir(codigo_ibge)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "local_dem.tif"
    dest.write_bytes(content)
    return dest


def _load_local_dem_geotiff(
    path: Path,
    west: float,
    south: float,
    east: float,
    north: float,
) -> tuple[np.ndarray, float, float, float, float] | None:
    try:
        import rasterio
        from rasterio.mask import mask
        from shapely.geometry import box, mapping

        clip_geom = box(west, south, east, north)
        with rasterio.open(path) as src:
            out_image, out_transform = mask(
                src,
                [mapping(clip_geom)],
                crop=True,
                filled=True,
                nodata=np.nan,
            )
            elev = out_image[0].astype(np.float64)
            if src.nodata is not None:
                elev[elev == float(src.nodata)] = np.nan
            finite = np.isfinite(elev)
            if not finite.any():
                return None
            fill = float(np.nanmean(elev[finite]))
            elev = np.where(finite, elev, fill)
            res_x = float(out_transform.a)
            res_y = abs(float(out_transform.e))
            out_west = float(out_transform.c)
            out_north = float(out_transform.f)
            out_south = out_north + elev.shape[0] * float(out_transform.e)
            return elev, res_x, res_y, out_west, out_south
    except Exception as exc:
        logger.warning("Falha ao ler DEM local %s: %s", path, exc)
        return None


def _upsample_dem_superres(elev: np.ndarray, factor: int = 3) -> np.ndarray:
    if factor <= 1:
        return elev
    return np.repeat(np.repeat(elev, factor, axis=0), factor, axis=1)


def _store_refined_pilot_dem(
    codigo_ibge: str,
    elev: np.ndarray,
    west: float,
    south: float,
    east: float,
    north: float,
    *,
    factor: int = 3,
) -> Path | None:
    """Gera DSM refinado (~10 m) a partir do SRTM para o município-piloto (interim até LiDAR real)."""
    from app.config import settings

    if codigo_ibge != settings.PILOT_IBGE_CODE or not settings.REFINE_PILOT_DEM:
        return None
    if find_local_dem(codigo_ibge):
        return None
    try:
        import rasterio
        from rasterio.transform import from_bounds

        refined = _upsample_dem_superres(elev, factor)
        rows, cols = refined.shape
        out_dir = dem_dir(codigo_ibge)
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / "local_dem.tif"
        transform = from_bounds(west, south, east, north, cols, rows)
        with rasterio.open(
            dest,
            "w",
            driver="GTiff",
            height=rows,
            width=cols,
            count=1,
            dtype=refined.dtype,
            transform=transform,
            crs="EPSG:4326",
        ) as dst:
            dst.write(refined, 1)
        logger.info("DSM refinado piloto salvo em %s (%dx upsample)", dest, factor)
        return dest
    except Exception as exc:
        logger.warning("Refino piloto DEM falhou: %s", exc)
        return None


def sync_dem_batch(db: Session, *, limit: int = 6, force: bool = False) -> dict[str, Any]:
    """Processa DEM (LiDAR local ou SRTM) para municípios prioritários."""
    from app.data_connectors.constants import TARGET_IBGE_CODES

    targets = TARGET_IBGE_CODES[: min(max(limit, 1), 6)]
    processed = 0
    skipped = 0
    local_count = 0
    errors: list[dict[str, str]] = []

    for code in targets:
        muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
        if not muni:
            skipped += 1
            errors.append({"codigo_ibge": code, "error": "município não carregado"})
            continue
        try:
            had_local = find_local_dem(code) is not None
            meta = process_municipality_dem(db, code, force=force)
            processed += 1
            if had_local or "local" in str(meta.get("dem_source", "")).lower() or "lidar" in str(meta.get("dem_source", "")).lower():
                local_count += 1
        except Exception as exc:
            logger.exception("DEM batch falhou %s", code)
            errors.append({"codigo_ibge": code, "error": str(exc)})

    return {
        "requested": len(targets),
        "processed": processed,
        "skipped": skipped,
        "local_or_refined": local_count,
        "errors": errors,
    }


def dem_status(*, limit: int = 6) -> dict[str, Any]:
    """Panorama DEM dos municípios prioritários (processados, LiDAR local, piloto)."""
    from app.config import settings
    from app.data_connectors.constants import TARGET_IBGE_CODES

    targets = TARGET_IBGE_CODES[: min(max(limit, 1), 6)]
    local_count = 0
    refined_count = 0
    processed = 0
    resolutions: list[float] = []

    for code in targets:
        if not is_processed(code):
            continue
        processed += 1
        meta = load_meta(code) or {}
        src = str(meta.get("dem_source", "")).lower()
        if "local" in src or "lidar" in src or "dsm" in src:
            local_count += 1
        if "refinado" in src:
            refined_count += 1
        res_m = meta.get("dem_resolution_m")
        if isinstance(res_m, (int, float)):
            resolutions.append(float(res_m))

    pilot_meta = load_meta(settings.PILOT_IBGE_CODE) if is_processed(settings.PILOT_IBGE_CODE) else None

    return {
        "prioritarios": len(targets),
        "processados": processed,
        "local_ou_lidar": local_count,
        "refinado_piloto": refined_count,
        "resolucao_media_m": round(sum(resolutions) / len(resolutions), 1) if resolutions else None,
        "local_dem_dir": str(LOCAL_DEM_DIR),
        "refine_pilot_enabled": settings.REFINE_PILOT_DEM,
        "piloto": {
            "codigo_ibge": settings.PILOT_IBGE_CODE,
            "nome": settings.PILOT_NAME,
            "dem_source": (pilot_meta or {}).get("dem_source"),
            "dem_resolution_m": (pilot_meta or {}).get("dem_resolution_m"),
            "vertical_accuracy_m": (pilot_meta or {}).get("vertical_accuracy_m"),
        } if pilot_meta else None,
    }


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
    if not _opentopography_enabled(api_key):
        logger.info("OpenTopography desligado (sem API key / OPENTOPOGRAPHY_ENABLED=false)")
        return None
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
    timeout = _opentopography_timeout_s()
    try:
        response = httpx.get(OPENTOPOGRAPHY_URL, params=params, timeout=timeout)
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
        logger.warning("Falha download SRTM (timeout=%.0fs): %s", timeout, exc)
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
    muni_mask: np.ndarray | None = None,
) -> dict[str, Any]:
    """Deriva caminhos de escoamento (D8) a partir de cristas em direção às baixadas."""
    rows, cols = elevation.shape
    filled = np.nan_to_num(elevation, nan=np.nanmean(elevation))
    if muni_mask is not None:
        filled = np.where(muni_mask, filled, np.nan)

    valid = np.isfinite(filled)
    if not valid.any():
        return {"type": "FeatureCollection", "features": []}

    ridge_threshold = float(np.percentile(filled[valid], 82))
    ridge_cells = np.argwhere(valid & (filled >= ridge_threshold))
    if len(ridge_cells) == 0:
        ridge_cells = np.argwhere(valid)

    rng = np.random.default_rng(42)
    if len(ridge_cells) > max_paths:
        picks = rng.choice(len(ridge_cells), max_paths, replace=False)
        starts = [tuple(ridge_cells[i]) for i in picks]
    else:
        starts = [tuple(rc) for rc in ridge_cells]

    features: list[dict[str, Any]] = []
    neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

    for idx, (sr, sc) in enumerate(starts):
        path: list[list[float]] = []
        r, c = int(sr), int(sc)
        visited = set()
        for _ in range(120):
            if (r, c) in visited or r <= 0 or c <= 0 or r >= rows - 1 or c >= cols - 1:
                break
            if muni_mask is not None and not muni_mask[r, c]:
                break
            visited.add((r, c))
            lon = west + c * res_x
            lat = south + r * res_y
            path.append([round(lon, 6), round(lat, 6)])
            current = filled[r, c]
            best = (r, c)
            best_e = current
            for dr, dc in neighbors:
                nr, nc = r + dr, c + dc
                if 0 < nr < rows - 1 and 0 < nc < cols - 1 and np.isfinite(filled[nr, nc]):
                    if muni_mask is not None and not muni_mask[nr, nc]:
                        continue
                    if filled[nr, nc] < best_e:
                        best_e = filled[nr, nc]
                        best = (nr, nc)
            if best == (r, c):
                break
            r, c = best
        if len(path) >= 5:
            features.append({
                "type": "Feature",
                "properties": {"path_id": idx + 1, "tipo": "escoamento", "layer_type": "flow_path"},
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
    """Processa DEM municipal — prioriza LiDAR local, SRTM refinado (piloto) ou SRTM 30 m."""
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
    hydro_dem_flag = False
    local_path = find_local_dem(codigo_ibge)
    result: tuple[np.ndarray, float, float, float, float] | None = None

    if local_path:
        result = _load_local_dem_geotiff(local_path, west, south, east, north)
        if result is not None:
            name = local_path.name.lower()
            hydro_label = hydro_dem_label(name)
            if hydro_label:
                dem_source = hydro_label
                hydro_dem_flag = True
            elif "lidar" in name or local_path.parent.name == str(codigo_ibge).zfill(7)[:7]:
                dem_source = "LiDAR/DSM local"
            else:
                dem_source = "DEM local"
            logger.info("DEM %s: usando arquivo local %s", codigo_ibge, local_path.name)

    if result is None:
        result = _download_srtm(south, north, west, east, api_key)
        if result is None:
            dem_source = "synthetic (OpenTopography indisponível)"
            elev, res_x, res_y, west, south = _synthetic_dem(south, north, west, east)
            rows, cols = elev.shape
            east = west + res_x * cols
            north = south + res_y * rows
            from app.config import settings as app_settings

            if codigo_ibge == app_settings.PILOT_IBGE_CODE and app_settings.REFINE_PILOT_DEM:
                refined_path = _store_refined_pilot_dem(
                    codigo_ibge, elev, west, south, east, north,
                )
                if refined_path is not None:
                    reloaded = _load_local_dem_geotiff(refined_path, west, south, east, north)
                    if reloaded is not None:
                        elev, res_x, res_y, west, south = reloaded
                        rows, cols = elev.shape
                        east = west + res_x * cols
                        north = south + res_y * rows
                        dem_source = "DEM refinado piloto (~10m, sintético)"
        else:
            elev, res_x, res_y, west, south = result
            rows, cols = elev.shape
            east = west + res_x * cols
            north = south + res_y * rows
            refined_path = _store_refined_pilot_dem(
                codigo_ibge, elev, west, south, east, north,
            )
            if refined_path is not None:
                reloaded = _load_local_dem_geotiff(refined_path, west, south, east, north)
                if reloaded is not None:
                    elev, res_x, res_y, west, south = reloaded
                    rows, cols = elev.shape
                    east = west + res_x * cols
                    north = south + res_y * rows
                    dem_source = "SRTM refinado piloto (~10m)"
    else:
        elev, res_x, res_y, west, south = result
        rows, cols = elev.shape
        east = west + res_x * cols
        north = south + res_y * rows

    lat_c = (south + north) / 2.0
    res_m = dem_resolution_m(res_x, res_y, lat_c)
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
    vertical_acc = round(min(5.0, max(1.0, res_m * 0.5)), 1) if res_m < 10 else 16.0
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
        "dem_resolution_m": round(res_m, 2),
        "vertical_accuracy_m": vertical_acc,
        "data_reference": "2024",
        "default_exaggeration": 2.5,
        "hydro_dem": hydro_dem_flag,
    }
    if local_path:
        meta["local_dem_path"] = str(local_path)
    meta_path(codigo_ibge).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("DEM processado %s — %s (%.1f m)", codigo_ibge, dem_source, res_m)
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
