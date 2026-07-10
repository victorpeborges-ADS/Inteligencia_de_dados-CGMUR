"""Testes do coletor de déficits domiciliares Censo 2022."""

from unittest.mock import MagicMock, patch

from app.data_connectors.censo_deficits_collector import (
    _pct,
    _poverty_factor,
    distribute_deficits_to_setores,
    fetch_municipal_deficits,
)


def test_pct_helper():
    assert _pct(25, 100) == 25.0
    assert _pct(None, 100) is None


def test_poverty_factor_lower_income_higher_weight():
    assert _poverty_factor(1200, 2200) > _poverty_factor(3500, 2200)


@patch("app.data_connectors.censo_deficits_collector._sidra_count")
def test_fetch_municipal_deficits_builds_rates(mock_count):
    def sidra_side_effect(path: str) -> float | None:
        if "c14/200/c11558/46292" in path and "72255" not in path and "72267" not in path and "72278" not in path:
            return 10_000.0  # denominador PUE
        if "c14/72255" in path:
            return 1_000.0
        if "c14/72267" in path:
            return 2_000.0
        if "c14/72278" in path:
            return 3_000.0
        if "c1821/72153" in path:
            return 400.0
        if "c11558/72113" in path or "c11558/92858" in path:
            return 250.0
        if "c67/10972" in path:
            return 10_000.0
        if "c67/72122" in path:
            return 50.0
        if "v/2513" in path:
            return 94.0
        return None

    mock_count.side_effect = sidra_side_effect

    result = fetch_municipal_deficits("2611606")
    rates = result["taxas_municipais"]
    assert result["disponivel"] is True
    assert rates["iluminacao_pct"] == 10.0
    assert rates["alfabetizacao_pct"] == 6.0


@patch("app.data_connectors.censo_deficits_collector.fetch_municipal_deficits")
def test_distribute_deficits_to_setores(mock_fetch):
    mock_fetch.return_value = {
        "taxas_municipais": {
            "iluminacao_pct": 10.0,
            "calcada_pct": 20.0,
            "arborizacao_pct": 30.0,
            "agua_pct": 5.0,
            "esgoto_pct": 15.0,
            "lixo_pct": 2.0,
            "alfabetizacao_pct": 6.0,
        }
    }
    muni = MagicMock()
    muni.codigo_ibge = "2611606"
    muni.id = 1

    setor_rico = MagicMock(renda_media=4000, deficits_censo_json=None)
    setor_pobre = MagicMock(renda_media=900, deficits_censo_json=None)
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [setor_rico, setor_pobre]

    updated = distribute_deficits_to_setores(db, muni, mock_fetch.return_value)
    assert updated == 2
    assert setor_pobre.deficits_censo_json["iluminacao"] > setor_rico.deficits_censo_json["iluminacao"]
