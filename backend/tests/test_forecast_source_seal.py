"""Testes do selo canônico de previsão (20e.3)."""

from app.services.forecast_source_seal import build_forecast_seal, seal_from_weather_payload


def test_seal_openmeteo_heuristic():
    seal = build_forecast_seal(
        risk_source="precip_curve",
        precip_forecast_mm=40,
        precip_for_risk_mm=40,
        cemaden_obs_mm=10,
    )
    assert seal["selo_qualidade"] == "Estimado"
    assert seal["fonte_chuva"] == "openmeteo"
    assert seal["score_kind"] == "score_heuristico_chuva"
    assert "Heurística" in seal["label_ui"]
    assert "calibrada" in seal["narrativa"].lower() or "heurístico" in seal["narrativa"].lower()


def test_seal_cemaden_observed_overrides_forecast():
    seal = build_forecast_seal(
        risk_source="precip_curve",
        precip_forecast_mm=20,
        precip_for_risk_mm=95,
        cemaden_obs_mm=95,
        cemaden_estacoes=3,
    )
    assert seal["usou_chuva_observada"] is True
    assert seal["fonte_chuva"] == "cemaden_obs"
    assert seal["selo_qualidade"] == "Observado"
    assert "CEMADEN" in seal["narrativa"]


def test_seal_ml_full_derivado():
    seal = build_forecast_seal(risk_source="ml_full", precip_forecast_mm=50)
    assert seal["selo_qualidade"] == "Derivado"
    assert seal["score_kind"] == "probabilidade_modelo"
    assert "ML full" in seal["label_ui"]


def test_seal_experimental_synthetic():
    seal = build_forecast_seal(
        risk_source="precip_curve",
        experimental=True,
        model_kind="baseline_synthetic",
        production_ready=False,
    )
    assert seal["selo_qualidade"] == "Estimado"
    assert seal["score_kind"] == "score_sintetico"
    assert seal["risk_source"] == "experimental"


def test_seal_from_cached_payload():
    payload = {
        "_risk_source": "precip_curve",
        "_selo_previsao": {
            "selo_qualidade": "Observado",
            "fonte_chuva": "cemaden_obs",
            "risk_source": "precip_curve",
            "score_kind": "score_heuristico_chuva",
            "label_ui": "Heurística · Observado",
            "narrativa": "cached",
            "disclaimer": "x",
        },
    }
    seal = seal_from_weather_payload(payload)
    assert seal["selo_qualidade"] == "Observado"
    assert seal["narrativa"] == "cached"
