from unittest.mock import patch

from app.data_connectors.ibge_collector import _parse_ibge_number, collect_ibge_municipality
from app.data_connectors.siconfi_collector import _pick_value


def test_parse_ibge_number_decimal_dot():
    assert _parse_ibge_number("935.672") == 935.672


def test_parse_ibge_number_integer():
    assert _parse_ibge_number("396526") == 396526.0


def test_parse_ibge_number_brazilian_format():
    assert _parse_ibge_number("1.234,56") == 1234.56


def test_pick_value_prefers_bimestre_column():
    items = [
        {"cod_conta": "ReceitaCorrenteLiquida", "coluna": "PREVISÃO INICIAL", "valor": 100},
        {"cod_conta": "ReceitaCorrenteLiquida", "coluna": "ATÉ O BIMESTRE (a)", "valor": 250},
    ]
    assert _pick_value(items, ("ReceitaCorrenteLiquida",)) == 250.0


@patch("app.data_connectors.ibge_collector._agregado_value")
@patch("app.data_connectors.ibge_collector._pesquisa_value")
def test_collect_ibge_municipality(mock_pesquisa, mock_agregado):
    mock_agregado.side_effect = [
        (420300, 2022),
        (1778947, 2021),
    ]
    mock_pesquisa.side_effect = [
        (420300, 2025),
        (935.672, 2024),
        (448.5, 2010),
    ]
    payload = collect_ibge_municipality("5201108")
    assert payload["populacao"] == 420300
    assert payload["area_km2"] == 935.672
    assert payload["pib_per_capita"] is not None
    assert payload["data_quality"] == "oficial"
