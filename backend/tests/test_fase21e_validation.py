"""Testes Fase 21d.1 (intensidade) e 21e (validação)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.constants import FEATURE_COLUMNS, FEATURE_DEFAULTS
from ml.intensity import enrich_intensity_features, intensity_from_precip
from ml.validation import evaluate_protocol, rain_threshold_baseline, temporal_split


def test_intensity_features_from_hours():
    df = pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=3),
        "precipitation_sum": [0.0, 60.0, 12.0],
        "precipitation_hours": [0.0, 3.0, 6.0],
    })
    out = enrich_intensity_features(df, codigo_ibge="2611606")
    assert out.loc[0, "intensidade_media_mm_h"] == 0.0
    assert out.loc[1, "intensidade_media_mm_h"] == 20.0
    assert out.loc[1, "intensidade_pico_proxy_mm_h"] == 40.0
    assert out.loc[1, "duracao_chuva_h"] == 3.0
    assert out.loc[1, "razao_intensidade_idf_tr2"] > 0


def test_intensity_from_precip_inference_aligns():
    feats = intensity_from_precip(60.0, duracao_h=3.0, codigo_ibge="2611606")
    assert feats["intensidade_media_mm_h"] == 20.0
    assert feats["intensidade_pico_proxy_mm_h"] == 40.0


def test_feature_columns_include_intensity():
    for col in (
        "duracao_chuva_h",
        "intensidade_media_mm_h",
        "intensidade_pico_proxy_mm_h",
        "razao_intensidade_idf_tr2",
    ):
        assert col in FEATURE_COLUMNS
        assert col in FEATURE_DEFAULTS


def test_temporal_split_and_protocol():
    rng = np.random.default_rng(0)
    rows = []
    for year in range(2015, 2025):
        for month in range(1, 13):
            precip = float(rng.uniform(0, 120))
            label = 1 if precip > 70 and month in (4, 5, 6) and rng.random() > 0.3 else 0
            row = {
                "date": pd.Timestamp(year=year, month=month, day=15),
                "precip_24h": precip,
                "precip_48h": precip * 1.3,
                "precip_72h": precip * 1.5,
                "precip_7d": precip * 2.0,
                "mes_do_ano": float(month),
                "label": label,
            }
            for c in FEATURE_COLUMNS:
                row.setdefault(c, FEATURE_DEFAULTS.get(c, 1.0))
            rows.append(row)
    df = pd.DataFrame(rows)
    train, test = temporal_split(df)
    assert train["date"].dt.year.max() <= 2021
    assert test["date"].dt.year.min() >= 2022

    result = evaluate_protocol(df, rain_threshold_mm=50.0, calibrate=False)
    assert result["ok"] is True
    assert "brier_model" in result
    assert "brier_rain_baseline" in result
    assert "reliability_curve" in result
    rain = rain_threshold_baseline(test["label"], test["precip_24h"], 50.0)
    assert set(np.unique(rain)).issubset({0.0, 1.0})


def test_spatial_hit_rate_with_geojson():
    from shapely.geometry import Point
    from unittest.mock import MagicMock, patch

    from ml.validation import evaluate_spatial_hit_rate

    flood_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"layer_type": "ml_risk_zone"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-0.01, -0.01], [0.01, -0.01], [0.01, 0.01], [-0.01, 0.01], [-0.01, -0.01]]
                    ],
                },
            }
        ],
    }

    db = MagicMock()
    with patch(
        "ml.validation._load_official_event_points",
        return_value=[
            {"id": 1, "fonte": "evento_alagamento_observado", "geom": Point(0.0, 0.0)},
            {"id": 2, "fonte": "evento_alagamento_observado", "geom": Point(10.0, 10.0)},
        ],
    ), patch(
        "ml.validation._risk_zone_from_terrain",
        return_value=(None, [], "unused"),
    ):
        # Municipio / bairros vazios para Jaccard
        muni_q = MagicMock()
        muni_q.filter.return_value.first.return_value = None
        db.query.return_value = muni_q

        result = evaluate_spatial_hit_rate(
            db,
            "2611606",
            flood_geojson=flood_fc,
            affected_bairros=["Centro"],
        )

    assert result["protocol"] == "21e5_spatial_hit_rate"
    assert result["eventos_com_geometria"] == 2
    assert result["eventos_na_zona"] == 1
    assert result["hit_rate"] == 0.5
    assert result["acordo"] == "media"
    assert result["disponivel"] is True


def test_model_card_includes_spatial(tmp_path):
    from ml.validation import write_model_card

    path = tmp_path / "card.md"
    write_model_card(
        path,
        codigo_ibge="2611606",
        meta={"model_version": "1.3", "model_kind": "full", "n_positive": 3, "label_policy": "official_only"},
        validation={
            "train_end_year": 2021,
            "test_start_year": 2022,
            "spatial": {
                "disponivel": True,
                "fonte": "evento_alagamento_observado",
                "eventos_com_geometria": 4,
                "hit_rate": 0.75,
                "jaccard_bairros": 0.5,
                "acordo": "alta",
                "zona_metodo": "top_25pct_suscetibilidade_local",
                "narrativa": "ok",
            },
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "Validação espacial (21e.5)" in text
    assert "0.75" in text
    assert "top_25pct_suscetibilidade_local" in text
