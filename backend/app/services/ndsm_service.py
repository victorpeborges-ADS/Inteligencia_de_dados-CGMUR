import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
from shapely.geometry import shape
from sqlalchemy.orm import Session

from app.models import Edificacao, Municipio
from app.services.dem_processor import LOCAL_DEM_DIR, dem_dir, find_local_dem, load_meta, meta_path

logger = logging.getLogger(__name__)

LEVEL_HEIGHT_M = 3.0
NDSM_MAX_M = 80.0
NDSM_MIN_BUILDING_M = 2.5
# Janela ~45–60 m em pixels (ajustada pela resolução)
GROUND_WINDOW_M = 50.0


def ndsm_path(codigo_ibge: str) -> Path:
    return dem_dir(codigo_ibge) / "ndsm.tif"


_MDT_NAMES = frozenset({"lidar.tif", "mdt.tif"})


def _is_mdt_filename(path: Path) -> bool:
    name = path.name.lower()
    return name in _MDT_NAMES or name.endswith("_lidar.tif") or name.endswith("_mdt.tif")


def find_local_dsm(codigo_ibge: str) -> Path | None:
    """Prefere MDS/DSM real (`*_dsm.tif` / `local_dem.tif`).

    Não usa SRTM genérico (`{ibge}.tif`) nem MDT PE3D (`*_lidar.tif`) como superfície —
    isso gera nDSM espúrio (SRTM−MDT) ou ~0 (MDT−minfilter).
    """
    code = str(codigo_ibge).zfill(7)[:7]
    LOCAL_DEM_DIR.mkdir(parents=True, exist_ok=True)
    candidates = [
        dem_dir(code) / "dsm.tif",
        LOCAL_DEM_DIR / f"{code}_dsm.tif",
        dem_dir(code) / "mds.tif",
        LOCAL_DEM_DIR / f"{code}_mds.tif",
        dem_dir(code) / "local_dem.tif",
    ]
    for path in candidates:
        if path.exists() and path.stat().st_size > 2048 and not _is_mdt_filename(path):
            return path
    return None


def find_local_mdt(codigo_ibge: str) -> Path | None:
    """MDT PE3D / terreno — DTM verdadeiro quando MDS também existe."""
    code = str(codigo_ibge).zfill(7)[:7]
    candidates = [
        dem_dir(code) / "mdt.tif",
        dem_dir(code) / "lidar.tif",
        LOCAL_DEM_DIR / f"{code}_mdt.tif",
        LOCAL_DEM_DIR / f"{code}_lidar.tif",
    ]
    for path in candidates:
        if path.exists() and path.stat().st_size > 2048:
            return path
    return None


def _ground_window_px(res_m: float) -> int:
    px = int(round(GROUND_WINDOW_M / max(res_m, 1.0)))
    px = max(5, min(px | 1, 51))  # ímpar, limitado
    return px


def _approx_res_m(transform, src) -> float:
    try:
        rx, ry = src.res
        if abs(rx) < 1:  # graus
            lat = float(transform.f)
            return float(abs(rx) * 111_320.0 * abs(np.cos(np.radians(lat))))
        return float((abs(rx) + abs(ry)) / 2.0)
    except Exception:
        return 20.0


