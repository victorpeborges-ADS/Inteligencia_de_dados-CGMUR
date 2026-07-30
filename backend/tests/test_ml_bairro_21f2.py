"""Testes Fase 21f.2 — modelo por bairro."""

from __future__ import annotations

import json
import pickle
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from ml.constants import BAIRRO_PRODUCTION_MODEL_KINDS, FEATURE_COLUMNS, FEATURE_DEFAULTS
from ml.features import _bairro_terrain_row, _top_quartile_bairro_ids
from ml.model_policy import is_bairro_production_model
from ml.predictor import FloodRiskPredictor


def test_bairro_production_kinds():
    assert "full_bairro" in BAIRRO_PRODUCTION_MODEL_KINDS
    assert is_bairro_production_model({"model_kind": "full_bairro"})
    assert is_bairro_production_model({"model_kind": "full_bairro_no_holdout"})
    assert not is_bairro_production_model({"model_kind": "full"})
    assert not is_bairro_production_model({"model_kind": "full_bairro_below_baseline"})


def test_top_quartile_bairro_ids():
    df = pd.DataFrame({
        "bairro_id": [1, 2, 3, 4],
        "suscetibilidade_local": [0.1, 0.2, 0.8, 0.9],
    })
    ids = _top_quartile_bairro_ids(df)
    assert ids <= {1, 2, 3, 4}
    assert 4 in ids
    assert 3 in ids or 4 in ids


def test_bairro_terrain_row_uses_local_susceptibility():
    municipal = {**FEATURE_DEFAULTS, "suscetibilidade_hand": 0.2, "curve_number": 80.0}
    series = pd.Series({
        "impermeabilizacao_pct": 70.0,
        "cobertura_vegetal_pct": 5.0,
        "declividade_media": 2.0,
        "water_proximity": 0.4,
        "curve_number": 92.0,
        "capacidade_drenagem_mm_h": 12.0,
        "suscetibilidade_local": 0.85,
    })
    row = _bairro_terrain_row(series, municipal)
    assert row["suscetibilidade_hand"] == 0.85
    assert row["curve_number"] == 92.0
    assert row["impermeabilizacao_pct"] == 70.0
    assert row["saturacao_drenagem_40mm"] == pytest.approx(1.0)  # min(1, 40/12)


def test_critical_neighborhoods_fallback_blend(tmp_path):
    """Sem artefato bairro → score_source=blend_susc_iri."""
    terrain = pd.DataFrame([
        {
            "bairro_id": 10,
            "bairro_nome": "Alto",
            "impermeabilizacao_pct": 80.0,
            "cobertura_vegetal_pct": 5.0,
            "declividade_media": 2.0,
            "water_proximity": 0.5,
            "suscetibilidade_local": 0.9,
            "curve_number": 90.0,
            "capacidade_drenagem_mm_h": 10.0,
        },
        {
            "bairro_id": 11,
            "bairro_nome": "Baixo",
            "impermeabilizacao_pct": 30.0,
            "cobertura_vegetal_pct": 40.0,
            "declividade_media": 5.0,
            "water_proximity": 0.05,
            "suscetibilidade_local": 0.2,
            "curve_number": 70.0,
            "capacidade_drenagem_mm_h": 25.0,
        },
    ])
    tpath = tmp_path / "2611606_bairros.parquet"
    terrain.to_parquet(tpath, index=False)
    (tmp_path / "2611606_bairros.municipal.json").write_text(
        json.dumps({**FEATURE_DEFAULTS}),
        encoding="utf-8",
    )

    db = MagicMock()
    muni = MagicMock()
    muni.id = 1
    db.query.return_value.filter.return_value.first.return_value = muni

    predictor = FloodRiskPredictor()
    with (
        patch("ml.predictor.terrain_parquet", return_value=tpath),
        patch.object(predictor, "_load_bairro_model", return_value=None),
        patch(
            "ml.predictor.AnalyticalEngine.calculate_flood_risk",
            return_value=[
                {"id": 10, "indice_risco_inundacao": 0.7},
                {"id": 11, "indice_risco_inundacao": 0.3},
            ],
        ),
        patch("ml.features._load_municipal_terrain", return_value={**FEATURE_DEFAULTS}),
    ):
        rows = predictor._critical_neighborhoods(
            db, "2611606", municipal_prob=0.6, feature_row={**FEATURE_DEFAULTS, "precip_24h": 80.0}
        )

    assert len(rows) == 2
    assert rows[0]["bairro_nome"] == "Alto"
    assert all(r["score_source"] == "blend_susc_iri" for r in rows)
    # Alto deve ter P maior que Baixo (susc + IRI maiores)
    assert rows[0]["risk_probability"] > rows[1]["risk_probability"]


