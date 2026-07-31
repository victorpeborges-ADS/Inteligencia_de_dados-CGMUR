"""Testes unitários do coletor SICONFI."""
from __future__ import annotations

from unittest.mock import patch

from app.data_connectors.siconfi_collector import (
    _pick_function_expense,
    _pick_value,
    collect_siconfi_municipality,
)


def test_pick_value_preferred_column():
    items = [
        {"cod_conta": "ReceitaCorrenteLiquida", "coluna": "OUTRA", "valor": "10"},
        {"cod_conta": "ReceitaCorrenteLiquida", "coluna": "ATÉ O BIMESTRE", "valor": "100.5"},
    ]
    assert _pick_value(items, ("ReceitaCorrenteLiquida",)) == 100.5


def test_pick_value_fallback_and_none():
    items = [{"cod_conta": "PessoalEEncargosSociais", "coluna": "X", "valor": "bad"}]
    assert _pick_value(items, ("PessoalEEncargosSociais",)) is None
    assert _pick_value([], ("ReceitaCorrenteLiquida",)) is None
    items_ok = [{"cod_conta": "PessoalEEncargosSociais", "coluna": "X", "valor": "50"}]
    assert _pick_value(items_ok, ("PessoalEEncargosSociais",)) == 50.0


def test_pick_function_expense_by_keyword():
    items = [
        {"cod_conta": "SaneamentoBasico", "conta": "Saneamento", "coluna": "ATÉ O BIMESTRE", "valor": "33"},
    ]
    assert _pick_function_expense(items, ("Saneamento",)) == 33.0
    assert _pick_function_expense(items, ("DefesaCivil",)) is None


@patch("app.data_connectors.siconfi_collector._fetch_demonstrativo")
def test_collect_siconfi_municipality_computes_pct(mock_fetch):
    mock_fetch.side_effect = [
        [
            {"cod_conta": "ReceitaCorrenteLiquida", "coluna": "ATÉ O BIMESTRE", "valor": "200"},
            {"cod_conta": "PessoalEEncargosSociais", "coluna": "ATÉ O BIMESTRE", "valor": "80"},
            {"cod_conta": "ResultadoPrimario", "coluna": "ATÉ O BIMESTRE", "valor": "5"},
            {"cod_conta": "Habitacao", "coluna": "ATÉ O BIMESTRE", "valor": "12"},
        ],
        [
            {"cod_conta": "DividaConsolidada", "coluna": "ATÉ O BIMESTRE", "valor": "40"},
        ],
    ]
    out = collect_siconfi_municipality("2611606")
    assert out["receita_corrente_liquida"] == 200.0
    assert out["despesa_pessoal_pct_rcl"] == 40.0
    assert out["divida_consolidada"] == 40.0
    assert out["exec_habitacao"] == 12.0
    assert out["data_quality"] == "oficial"


@patch("app.data_connectors.siconfi_collector._fetch_demonstrativo", return_value=[])
def test_collect_siconfi_empty_estimado(mock_fetch):
    out = collect_siconfi_municipality("9999999")
    assert out["data_quality"] == "estimado"
    assert out["receita_corrente_liquida"] is None
