"""Suscetibilidade a inundação derivada de HAND/TWI (Fase 21d.5).

Sem carta CPRM: proxy físico a partir do DEM (HAND + TWI) e, por bairro,
impermeabilização + proximidade à água + declividade.
"""

from __future__ import annotations

import numpy as np


def suscetibilidade_from_hand(
    hand_media_m: float,
    pct_hand_lt_5m: float,
    *,
    twi_media: float | None = None,
) -> float:
    """Score 0–1: HAND baixo e área ampla com HAND < 5 m → maior risco."""
    hand = max(0.0, float(hand_media_m))
    pct_low = min(100.0, max(0.0, float(pct_hand_lt_5m))) / 100.0
    # HAND médio: 0 m → 1.0; ≥ 25 m → 0.0
    hand_comp = max(0.0, 1.0 - hand / 25.0)
    score = 0.55 * pct_low + 0.35 * hand_comp
    if twi_media is not None:
        # TWI típico urbano ~4–12; normaliza em torno de 6–14
        twi_n = min(1.0, max(0.0, (float(twi_media) - 4.0) / 10.0))
        score = 0.85 * score + 0.15 * twi_n
    return round(min(1.0, max(0.0, score)), 4)


def bairro_suscetibilidade(
    impermeabilizacao_pct: float,
    water_proximity: float,
    declividade_media: float,
    *,
    hand_media_m: float = 12.0,
    pct_hand_lt_5m: float = 15.0,
) -> float:
    """Suscetibilidade local 0–1 (proxy até haver HAND por polígono)."""
    imperm = min(1.0, max(0.0, float(impermeabilizacao_pct) / 100.0))
    water = min(1.0, max(0.0, float(water_proximity)))
    # Declividade baixa favorece alagamento pluvial
    slope = float(declividade_media)
    slope_comp = max(0.0, 1.0 - min(slope, 12.0) / 12.0)
    hand_score = suscetibilidade_from_hand(hand_media_m, pct_hand_lt_5m)
    score = 0.30 * imperm + 0.25 * water + 0.15 * slope_comp + 0.30 * hand_score
    return round(min(1.0, max(0.0, score)), 4)


def compute_twi_mean(
    elevation: np.ndarray,
    mask: np.ndarray,
    *,
    cell_area_m2: float = 900.0,
) -> float:
    """TWI médio = ln(a / tan β) com acumulação D8 (área contribuinte)."""
    from app.services.hydro_simulator import _compute_d8_accumulation, _fill_sinks

    if not mask.any():
        return 8.0

    filled, _ = _fill_sinks(elevation, mask)
    acc = _compute_d8_accumulation(filled, mask)
    elev = np.where(mask, np.nan_to_num(filled, nan=float(np.nanmean(filled[mask]))), np.nan)
    dz_dy, dz_dx = np.gradient(np.nan_to_num(elev, nan=0.0))
    slope = np.sqrt(dz_dx**2 + dz_dy**2)
    # Aproxima tan(β) com gradiente em células; piso evita log infinito
    tan_b = np.maximum(slope, 1e-4)
    area = np.maximum(acc.astype(np.float64) * float(cell_area_m2), cell_area_m2)
    twi = np.full_like(elev, np.nan, dtype=np.float64)
    twi[mask] = np.log(area[mask] / tan_b[mask])
    vals = twi[mask & np.isfinite(twi)]
    if len(vals) == 0:
        return 8.0
    return round(float(np.nanmean(vals)), 3)
