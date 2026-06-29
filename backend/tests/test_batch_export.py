"""Testes de exportação em lote."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.batch_export_service import run_batch_diagnostics, run_batch_reports


def test_batch_diagnostics_skips_missing_municipio():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    result = run_batch_diagnostics(db, limit=1, codigos=["9999999"])
    assert result["processed"] == 0
    assert result["skipped"] == 1
    assert result["errors"]


@patch("app.services.maturity_engine.compute_maturity", return_value={"score": 10.0})
def test_batch_reports_blocks_low_maturity(_mock_maturity):
    db = MagicMock()
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    db.query.return_value.filter.return_value.first.return_value = muni
    result = run_batch_reports(db, limit=1, force=False, codigos=["2611606"])
    assert result["processed"] == 0
    assert result["blocked_maturidade"] == 1
