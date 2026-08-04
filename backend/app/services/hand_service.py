"""HAND (Height Above Nearest Drainage) a partir do DEM municipal (Fase 21d.2).

Reutiliza fill sinks + acumulação D8 do hydro_simulator.
Inclui vectorização em faixas para camada de mapa (`hand_suscetibilidade`).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Percentil de acumulação que define a rede de drenagem
STREAM_PERCENTILE = 92.0
HAND_LOW_M = 5.0  # fração da área com HAND baixo = suscetível
# Grade da camada mapa (HAND em Python puro é O(n·path) — manter leve)
HAND_MAP_MAX_GRID_DIM = 384
HAND_BANDS = (
    ("muito_baixa", 0.0, 2.0, "HAND < 2 m (muito suscetível)"),
    ("baixa", 2.0, 5.0, "HAND 2–5 m (suscetível)"),
    ("moderada", 5.0, 10.0, "HAND 5–10 m"),
    ("elevada", 10.0, 25.0, "HAND 10–25 m"),
)
HAND_BAND_COLORS = {
    "muito_baixa": "#7f1d1d",
    "baixa": "#ea580c",
    "moderada": "#ca8a04",
    "elevada": "#a3a3a3",
}
MAX_HAND_POLYGONS_PER_BAND = 24
HAND_CACHE_NAME = "hand_bands.geojson"


def compute_hand_raster(
    elevation: np.ndarray,
    mask: np.ndarray,
    *,
    stream_percentile: float = STREAM_PERCENTILE,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Calcula HAND (m) para cada célula da máscara."""
    from app.services.hydro_simulator import D8_OFFSETS, _compute_d8_accumulation, _fill_sinks

    if not mask.any():
        return np.full_like(elevation, np.nan, dtype=np.float64), {"ok": False, "reason": "mask_vazia"}

    filled, fill_meta = _fill_sinks(elevation, mask)
    acc = _compute_d8_accumulation(filled, mask)
    thr = float(np.percentile(acc[mask], stream_percentile))
    stream = mask & (acc >= max(thr, 2.0))

    rows, cols = filled.shape
    # Direção de fluxo D8 (índice em D8_OFFSETS) ou -1
    flow_dir = np.full((rows, cols), -1, dtype=np.int8)
    elev = np.where(mask, np.nan_to_num(filled, nan=float(np.nanmean(filled[mask]))), np.inf)

    for r in range(rows):
        for c in range(cols):
            if not mask[r, c]:
                continue
            cur = elev[r, c]
            best_i = -1
            best_drop = 0.0
            for i, (dr, dc) in enumerate(D8_OFFSETS):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and mask[nr, nc]:
                    drop = cur - elev[nr, nc]
                    if drop > best_drop:
                        best_drop = drop
                        best_i = i
            flow_dir[r, c] = best_i

    hand = np.full((rows, cols), np.nan, dtype=np.float64)
    # Células de drenagem: HAND = 0
    hand[stream] = 0.0

    r_idx, c_idx = np.where(mask & ~stream)
    for r, c in zip(r_idx.tolist(), c_idx.tolist()):
        path_r, path_c = r, c
        visited = 0
        outlet_elev = None
        while visited < rows * cols:
            visited += 1
            if stream[path_r, path_c]:
                outlet_elev = elev[path_r, path_c]
                break
            di = int(flow_dir[path_r, path_c])
            if di < 0:
                break
            dr, dc = D8_OFFSETS[di]
            nr, nc = path_r + dr, path_c + dc
            if not (0 <= nr < rows and 0 <= nc < cols and mask[nr, nc]):
                break
            path_r, path_c = nr, nc
        if outlet_elev is not None:
            hand[r, c] = max(0.0, float(elev[r, c] - outlet_elev))
        else:
            # Sem exutório: usa diferença para o mínimo local da máscara (conservador)
            hand[r, c] = max(0.0, float(elev[r, c] - float(np.nanmin(elev[mask]))))

    vals = hand[mask & np.isfinite(hand)]
    meta = {
        "ok": True,
        "stream_percentile": stream_percentile,
        "stream_threshold_acc": thr,
        "stream_cells": int(stream.sum()),
        "hand_mean_m": round(float(np.nanmean(vals)), 3) if len(vals) else None,
        "hand_median_m": round(float(np.nanmedian(vals)), 3) if len(vals) else None,
        "pct_hand_lt_5m": (
            round(float(100.0 * np.mean(vals < HAND_LOW_M)), 2) if len(vals) else None
        ),
        "fill": fill_meta,
    }
    return hand, meta


