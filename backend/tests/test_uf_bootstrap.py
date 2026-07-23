"""Testes bootstrap por UF (18c.1)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.uf_bootstrap_service import (
    normalize_uf,
    preview_uf_bootstrap,
    bootstrap_uf,
)


def test_normalize_uf_ok():
    assert normalize_uf("pe") == "PE"
    assert normalize_uf("RJ") == "RJ"


def test_normalize_uf_invalid():
    with pytest.raises(ValueError):
        normalize_uf("XX")


@patch("app.services.uf_bootstrap_service.list_municipios_ibge_uf")
def test_preview_uf_bootstrap(mock_list):
    mock_list.return_value = [
        {"codigo_ibge": "2611606", "nome": "Recife", "uf": "PE"},
        {"codigo_ibge": "2604106", "nome": "Caruaru", "uf": "PE"},
    ]
    db = MagicMock()
    # já carregado: Recife
    row = MagicMock(codigo_ibge="2611606")
    db.query.return_value.filter.return_value.all.return_value = [row]

    out = preview_uf_bootstrap(db, "PE", limit=10)
    assert out["uf"] == "PE"
    assert out["total_ibge"] == 2
    assert out["ja_carregados"] == 1
    assert out["pendentes"] == 1
    assert out["a_processar"] == 1
    assert out["amostra"][0]["codigo_ibge"] == "2604106"


@patch("app.services.uf_bootstrap_service._bootstrap_one")
@patch("app.services.uf_bootstrap_service.list_municipios_ibge_uf")
def test_bootstrap_uf_processes_pending(mock_list, mock_one):
    mock_list.return_value = [
        {"codigo_ibge": "2611606", "nome": "Recife", "uf": "PE"},
        {"codigo_ibge": "2604106", "nome": "Caruaru", "uf": "PE"},
    ]
    mock_one.return_value = {
        "codigo_ibge": "2604106",
        "nome": "Caruaru",
        "uf": "PE",
        "status": "ok",
        "steps": {"ensure": "ok"},
        "errors": [],
    }
    db = MagicMock()
    row = MagicMock(codigo_ibge="2611606")
    db.query.return_value.filter.return_value.all.return_value = [row]

    out = bootstrap_uf(db, "PE", limit=5, skip_existing=True)
    assert out["uf"] == "PE"
    assert out["processed"] == 1
    assert out["ok"] == 1
    mock_one.assert_called_once()
