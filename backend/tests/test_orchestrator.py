"""Testes do IntegrationOrchestrator com conectores mockados."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.data_connectors.orchestrator import IntegrationOrchestrator


def _db_mock() -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.count.return_value = 0
    return db


@patch("app.observability.metrics.record_integration_sync")
@patch("app.data_connectors.orchestrator.sync_singedlab_batch")
@patch("app.data_connectors.orchestrator.sync_external_sources_batch")
@patch("app.data_connectors.orchestrator.collect_snis_municipality")
@patch("app.data_connectors.orchestrator.collect_capag_municipality")
@patch("app.data_connectors.orchestrator.collect_siconfi_municipality")
@patch("app.data_connectors.orchestrator.collect_ibge_municipality")
def test_sync_all_counts_successes(
    mock_ibge,
    mock_siconfi,
    mock_capag,
    mock_snis,
    mock_ext,
    mock_singed,
    _mock_metrics,
):
    mock_ibge.return_value = {
        "populacao": 1000,
        "area_km2": 10.0,
        "populacao_ano": 2024,
        "raw_payload": {},
    }
    mock_siconfi.return_value = {
        "receita_corrente_liquida": 1.0,
        "despesa_pessoal_pct_rcl": 40.0,
        "resultado_primario": 0.1,
        "raw_payload": {},
    }
    mock_capag.return_value = {"nota_capag": "B", "fonte": "CAPAG", "indicadores": []}
    mock_snis.return_value = {
        "data_quality": "oficial",
        "cobertura_agua_pct": 90.0,
        "raw_payload": {},
    }
    mock_ext.return_value = {"processed": 2, "errors": []}
    mock_singed.return_value = {"processed": 1, "errors": []}

    db = _db_mock()
    muni = MagicMock(id=1, codigo_ibge="2611606")
    db.query.return_value.filter.return_value.first.return_value = muni

    orch = IntegrationOrchestrator(db)
    summary = orch.sync_all(codigos=["2611606"])

    assert summary["ibge"] == 1
    assert summary["siconfi"] == 1
    assert summary["capag"] == 1
    assert summary["snis"] == 1
    assert summary["fontes_externas"] == 2
    assert summary["singedlab"] == 1
    assert summary["errors"] == []
    assert db.commit.called
    assert db.add.call_count >= 6  # IntegrationRun rows


@patch("app.data_connectors.orchestrator.sync_singedlab_batch", side_effect=RuntimeError("sl"))
@patch("app.data_connectors.orchestrator.sync_external_sources_batch", return_value={"processed": 0, "errors": []})
@patch("app.data_connectors.orchestrator.collect_snis_municipality", side_effect=RuntimeError("snis"))
@patch("app.data_connectors.orchestrator.collect_capag_municipality", side_effect=RuntimeError("capag"))
@patch("app.data_connectors.orchestrator.collect_siconfi_municipality", side_effect=RuntimeError("siconfi"))
@patch("app.data_connectors.orchestrator.collect_ibge_municipality", side_effect=RuntimeError("ibge"))
def test_sync_all_collects_errors(mock_ibge, mock_siconfi, mock_capag, mock_snis, mock_ext, mock_sl):
    db = _db_mock()
    orch = IntegrationOrchestrator(db)
    summary = orch.sync_all(codigos=["2611606"])
    sources = {e["source"] for e in summary["errors"]}
    assert "ibge" in sources
    assert "siconfi" in sources
    assert "capag" in sources
    assert "snis" in sources
    assert "singedlab" in sources
    assert summary["ibge"] == 0


def test_sync_ibge_returns_false_without_population():
    db = _db_mock()
    orch = IntegrationOrchestrator(db)
    with patch(
        "app.data_connectors.orchestrator.collect_ibge_municipality",
        return_value={"populacao": None},
    ):
        assert orch._sync_ibge("2611606") is False


def test_sync_snis_returns_false_on_lacuna():
    db = _db_mock()
    orch = IntegrationOrchestrator(db)
    with patch(
        "app.data_connectors.orchestrator.collect_snis_municipality",
        return_value={"data_quality": "lacuna"},
    ):
        assert orch._sync_snis("2611606") is False


def test_status_marks_empty_as_desatualizado():
    db = _db_mock()
    db.query.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    orch = IntegrationOrchestrator(db)
    status = orch.status()
    assert len(status) >= 4
    assert all(item["status"] == "DESATUALIZADO" for item in status)
    assert all(item["records_count"] == 0 for item in status)