def municipal_hand_features(db: Session, codigo_ibge: str) -> dict[str, float]:
    """Agrega HAND/TWI e suscetibilidade para features ML municipais (21d.2/21d.5)."""
    from app.models import Municipio
    from app.services.hydro_simulator import (
        _downsample_elevation_grid,
        _hydro_grid_limit_for,
        _load_elevation_grid,
        _muni_raster_mask,
    )
    from ml.susceptibility import compute_twi_mean, suscetibilidade_from_hand

    defaults = {
        "hand_media_m": 12.0,
        "pct_hand_lt_5m": 15.0,
        "twi_media": 8.0,
        "suscetibilidade_hand": 0.35,
    }
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return defaults

    loaded = _load_elevation_grid(db, code, muni)
    if loaded is None:
        logger.info("HAND %s: DEM indisponível — defaults", code)
        return defaults

    elev, west, south, res_x, res_y, meta = loaded
    grid_limit = _hydro_grid_limit_for(meta, elev, res_x, res_y, south)
    elev, west, south, res_x, res_y = _downsample_elevation_grid(
        elev, west, south, res_x, res_y, max_dim=grid_limit,
    )
    try:
        import json
        from shapely.geometry import shape

        muni_geom = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
        mask = _muni_raster_mask(elev, muni_geom, west, south, res_x, res_y)
    except Exception as exc:
        logger.warning("HAND mask %s: %s", code, exc)
        return defaults

    _hand, meta = compute_hand_raster(elev, mask)
    if not meta.get("ok"):
        return defaults

    hand_m = float(meta.get("hand_mean_m") or defaults["hand_media_m"])
    pct_low = float(meta.get("pct_hand_lt_5m") or defaults["pct_hand_lt_5m"])
    try:
        cell_m2 = abs(float(res_x) * 111_320.0) * abs(float(res_y) * 111_320.0)
        twi = compute_twi_mean(elev, mask, cell_area_m2=max(cell_m2, 100.0))
    except Exception as exc:
        logger.info("TWI %s: %s — default", code, exc)
        twi = defaults["twi_media"]

    return {
        "hand_media_m": hand_m,
        "pct_hand_lt_5m": pct_low,
        "twi_media": float(twi),
        "suscetibilidade_hand": suscetibilidade_from_hand(hand_m, pct_low, twi_media=twi),
    }


def build_hand_bands_geojson(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """GeoJSON de faixas HAND para o LayerPanel (`hand_suscetibilidade`).

    Usa grade limitada + cache em disco no diretório DEM municipal.
    """
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    from app.models import Municipio
    from app.services.dem_processor import dem_dir
    from app.services.hydro_simulator import (
        MIN_FLOOD_POLYGON_AREA_DEG2,
        _downsample_elevation_grid,
        _load_elevation_grid,
        _muni_raster_mask,
        _vectorize_band,
    )

    empty: dict[str, Any] = {"type": "FeatureCollection", "features": []}
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return empty

    cache_path = dem_dir(code) / HAND_CACHE_NAME
    if not force and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("type") == "FeatureCollection":
                return cached
        except Exception as exc:
            logger.info("HAND cache inválido %s: %s", code, exc)

    loaded = _load_elevation_grid(db, code, muni)
    if loaded is None:
        return empty

    elev, west, south, res_x, res_y, _meta = loaded
    elev, west, south, res_x, res_y = _downsample_elevation_grid(
        elev, west, south, res_x, res_y, max_dim=HAND_MAP_MAX_GRID_DIM,
    )
    try:
        muni_geom = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
        mask = _muni_raster_mask(elev, muni_geom, west, south, res_x, res_y)
    except Exception as exc:
        logger.warning("HAND bands mask %s: %s", code, exc)
        return empty

    hand, hmeta = compute_hand_raster(elev, mask)
    if not hmeta.get("ok"):
        return empty

    # _vectorize_band usa (depth >= lo) & (depth < hi) — HAND funciona igual
    features: list[dict[str, Any]] = []
    for band_id, lo, hi, label in HAND_BANDS:
        try:
            shapes = _vectorize_band(hand, lo, hi, mask, west, south, res_x, res_y)
        except RuntimeError as exc:
            if "rasterio" in str(exc).lower() or "rasterio_required" in str(exc):
                logger.warning("HAND bands sem rasterio: %s", exc)
                return empty
            raise
        except Exception as exc:
            logger.warning("HAND vectorize %s %s: %s", code, band_id, exc)
            continue

        # Simplifica / funde e corta por município
        polys = []
        for g in shapes:
            try:
                g2 = g.intersection(muni_geom)
                if g2.is_empty:
                    continue
                if g2.geom_type == "Polygon":
                    polys.append(g2)
                elif g2.geom_type == "MultiPolygon":
                    polys.extend(list(g2.geoms))
            except Exception:
                continue
        if not polys:
            continue
        try:
            merged = unary_union(polys)
        except Exception:
            merged = polys[0]
        parts = list(merged.geoms) if merged.geom_type == "MultiPolygon" else [merged]
        parts = sorted(
            [p for p in parts if p.geom_type == "Polygon" and p.area >= MIN_FLOOD_POLYGON_AREA_DEG2],
            key=lambda p: p.area,
            reverse=True,
        )[:MAX_HAND_POLYGONS_PER_BAND]
        for poly in parts:
            features.append({
                "type": "Feature",
                "geometry": mapping(poly),
                "properties": {
                    "layer_type": "hand_band",
                    "hand_band": band_id,
                    "hand_min_m": lo,
                    "hand_max_m": hi if hi < 100 else None,
                    "label": label,
                    "fill_color": HAND_BAND_COLORS.get(band_id, "#a3a3a3"),
                    "fonte_referencia": "HAND derivado do DEM municipal (D8)",
                    "qualidade_dado": "Derivado Sinidu+Clima",
                    "hand_mean_m": hmeta.get("hand_mean_m"),
                    "pct_hand_lt_5m": hmeta.get("pct_hand_lt_5m"),
                },
            })

    fc: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "codigo_ibge": code,
            "method": "hand_d8",
            "hand_mean_m": hmeta.get("hand_mean_m"),
            "pct_hand_lt_5m": hmeta.get("pct_hand_lt_5m"),
            "grid_max_dim": HAND_MAP_MAX_GRID_DIM,
        },
    }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(fc), encoding="utf-8")
    except Exception as exc:
        logger.info("HAND cache write %s: %s", code, exc)
    return fc
