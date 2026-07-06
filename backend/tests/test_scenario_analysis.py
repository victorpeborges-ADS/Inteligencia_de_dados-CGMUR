"""Testes análise de cenário — Step 6."""

from app.services.scenario_analysis_service import (
    _deterministic_analysis,
    alert_icon_and_category,
    group_timeline_entries,
    RISK_ACTIONS,
)


def test_deterministic_analysis_amarelo():
    ctx = {
        "municipio_nome": "Recife",
        "n_alertas": 31,
        "precip_24h": 0.1,
        "precip_72h": 8.4,
        "nivel_risco": "AMARELO",
        "prob_critico": 15,
        "proxima_revisao": "14:30",
        "historico_similar": None,
    }
    out = _deterministic_analysis(ctx)
    assert "Recife" in out["interpretacao"]
    assert out["recomendacao_nivel"] == "AMARELO"
    assert len(out["recomendacoes"]) == len(RISK_ACTIONS["AMARELO"])


def test_group_timeline():
    entries = [
        {"id": 1, "tipo": "CEMADEN_ALERT", "nivel": "AMARELO", "titulo": "Alerta CEMADEN", "mensagem": "chuva", "created_at": "2026-07-06T10:00:00"},
        {"id": 2, "tipo": "CEMADEN_ALERT", "nivel": "AMARELO", "titulo": "Alerta CEMADEN", "mensagem": "chuva", "created_at": "2026-07-06T11:00:00"},
    ]
    grouped = group_timeline_entries(entries)
    assert len(grouped) == 1
    assert grouped[0]["count"] == 2
    assert "2 alertas" in grouped[0]["titulo_display"]


def test_alert_icon_rain():
    icon, cat = alert_icon_and_category("CEMADEN_ALERT", "Chuva intensa", "precipitação")
    assert icon == "rain"
    assert cat == "Chuva"
