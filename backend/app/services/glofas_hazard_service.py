"""Hazard de referência JRC GloFAS (RP100) — camada de validação aberta.

Baixa o tile 10°×10° que cobre o município (~4 MB), recorta ao perímetro
e vectoriza faixas de profundidade. Uso: comparar com a mancha Sinidu.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import requests
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

TILE_EXTENTS_URL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard/tile_extents.geojson"
)
TILE_URL_TMPL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard/"
    "RP100/ID{id}_{name}_RP100_depth.tif"
)
CACHE_FC = "glofas_rp100_bands.geojson"
BANDS = (
    ("leve", 0.05, 0.50, "GloFAS RP100 5–50 cm"),
    ("moderada", 0.50, 1.50, "GloFAS RP100 50–150 cm"),
    ("profunda", 1.50, 999.0, "GloFAS RP100 > 150 cm"),
)
BAND_COLORS = {
    "leve": "#93c5fd",
    "moderada": "#2563eb",
    "profunda": "#1e3a8a",
}
MAX_POLYS = 20
MIN_AREA = 1.5e-8


def _glofas_dir() -> Path:
    root = Path(__file__).resolve().parents[2] / "data" / "glofas"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _muni_cache(codigo_ibge: str) -> Path:
    from app.services.dem_processor import dem_dir

    return dem_dir(str(codigo_ibge).zfill(7)[:7]) / CACHE_FC


def _load_tile_index() -> list[dict[str, Any]]:
    path = _glofas_dir() / "tile_extents.geojson"
    if not path.exists():
        resp = requests.get(TILE_EXTENTS_URL, timeout=60, headers={"User-Agent": "SiniduClima/1.0"})
        resp.raise_for_status()
        path.write_bytes(resp.content)
    fc = json.loads(path.read_text(encoding="utf-8"))
    return fc.get("features") or []


def _find_tile(lon: float, lat: float) -> tuple[int, str] | None:
    from shapely.geometry import Point

    pt = Point(lon, lat)
    for feat in _load_tile_index():
        props = feat.get("properties") or {}
        try:
            g = shape(feat["geometry"])
        except Exception:
            continue
        if g.contains(pt) or g.intersects(pt.buffer(0.05)):
            tid = props.get("id")
            name = props.get("name")
            if tid is not None and name:
                return int(tid), str(name)
    return None


def _ensure_tile(tile_id: int, name: str) -> Path:
    dest = _glofas_dir() / f"ID{tile_id}_{name}_RP100_depth.tif"
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    url = TILE_URL_TMPL.format(id=tile_id, name=name)
    logger.info("Baixando GloFAS tile %s", url)
    resp = requests.get(url, timeout=180, headers={"User-Agent": "SiniduClima/1.0"})
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def build_glofas_rp100_geojson(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """FeatureCollection de faixas GloFAS RP100 no município."""
    import rasterio
    from rasterio.features import shapes as rio_shapes
    from rasterio.mask import mask as rio_mask

    from app.models import Municipio

    empty: dict[str, Any] = {"type": "FeatureCollection", "features": []}
    code = str(codigo_ibge).zfill(7)[:7]
    cache = _muni_cache(code)
    if not force and cache.exists():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if cached.get("type") == "FeatureCollection":
                return cached
        except Exception:
            pass

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni or muni.geom is None:
        return empty

    try:
        muni_geom = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
        lon, lat = float(muni_geom.centroid.x), float(muni_geom.centroid.y)
    except Exception as exc:
        logger.warning("GloFAS geom %s: %s", code, exc)
        return empty

    tile = _find_tile(lon, lat)
    if not tile:
        logger.warning("GloFAS: sem tile para %s (%.3f, %.3f)", code, lon, lat)
        return empty
    tile_id, tile_name = tile

    try:
        tif = _ensure_tile(tile_id, tile_name)
    except Exception as exc:
        logger.warning("GloFAS download %s: %s", code, exc)
        return empty

    features: list[dict[str, Any]] = []
    try:
        with rasterio.open(tif) as src:
            geoms = [mapping(muni_geom)]
            try:
                data, transform = rio_mask(src, geoms, crop=True, filled=True, nodata=0)
            except ValueError:
                # município fora do raster (borda) — tenta envelope
                data, transform = rio_mask(src, geoms, crop=True, all_touched=True, filled=True, nodata=0)
            arr = data[0].astype(np.float64)
            # nodata / zeros
            nodata = src.nodata
            if nodata is not None:
                arr = np.where(arr == nodata, 0.0, arr)
            arr = np.where(arr < 0, 0.0, arr)

        for band_id, lo, hi, label in BANDS:
            mask = (arr >= lo) & (arr < hi)
            if not mask.any():
                continue
            polys = []
            for geom, val in rio_shapes(mask.astype(np.uint8), mask=mask, transform=transform):
                if int(val) != 1:
                    continue
                try:
                    g = shape(geom).intersection(muni_geom)
                except Exception:
                    continue
                if g.is_empty:
                    continue
                if g.geom_type == "Polygon":
                    polys.append(g)
                elif g.geom_type == "MultiPolygon":
                    polys.extend(list(g.geoms))
            if not polys:
                continue
            try:
                merged = unary_union(polys)
            except Exception:
                merged = polys[0]
            parts = list(merged.geoms) if merged.geom_type == "MultiPolygon" else [merged]
            parts = sorted(
                [p for p in parts if p.geom_type == "Polygon" and p.area >= MIN_AREA],
                key=lambda p: p.area,
                reverse=True,
            )[:MAX_POLYS]
            for poly in parts:
                features.append({
                    "type": "Feature",
                    "geometry": mapping(poly),
                    "properties": {
                        "layer_type": "glofas_hazard",
                        "hazard_band": band_id,
                        "depth_min_m": lo,
                        "depth_max_m": None if hi >= 100 else hi,
                        "label": label,
                        "fill_color": BAND_COLORS.get(band_id, "#2563eb"),
                        "return_period_years": 100,
                        "fonte_referencia": "JRC CEMS-GloFAS Flood Hazard RP100",
                        "qualidade_dado": "Referencia",
                        "tile": f"ID{tile_id}_{tile_name}",
                    },
                })
    except Exception as exc:
        logger.warning("GloFAS vectorize %s: %s", code, exc)
        return empty

    fc = {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "codigo_ibge": code,
            "source": "jrc_glofas_rp100",
            "tile": f"ID{tile_id}_{tile_name}",
            "n_features": len(features),
        },
    }
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(fc), encoding="utf-8")
    except Exception as exc:
        logger.info("GloFAS cache write %s: %s", code, exc)
    return fc
