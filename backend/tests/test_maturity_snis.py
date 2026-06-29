"""Testes de maturidade com SNIS."""

from unittest.mock import MagicMock

from app.services.maturity_engine import _eval_snis, compute_maturity


def test_eval_snis_oficial():
    row = MagicMock()
    row.data_quality = "oficial"
    row.cobertura_agua_pct = 97.2
    row.cobertura_esgoto_pct = 67.8

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = row

    result = _eval_snis(db, "2611606")
    assert result["status"] == "OFICIAL"
    assert result["id"] == "snis"
    assert "97" in result["detail"]


def test_eval_snis_lacuna():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    result = _eval_snis(db, "9999999")
    assert result["status"] == "LACUNA"


def test_compute_maturity_includes_snis_source():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    result = compute_maturity(db, "2611606")
    source_ids = [item["id"] for item in result["fontes"]]
    assert "snis" in source_ids
