"""Testes Fase 21f.3 / 21f.4 — horizonte e incerteza."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from ml.constants import FEATURE_COLUMNS, FEATURE_DEFAULTS
from ml.horizon import (
    build_horizon_forecasts,
    precip_windows_for_horizon,
    predict_proba_with_uncertainty,
)


def test_precip_windows_split_by_horizon():
    w1 = precip_windows_for_horizon(40, 70, 100, horizon_d=1)
    w2 = precip_windows_for_horizon(40, 70, 100, horizon_d=2)
    w3 = precip_windows_for_horizon(40, 70, 100, horizon_d=3)
    assert w1["precip_24h"] == 40.0
    assert w2["precip_24h"] == 30.0  # 70-40
    assert w3["precip_24h"] == 30.0  # 100-70


def test_uncertainty_from_rf_trees():
    rng = np.random.default_rng(1)
    n = 60
    x = np.column_stack([rng.random(n) for _ in FEATURE_COLUMNS])
    y = (x[:, 0] > 0.5).astype(int)
    clf = RandomForestClassifier(n_estimators=30, max_depth=4, random_state=1)
    clf.fit(x, y)
    vec = np.array([[FEATURE_DEFAULTS.get(c, 0.5) for c in FEATURE_COLUMNS]])
    unc = predict_proba_with_uncertainty(clf, vec)
    assert 0.0 <= unc["ci_low"] <= unc["probability"] <= unc["ci_high"] <= 1.0
    assert unc["method"] == "rf_tree_dispersion"
    assert unc["confidence_level"] == 0.9


def test_horizon_forecasts_three_days():
    rng = np.random.default_rng(2)
    n = 50
    x = np.column_stack([rng.random(n) for _ in FEATURE_COLUMNS])
    y = (x[:, 0] + x[:, 1] > 1).astype(int)
    if y.sum() < 2:
        y[:25] = 1
        y[25:] = 0
    clf = RandomForestClassifier(n_estimators=20, max_depth=3, random_state=2)
    clf.fit(x, y)
    row = {c: FEATURE_DEFAULTS.get(c, 1.0) for c in FEATURE_COLUMNS}
    horizons = build_horizon_forecasts(
        clf,
        FEATURE_COLUMNS,
        row,
        precip_24h=50,
        precip_48h=90,
        precip_72h=120,
        codigo_ibge="2611606",
    )
    assert [h["horizon"] for h in horizons] == ["D+1", "D+2", "D+3"]
    assert all("ci_low" in h and "ci_high" in h for h in horizons)
