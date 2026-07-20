"""Testes do nível de alerta vivo (CEMADEN → contingência)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.live_alert_level import live_alert_snapshot, max_alert_level, normalize_nivel


def test_normalize_and_max_level():
    assert normalize_nivel("amarelo") == "AMARELO"
    assert normalize_nivel("x") == "VERDE"
    assert max_alert_level(["VERDE", "AMARELO", "LARANJA"]) == "LARANJA"
    assert max_alert_level(["VERMELHO", "AMARELO"]) == "VERMELHO"
    assert max_alert_level([]) == "VERDE"


def test_live_alert_snapshot_aggregates(monkeypatch):
    from app.models import AlertaCemaden, MonitoringAlert, Municipio

    db = MagicMock()
    muni = MagicMock(id=1, codigo_ibge="2611606")
    a1 = MagicMock(tipo="CEMADEN_ALERT", nivel="AMARELO", titulo="Chuva intensa")
    a2 = MagicMock(tipo="RISK_THRESHOLD", nivel="LARANJA", titulo="IRI alto")

    def _query(model):
        q = MagicMock()
        if model is MonitoringAlert:
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [a2, a1]
        elif model is Municipio:
            q.filter.return_value.first.return_value = muni
        elif model is AlertaCemaden:
            q.filter.return_value.count.return_value = 3
        return q

    db.query.side_effect = _query
    snap = live_alert_snapshot(db, "2611606", hours=24)
    assert snap["nivel_alerta"] == "LARANJA"
    assert snap["cemaden_ativos_24h"] == 1
    assert snap["alertas_risco_24h"] == 1
    assert snap["vivo"] is True
    assert snap["fonte"] == "cemaden"
