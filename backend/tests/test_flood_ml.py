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
    assert resolve_codigo_ibge("aracaju") == "2800308"
    assert resolve_codigo_ibge("sao_paulo") == "3550308"


def test_ml_targets_piloto():
    from ml.baseline import TERRAIN_PRESETS
    from ml.constants import ML_TARGET_IBGE_CODES, SLUG_BY_IBGE

    assert len(ML_TARGET_IBGE_CODES) == 8
    assert "2800308" in ML_TARGET_IBGE_CODES
    assert "3550308" in ML_TARGET_IBGE_CODES
    assert set(ML_TARGET_IBGE_CODES) <= set(SLUG_BY_IBGE)
    assert set(ML_TARGET_IBGE_CODES) <= set(TERRAIN_PRESETS)


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
    from ml.constants import FEATURE_DEFAULTS

    model = RandomForestClassifier(n_estimators=10, random_state=42)
    n = 5
    base = {
        "precip_24h": [10, 30, 60, 90, 120],
        "precip_48h": [15, 45, 90, 130, 170],
        "precip_72h": [20, 60, 110, 160, 210],
        "precip_7d": [40, 100, 180, 260, 340],
        "mes_do_ano": [3, 3, 4, 4, 5],
        "impermeabilizacao_pct": [50] * n,
        "cobertura_vegetal_pct": [15] * n,
        "declividade_media": [3] * n,
    }
    for col in FEATURE_COLUMNS:
        if col not in base:
            base[col] = [FEATURE_DEFAULTS.get(col, 0.0)] * n
    x = pd.DataFrame(base)[FEATURE_COLUMNS]
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
        "model_kind": "full",
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
            result = predictor.predict(db, "recife", 80, 120, 150, precip_7d=280)
    assert 0 <= result["risk_probability"] <= 1
    assert result["risk_level"] in {"BAIXO", "MEDIO", "ALTO", "MUITO_ALTO"}
    assert "disclaimer" in result
    assert result["mm_acima_limiar"] == round(80 - 65.0, 1)
    assert isinstance(result["top_features"], list)
    assert len(result["top_features"]) >= 3
    assert "feature" in result["top_features"][0]
    assert result.get("explanation", {}).get("disponivel") is True
    assert result["features_used"]["precip_7d"] == 280
    assert result["production_ready"] is True
    assert result["model_auc_roc"] == 0.8


@patch("ml.predictor.model_path")
def test_predictor_hides_auc_for_synthetic(mock_path, tmp_path):
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    x = pd.DataFrame({col: [1.0, 0.2, 0.8, 0.3, 0.9] for col in FEATURE_COLUMNS})
    y = pd.Series([0, 1, 1, 0, 1])
    model.fit(x, y)
    meta = {
        "model_kind": "baseline_synthetic",
        "model_version": "1.0",
        "auc_roc_cv": 0.99,
        "n_positive": 800,
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

    predictor = FloodRiskPredictor()
    with patch.object(predictor, "_critical_neighborhoods", return_value=[]):
        with patch.object(predictor, "_flood_patch_geojson", return_value={"type": "FeatureCollection", "features": []}):
            result = predictor.predict(MagicMock(), "recife", 80, 120, 150, precip_7d=200)
    assert result["model_auc_roc"] is None
    assert result["confidence"] == "nao_producao"
    assert result["score_kind"] == "score_sintetico"
    assert result["production_ready"] is False


def test_municipality_slugs_count():
    assert len(MUNICIPALITY_SLUGS) == 8
    assert MUNICIPALITY_SLUGS["aracaju"] == "2800308"


def test_resolve_risk_probability_blocks_synthetic():
    from app.services.weather_monitor import _risk_probability, resolve_risk_probability

    db = MagicMock()
    with patch("ml.paths.model_path") as mock_path, patch(
        "ml.model_policy.production_model_ready", return_value=False
    ):
        mock_path.return_value.exists.return_value = True
        risk, source = resolve_risk_probability(db, "2611606", 90.0, 140.0, precip_48h=110.0, precip_7d=200.0)
        assert source == "precip_curve"
        assert risk == _risk_probability(90.0)


def test_resolve_risk_probability_ml_full():
    from app.services.weather_monitor import resolve_risk_probability

    db = MagicMock()
    with patch("ml.paths.model_path") as mock_path, patch(
        "ml.model_policy.production_model_ready", return_value=True
    ), patch(
        "ml.predictor.predictor.predict",
        return_value={"risk_probability": 0.66, "model_kind": "full", "production_ready": True},
    ):
        mock_path.return_value.exists.return_value = True
        risk, source = resolve_risk_probability(
            db, "2611606", 90.0, 140.0, precip_48h=110.0, precip_7d=200.0
        )
        assert source == "ml_full"
        assert risk == 0.66


def test_precip_windows_aligns_past_and_forecast():
    from app.services.weather_monitor import _precip_windows

    # 30d past (720h) + 72h forecast — alinhado a past_days=30
    past = [1.0] * (30 * 24)
    forecast = [2.0] * 72
    data = {"hourly": {"precipitation": past + forecast, "time": ["t"] * (720 + 72)}}
    w = _precip_windows(data)
    assert w["precip_24h"] == 48.0  # 24 * 2
    assert w["precip_48h"] == 96.0
    assert w["precip_72h"] == 144.0
    assert w["precip_5d"] == 120.0  # 5*24 * 1
    assert w["precip_7d"] == 168.0  # 7*24 * 1
    assert w["precip_10d"] == 240.0
    assert w["precip_30d"] == 720.0


def test_label_lag_constants():
    from ml.constants import LABEL_LAG_AFTER_DAYS, LABEL_LAG_BEFORE_DAYS

    assert LABEL_LAG_BEFORE_DAYS == 3
    assert LABEL_LAG_AFTER_DAYS == 1


def test_enrich_precip_antecedent_and_seasonality():
    import pandas as pd

    from ml.precipitation import enrich_precip_windows

    df = pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=40),
        "precipitation_sum": [1.0] * 40,
        "precipitation_hours": [2.0] * 40,
    })
    out = enrich_precip_windows(df, codigo_ibge="2611606")
    assert out.loc[4, "precip_5d"] == 5.0
    assert out.loc[9, "precip_10d"] == 10.0
    assert out.loc[29, "precip_30d"] == 30.0
    assert "sazonalidade_sin" in out.columns
    assert "sazonalidade_cos" in out.columns
    assert abs(out.loc[0, "sazonalidade_sin"] ** 2 + out.loc[0, "sazonalidade_cos"] ** 2 - 1.0) < 1e-3