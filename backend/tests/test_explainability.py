"""Testes Fase 21g.3 — explicabilidade por domínio."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from ml.constants import FEATURE_COLUMNS, FEATURE_DEFAULTS
from ml.explainability import domain_contributions


def test_domain_contributions_sums_and_labels():
    rng = np.random.default_rng(0)
    n = 80
    x = np.column_stack([rng.random(n) for _ in FEATURE_COLUMNS])
    y = (x[:, 0] + x[:, 1] > 1.0).astype(int)
    if y.sum() < 2:
        y[:40] = 1
        y[40:] = 0
    clf = RandomForestClassifier(n_estimators=20, max_depth=4, random_state=0)
    clf.fit(x, y)

    row = {c: FEATURE_DEFAULTS.get(c, 1.0) for c in FEATURE_COLUMNS}
    row["precip_24h"] = 90.0
    row["hand_media_m"] = 3.0
    out = domain_contributions(clf, FEATURE_COLUMNS, row)

    assert out["disponivel"] is True
    assert out["method"] == "rf_importance_by_domain"
    ids = {d["id"] for d in out["domains"]}
    assert "chuva" in ids
    assert "hand_hidrografia" in ids
    assert "drenagem" in ids
    assert "solo_uso" in ids
    pct = sum(d["contribution_pct"] for d in out["domains"])
    assert 99.0 <= pct <= 101.0
    assert out["narrativa"]
    assert len(out["top_features"]) >= 1


def test_domain_contributions_without_importances():
    class Dummy:
        pass

    out = domain_contributions(Dummy(), FEATURE_COLUMNS, None)
    assert out["disponivel"] is False
