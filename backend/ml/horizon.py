"""Horizonte D+1..D+3 e intervalo de incerteza (Fase 21f.3 / 21f.4).

Sem retreinar: deriva janelas de chuva do acumulado 24/48/72h e estima
dispersão via árvores do Random Forest (ou fallback ± margem heurística).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ml.constants import FEATURE_DEFAULTS


def precip_windows_for_horizon(
    precip_24h: float,
    precip_48h: float,
    precip_72h: float,
    *,
    horizon_d: int,
) -> dict[str, float]:
    """Janelas de precipitação relativas ao dia-alvo (D+h).

    D+1: próximas 24h (cenário base).
    D+2: chuva do 2º dia ≈ max(0, 48h−24h).
    D+3: chuva do 3º dia ≈ max(0, 72h−48h).
    """
    p24 = max(0.0, float(precip_24h))
    p48 = max(0.0, float(precip_48h))
    p72 = max(0.0, float(precip_72h))
    h = int(horizon_d)

    if h <= 1:
        day = p24
        win48 = p48
        win72 = p72
    elif h == 2:
        day = max(0.0, p48 - p24)
        win48 = max(day, p72 - p24)
        win72 = max(win48, p72)
    else:
        day = max(0.0, p72 - p48)
        win48 = day + max(0.0, p48 - p24)  # D+2 + D+3 aprox.
        win72 = max(win48, p72)

    return {
        "precip_24h": round(day, 2),
        "precip_48h": round(win48, 2),
        "precip_72h": round(win72, 2),
        "horizon_d": float(h),
    }


def _base_estimator(model: Any) -> Any:
    """RF direto ou base de CalibratedClassifierCV."""
    if hasattr(model, "estimators_") and hasattr(model, "predict_proba"):
        return model
    cals = getattr(model, "calibrated_classifiers_", None)
    if cals:
        est = getattr(cals[0], "estimator", None) or getattr(cals[0], "base_estimator", None)
        if est is not None:
            return est
    est = getattr(model, "estimator", None)
    return est if est is not None else model


def predict_proba_with_uncertainty(
    model: Any,
    vec: np.ndarray,
    *,
    z: float = 1.64,
) -> dict[str, Any]:
    """Probabilidade média + intervalo aproximado 90% (z≈1.64).

    Preferência: dispersão entre árvores do RF.
    Fallback: margem ±0.08 em torno da proba do modelo.
    """
    mean_p = float(model.predict_proba(vec)[0][1])
    base = _base_estimator(model)
    estimators = getattr(base, "estimators_", None)
    method = "heuristic_margin"
    std = 0.08

    if estimators:
        probs = []
        for tree in estimators:
            try:
                proba = tree.predict_proba(vec)
                # Árvore isolada pode ter 1 coluna se só viu uma classe no bootstrap
                if proba.shape[1] >= 2:
                    probs.append(float(proba[0][1]))
                else:
                    probs.append(float(proba[0][0]))
            except Exception:
                continue
        if len(probs) >= 5:
            arr = np.asarray(probs, dtype=float)
            mean_p = float(np.mean(arr))
            std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.05
            method = "rf_tree_dispersion"

    lo = max(0.0, mean_p - z * std)
    hi = min(1.0, mean_p + z * std)
    # Garante intervalo mínimo visível
    if hi - lo < 0.04:
        mid = (lo + hi) / 2.0
        lo = max(0.0, mid - 0.02)
        hi = min(1.0, mid + 0.02)

    return {
        "probability": round(mean_p, 4),
        "ci_low": round(lo, 4),
        "ci_high": round(hi, 4),
        "std": round(std, 4),
        "method": method,
        "confidence_level": 0.90,
    }


def build_horizon_forecasts(
    model: Any,
    cols: list[str],
    base_row: dict[str, float],
    *,
    precip_24h: float,
    precip_48h: float,
    precip_72h: float,
    codigo_ibge: str | None = None,
    duracao_chuva_h: float | None = None,
) -> list[dict[str, Any]]:
    """Gera D+1, D+2, D+3 com incerteza."""
    from ml.intensity import intensity_from_precip

    out: list[dict[str, Any]] = []
    for h in (1, 2, 3):
        wins = precip_windows_for_horizon(precip_24h, precip_48h, precip_72h, horizon_d=h)
        intensity = intensity_from_precip(
            wins["precip_24h"],
            duracao_h=duracao_chuva_h,
            codigo_ibge=codigo_ibge,
        )
        row = {**base_row, **wins, **intensity}
        vec = np.array([[float(row.get(c, FEATURE_DEFAULTS.get(c, 0.0))) for c in cols]])
        unc = predict_proba_with_uncertainty(model, vec)
        p = unc["probability"]
        out.append({
            "horizon": f"D+{h}",
            "horizon_d": h,
            "risk_probability": round(p, 3),
            "ci_low": unc["ci_low"],
            "ci_high": unc["ci_high"],
            "precip_24h_mm": wins["precip_24h"],
            "uncertainty_method": unc["method"],
        })
    return out
