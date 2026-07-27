"""Features de duração/intensidade e razão IDF (Fase 21d.1)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def enrich_intensity_features(
    df: pd.DataFrame,
    *,
    codigo_ibge: str | None = None,
) -> pd.DataFrame:
    """Deriva duração, intensidade média/pico e razão vs IDF TR2 a partir do diário.

    Usa `precipitation_hours` (Open-Meteo) quando disponível.
    Pico = proxy de hidrograma triangular (≈ 2 × média).
    """
    out = df.copy()
    precip = out["precipitation_sum"].astype(float).fillna(0.0)
    if "precipitation_hours" in out.columns:
        hours = out["precipitation_hours"].astype(float).fillna(0.0).clip(lower=0.0, upper=24.0)
    else:
        # Sem horas: assume 6 h tipificadas para dias com chuva (hidrograma Sinidu)
        hours = pd.Series(np.where(precip > 0, 6.0, 0.0), index=out.index)

    dur = hours.where(precip > 0, 0.0)
    # Evita divisão por zero: piso 0,5 h em dias chuvosos
    denom = hours.clip(lower=0.5).where(precip > 0, np.nan)
    intens_media = (precip / denom).fillna(0.0)
    intens_pico = (2.0 * precip / denom).fillna(0.0)

    out["duracao_chuva_h"] = dur.round(2)
    out["intensidade_media_mm_h"] = intens_media.clip(upper=300.0).round(3)
    out["intensidade_pico_proxy_mm_h"] = intens_pico.clip(upper=500.0).round(3)

    idf_i = _idf_intensity_mm_h(codigo_ibge, duration_h=1.0)
    out["razao_intensidade_idf_tr2"] = (
        (out["intensidade_pico_proxy_mm_h"] / idf_i).clip(upper=20.0).round(4)
        if idf_i > 0
        else 0.0
    )
    return out


def intensity_from_precip(
    precip_24h: float,
    *,
    duracao_h: float | None = None,
    codigo_ibge: str | None = None,
) -> dict[str, float]:
    """Mesmas features na inferência (alinhado ao treino)."""
    p = max(0.0, float(precip_24h))
    d = float(duracao_h) if duracao_h is not None and duracao_h > 0 else (6.0 if p > 0 else 0.0)
    d = min(24.0, max(0.0, d))
    denom = max(d, 0.5) if p > 0 else 1.0
    media = (p / denom) if p > 0 else 0.0
    pico = (2.0 * p / denom) if p > 0 else 0.0
    idf_i = _idf_intensity_mm_h(codigo_ibge, duration_h=max(d, 1.0))
    razao = (pico / idf_i) if idf_i > 0 else 0.0
    return {
        "duracao_chuva_h": round(d, 2),
        "intensidade_media_mm_h": round(min(media, 300.0), 3),
        "intensidade_pico_proxy_mm_h": round(min(pico, 500.0), 3),
        "razao_intensidade_idf_tr2": round(min(razao, 20.0), 4),
    }


def _idf_intensity_mm_h(codigo_ibge: str | None, *, duration_h: float) -> float:
    if not codigo_ibge:
        return 40.0  # TR2 nacional 60 min (fallback)
    try:
        from app.services.idf_rainfall_service import resolve_idf_precipitacao

        dur_min = int(round(max(0.5, float(duration_h)) * 60.0))
        dur_min = 60 if dur_min < 90 else 120
        resolved = resolve_idf_precipitacao(str(codigo_ibge).zfill(7)[:7], 2, duracao_min=dur_min)
        return float(resolved["intensidade_mm_h"] or 40.0)
    except Exception:
        return 40.0
