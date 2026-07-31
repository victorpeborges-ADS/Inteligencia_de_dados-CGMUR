"""Testes Fase 21f.1 — HistGradientBoosting via model_factory."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier

from ml.constants import FEATURE_COLUMNS, FEATURE_DEFAULTS, ML_ALGORITHM
from ml.model_factory import attach_permutation_importances, fit_classifier, make_classifier
from ml.explainability import domain_contributions


def test_make_classifier_defaults_to_hgb():
    assert ML_ALGORITHM == "hist_gradient_boosting"
    model, name = make_classifier()
    assert name == "hist_gradient_boosting"
    assert isinstance(model, HistGradientBoostingClassifier)


def test_make_classifier_rf_fallback_name():
    model, name = make_classifier("random_forest")
    assert name == "random_forest"
    assert isinstance(model, RandomForestClassifier)


def test_fit_hgb_and_permutation_importances():
    rng = np.random.default_rng(0)
    n = 120
    rows = []
    for i in range(n):
        precip = float(rng.uniform(0, 120))
        label = 1 if precip > 55 and rng.random() > 0.35 else 0
        row = {c: FEATURE_DEFAULTS.get(c, 1.0) for c in FEATURE_COLUMNS}
        row["precip_24h"] = precip
        row["precip_48h"] = precip * 1.3
        row["label"] = label
        rows.append(row)
    df = pd.DataFrame(rows)
    x = df[FEATURE_COLUMNS].astype(float)
    y = df["label"].astype(int)
    if y.nunique() < 2:
        y.iloc[:60] = 1
        y.iloc[60:] = 0

    model, algo = make_classifier("hist_gradient_boosting")
    fit_classifier(model, x, y, algorithm=algo)
    proba = model.predict_proba(x.iloc[:5])
    assert proba.shape[1] == 2

    imp = attach_permutation_importances(model, x, y, n_repeats=2, max_samples=80)
    assert imp is not None
    assert len(imp) == len(FEATURE_COLUMNS)

    expl = domain_contributions(model, FEATURE_COLUMNS, dict(x.iloc[0]))
    assert expl["disponivel"] is True
