"""Fábrica de classificadores ML de alagamento (Fase 21f.1).

Preferência: HistGradientBoosting (sklearn, CPU-friendly, bom em tabular
desbalanceado). Fallback: Random Forest.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.utils.class_weight import compute_sample_weight

from ml.constants import HGB_PARAMS, ML_ALGORITHM, RF_PARAMS


def make_classifier(algorithm: str | None = None) -> tuple[Any, str]:
    """Retorna (estimator não treinado, nome do algoritmo)."""
    algo = (algorithm or ML_ALGORITHM).strip().lower()
    if algo in {"hgb", "hist_gradient_boosting", "histgradientboosting", "boosting"}:
        return HistGradientBoostingClassifier(**HGB_PARAMS), "hist_gradient_boosting"
    return RandomForestClassifier(**RF_PARAMS), "random_forest"


def fit_classifier(
    model: Any,
    x,
    y,
    *,
    algorithm: str | None = None,
) -> Any:
    """Fit com sample_weight balanceado quando o algoritmo não tem class_weight."""
    algo = algorithm or ""
    name = algo or type(model).__name__.lower()
    if "histgradient" in name or "hist_gradient" in str(algorithm or ""):
        sw = compute_sample_weight("balanced", y)
        model.fit(x, y, sample_weight=sw)
    else:
        model.fit(x, y)
    return model


def attach_permutation_importances(
    model: Any,
    x,
    y,
    *,
    n_repeats: int = 4,
    max_samples: int = 400,
) -> np.ndarray | None:
    """Anexa `_sinidu_feature_importances_` (útil para HGB sem importances nativas)."""
    try:
        from sklearn.inspection import permutation_importance
    except Exception:
        return None
    if len(y) < 20 or getattr(y, "nunique", lambda: 2)() < 2:
        return None
    try:
        n = len(x)
        if n > max_samples:
            rng = np.random.default_rng(42)
            idx = rng.choice(n, size=max_samples, replace=False)
            if hasattr(x, "iloc"):
                xs, ys = x.iloc[idx], y.iloc[idx]
            else:
                xs, ys = x[idx], y[idx]
        else:
            xs, ys = x, y
        result = permutation_importance(
            model,
            xs,
            ys,
            n_repeats=n_repeats,
            random_state=42,
            scoring="roc_auc",
            n_jobs=1,
        )
        imp = np.asarray(result.importances_mean, dtype=float)
        # Importância relativa não-negativa
        imp = np.maximum(imp, 0.0)
        if float(imp.sum()) <= 0:
            return None
        setattr(model, "_sinidu_feature_importances_", imp)
        return imp
    except Exception:
        return None