def test_critical_neighborhoods_uses_bairro_model(tmp_path):
    """Com artefato full_bairro → score_source=modelo_bairro e ranking ≠ blend puro."""
    model = RandomForestClassifier(n_estimators=20, random_state=0)
    # Treina para favorecer impermeabilizacao alta
    n = 40
    x = pd.DataFrame({col: np.random.default_rng(0).random(n) for col in FEATURE_COLUMNS})
    x["impermeabilizacao_pct"] = np.linspace(10, 90, n)
    y = (x["impermeabilizacao_pct"] > 50).astype(int)
    model.fit(x[FEATURE_COLUMNS], y)

    meta = {
        "model_kind": "full_bairro",
        "grain": "bairro",
        "feature_columns": FEATURE_COLUMNS,
        "codigo_ibge": "2611606",
    }
    payload = {"model": model, "meta": meta}

    terrain = pd.DataFrame([
        {
            "bairro_id": 1,
            "bairro_nome": "Denso",
            "impermeabilizacao_pct": 85.0,
            "cobertura_vegetal_pct": 5.0,
            "declividade_media": 2.0,
            "water_proximity": 0.4,
            "suscetibilidade_local": 0.5,
            "curve_number": 95.0,
            "capacidade_drenagem_mm_h": 10.0,
        },
        {
            "bairro_id": 2,
            "bairro_nome": "Verde",
            "impermeabilizacao_pct": 20.0,
            "cobertura_vegetal_pct": 50.0,
            "declividade_media": 4.0,
            "water_proximity": 0.05,
            "suscetibilidade_local": 0.5,
            "curve_number": 65.0,
            "capacidade_drenagem_mm_h": 28.0,
        },
    ])
    tpath = tmp_path / "2611606_bairros.parquet"
    terrain.to_parquet(tpath, index=False)

    db = MagicMock()
    muni = MagicMock()
    muni.id = 1
    db.query.return_value.filter.return_value.first.return_value = muni

    predictor = FloodRiskPredictor()
    with (
        patch("ml.predictor.terrain_parquet", return_value=tpath),
        patch.object(predictor, "_load_bairro_model", return_value=payload),
        patch(
            "ml.predictor.AnalyticalEngine.calculate_flood_risk",
            return_value=[
                {"id": 1, "indice_risco_inundacao": 0.5},
                {"id": 2, "indice_risco_inundacao": 0.5},
            ],
        ),
        patch("ml.features._load_municipal_terrain", return_value={**FEATURE_DEFAULTS}),
    ):
        # feature_row com precip alta; IRI e susc iguais → blend daria empate
        feature_row = {
            **FEATURE_DEFAULTS,
            "precip_24h": 90.0,
            "precip_48h": 120.0,
            "precip_72h": 150.0,
            "precip_7d": 200.0,
            "mes_do_ano": 3.0,
        }
        rows = predictor._critical_neighborhoods(
            db, "2611606", municipal_prob=0.5, feature_row=feature_row
        )

    assert len(rows) == 2
    assert all(r["score_source"] == "modelo_bairro" for r in rows)
    # Com IRI/susc iguais, o blend daria 0.5 para ambos; o modelo deve diferenciar
    probs = {r["bairro_nome"]: r["risk_probability"] for r in rows}
    assert probs["Denso"] != probs["Verde"]
    assert probs["Denso"] > probs["Verde"]


def test_bairro_model_paths():
    from ml.paths import bairro_features_parquet, bairro_model_meta_path, bairro_model_path

    assert "bairro" in str(bairro_model_path("2611606"))
    assert "bairro" in str(bairro_model_meta_path("2611606"))
    assert "labeled_bairro" in str(bairro_features_parquet("2611606"))
