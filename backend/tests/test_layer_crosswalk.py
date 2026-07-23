"""Testes do cruzamento guiado de camadas (17h.2c)."""

from app.services.layer_crosswalk_service import recommend_layer_crosswalk


def test_pobre_alagamento():
    r = recommend_layer_crosswalk("onde há gente pobre em área de alagamento?")
    assert r["matched_rule"] == "pobre_alagamento"
    assert "socioeconomico" in r["recommended_layers"]
    assert "inundacao" in r["recommended_layers"]


def test_alerta_agora():
    r = recommend_layer_crosswalk("quais alertas CEMADEN agora?")
    assert "alertas" in r["recommended_layers"]


def test_default_fallback():
    r = recommend_layer_crosswalk("olá, tudo bem?")
    assert r["matched_rule"] is None
    assert "vulnerabilidade" in r["recommended_layers"]
    assert "inundacao" in r["recommended_layers"]


def test_escola_risco():
    r = recommend_layer_crosswalk("escolas em risco de inundação")
    assert r["matched_rule"] == "escola_risco"
    assert "educacao" in r["recommended_layers"]