def build_ndsm(codigo_ibge: str, *, force: bool = False) -> dict[str, Any]:
    """Gera nDSM GeoTIFF a partir do DSM/LiDAR local. Requer rasterio."""
    code = str(codigo_ibge).zfill(7)[:7]
    out = ndsm_path(code)
    if out.exists() and not force:
        meta = load_meta(code) or {}
        return {
            "codigo_ibge": code,
            "status": "cached",
            "path": str(out),
            "dem_source": meta.get("dem_source"),
        }

    src_path = find_local_dsm(code)
    if not src_path:
        cand = dem_dir(code) / "dem.tif"
        src_path = cand if cand.exists() else None
    if not src_path:
        return {"codigo_ibge": code, "status": "sem_dsm", "path": None}

    mdt_path = find_local_mdt(code)

    try:
        import rasterio
        from rasterio.warp import reproject, Resampling
        from scipy import ndimage
    except ImportError as exc:
        return {"codigo_ibge": code, "status": "deps_ausentes", "erro": str(exc)}

    dem_dir(code).mkdir(parents=True, exist_ok=True)
    method = "dsm_minus_minfilter_dtm_proxy"
    with rasterio.open(src_path) as src:
        dsm = src.read(1).astype(np.float64)
        nodata = src.nodata
        if nodata is not None:
            dsm[dsm == float(nodata)] = np.nan
        transform = src.transform
        profile = src.profile.copy()
        res_m = _approx_res_m(transform, src)
        win = _ground_window_px(res_m)
        finite = np.isfinite(dsm)

        dtm = None
        if mdt_path and src_path.resolve() != mdt_path.resolve():
            try:
                with rasterio.open(mdt_path) as mdt_src:
                    dtm = np.empty(dsm.shape, dtype=np.float64)
                    reproject(
                        source=rasterio.band(mdt_src, 1),
                        destination=dtm,
                        src_transform=mdt_src.transform,
                        src_crs=mdt_src.crs,
                        dst_transform=transform,
                        dst_crs=src.crs,
                        resampling=Resampling.bilinear,
                        src_nodata=mdt_src.nodata,
                        dst_nodata=np.nan,
                    )
                    method = "mds_minus_mdt"
            except Exception as exc:
                logger.warning("nDSM: falha ao alinhar MDT %s: %s", mdt_path, exc)
                dtm = None

        if dtm is None:
            fill_val = float(np.nanmax(dsm)) if finite.any() else 0.0
            filled = np.where(finite, dsm, fill_val)
            dtm = ndimage.minimum_filter(filled, size=win, mode="nearest")

        ndsm = np.clip(dsm - dtm, 0.0, NDSM_MAX_M)
        ndsm = np.where(finite, ndsm, np.nan)

        profile.update(dtype="float32", count=1, nodata=-9999.0, compress="deflate")
        with rasterio.open(out, "w", **profile) as dst:
            dst.write(np.nan_to_num(ndsm, nan=-9999.0).astype(np.float32), 1)

        finite_n = ndsm[np.isfinite(ndsm)]
        stats = {
            "ndsm_min_m": float(np.min(finite_n)) if finite_n.size else None,
            "ndsm_max_m": float(np.max(finite_n)) if finite_n.size else None,
            "ndsm_p95_m": float(np.percentile(finite_n, 95)) if finite_n.size else None,
            "ground_window_px": win,
            "ground_window_m_approx": GROUND_WINDOW_M,
            "dsm_source": str(src_path),
            "mdt_source": str(mdt_path) if mdt_path and method == "mds_minus_mdt" else None,
            "resolution_m_approx": round(res_m, 2),
        }

    meta = load_meta(code) or {"codigo_ibge": code}
    meta["ndsm_file"] = "ndsm.tif"
    meta["ndsm_method"] = method
    meta["ndsm_stats"] = stats
    meta_path(code).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "codigo_ibge": code,
        "status": "ok",
        "path": str(out),
        "stats": stats,
    }


def sample_ndsm_height(codigo_ibge: str, lon: float, lat: float) -> float | None:
    """Amostra nDSM (m) no ponto; gera nDSM sob demanda se necessário."""
    code = str(codigo_ibge).zfill(7)[:7]
    path = ndsm_path(code)
    if not path.exists():
        result = build_ndsm(code)
        if result.get("status") not in {"ok", "cached"}:
            return None
    try:
        import rasterio
    except ImportError:
        return None

    try:
        with rasterio.open(path) as src:
            vals = list(src.sample([(lon, lat)]))
            if not vals:
                return None
            v = float(vals[0][0])
            if v < 0 or not np.isfinite(v):
                return None
            return round(float(np.clip(v, 0, NDSM_MAX_M)), 2)
    except Exception as exc:
        logger.debug("sample_ndsm falhou: %s", exc)
        return None


def refine_building_heights_from_ndsm(
    db: Session,
    codigo_ibge: str,
    *,
    force_rebuild_ndsm: bool = False,
) -> dict[str, Any]:
    """Atualiza altura LOD1 com nDSM quando o valor LiDAR é mais crível que heurística."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    ndsm_info = build_ndsm(code, force=force_rebuild_ndsm)
    if ndsm_info.get("status") not in {"ok", "cached"}:
        return {"codigo_ibge": code, "status": ndsm_info.get("status"), "updated": 0}

    rows = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).all()
    updated = 0
    sampled = 0
    for row in rows:
        if row.geom is None:
            continue
        try:
            gjson = db.scalar(row.geom.ST_AsGeoJSON())
            if not gjson:
                continue
            g = shape(json.loads(gjson))
            c = g.centroid
            lon, lat = float(c.x), float(c.y)
        except Exception:
            continue
        h_ndsm = sample_ndsm_height(code, lon, lat)
        if h_ndsm is None or h_ndsm < NDSM_MIN_BUILDING_M:
            continue
        sampled += 1
        current = float(row.altura_m or 0)
        fonte = (row.fonte_altura or "").lower()
        should = fonte in {"heuristic", "seed"} or (
            fonte == "osm_levels" and h_ndsm > current * 1.35
        )
        if fonte == "osm_height":
            continue
        if should or (fonte.startswith("ndsm") and abs(h_ndsm - current) > 0.5):
            row.altura_m = h_ndsm
            row.fonte_altura = "ndsm_lidar"
            row.qualidade = "Observado"
            row.pavimentos = max(1, int(round(h_ndsm / LEVEL_HEIGHT_M)))
            updated += 1

    if updated:
        db.commit()
    return {
        "codigo_ibge": code,
        "status": "ok",
        "edificios": len(rows),
        "amostrados": sampled,
        "updated": updated,
        "ndsm": ndsm_info,
    }
