"""HAND (Height Above Nearest Drainage) a partir do DEM municipal (Fase 21d.2).

Reutiliza fill sinks + acumulação D8 do hydro_simulator.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Percentil de acumulação que define a rede de drenagem
STREAM_PERCENTILE = 92.0
HAND_LOW_M = 5.0  # fração da área com HAND baixo = suscetível


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

    elev, west, south, res_x, res_y, _meta = loaded
    elev, west, south, res_x, res_y = _downsample_elevation_grid(elev, west, south, res_x, res_y)
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
