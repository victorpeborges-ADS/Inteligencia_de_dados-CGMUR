import pickle
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from ml.constants import FEATURE_COLUMNS, MUNICIPALITY_SLUGS
from ml.predictor import FloodRiskPredictor, resolve_codigo_ibge
from ml.train import _find_threshold_mm, _temporal_cv_auc


def test_resolve_codigo_ibge_slug():
    assert resolve_codigo_ibge("recife") == "2611606"
    assert resolve_codigo_ibge("2611606") == "2611606"


def test_resolve_codigo_ibge_invalid():
    with pytest.raises(ValueError):
        resolve_codigo_ibge("cidade_inexistente")


def test_temporal_cv_auc_synthetic():
    rng = np.random.default_rng(42)
    n = 200
    x = pd.DataFrame({col: rng.random(n) for col in FEATURE_COLUMNS})
    y = pd.Series((x["precip_24h"] > 0.6).astype(int))
    auc = _temporal_cv_auc(x, y, n_splits=3)
    assert auc > 0.5


def test_find_threshold_mm():
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    x = pd.DataFrame({
        "precip_24h": [10, 30, 60, 90, 120],
        "precip_48h": [15, 45, 90, 130, 170],
        "precip_72h": [20, 60, 110, 160, 210],
        "precip_7d": [40, 100, 180, 260, 340],
        "mes_do_ano": [3, 3, 4, 4, 5],
        "impermeabilizacao_pct": [50] * 5,
        "cobertura_vegetal_pct": [15] * 5,
        "declividade_media": [3] * 5,
    })
    y = pd.Series([0, 0, 1, 1, 1])
    model.fit(x, y)
    terrain = {"impermeabilizacao_pct": 50.0, "cobertura_vegetal_pct": 15.0, "declividade_media": 3.0}
    threshold = _find_threshold_mm(model, terrain)
    assert 10 <= threshold <= 200


@patch("ml.predictor.model_path")
def test_predictor_with_mock_model(mock_path, tmp_path):
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    x = pd.DataFrame({col: [1.0, 0.2, 0.8, 0.3, 0.9] for col in FEATURE_COLUMNS})
    y = pd.Series([0, 1, 1, 0, 1])
    model.fit(x, y)

    meta = {
        "codigo_ibge": "2611606",
        "model_version": "1.0",
        "auc_roc_cv": 0.8,
        "n_positive": 3,
        "threshold_mm_24h": 65.0,
        "terrain": {
            "impermeabilizacao_pct": 45.0,
            "cobertura_vegetal_pct": 12.0,
            "declividade_media": 3.5,
        },
    }
    pkl = tmp_path / "model.pkl"
    with pkl.open("wb") as fh:
        pickle.dump({"model": model, "meta": meta}, fh)
    mock_path.return_value = pkl

    db = MagicMock()
    predictor = FloodRiskPredictor()
    with patch.object(predictor, "_critical_neighborhoods", return_value=[]):
        with patch.object(predictor, "_flood_patch_geojson", return_value={"type": "FeatureCollection", "features": []}):
            result = predictor.predict(db, "recife", 80, 120, 150)
    assert 0 <= result["risk_probability"] <= 1
    assert result["risk_level"] in {"BAIXO", "MEDIO", "ALTO", "MUITO_ALTO"}
    assert "disclaimer" in result


def test_municipality_slugs_count():
    assert len(MUNICIPALITY_SLUGS) == 5
