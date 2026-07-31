"""Testes série PIB municipal IBGE agregado 5938/37."""

from __future__ import annotations

import pytest

from app.data_connectors.ibge_collector import _agregado_series, collect_ibge_municipality


def test_recife_pib_series_has_multiple_years():
    serie = _agregado_series("2611606", 5938, 37, start_year=2018, end_year=2023)
    if not serie:
        pytest.skip("API IBGE indisponível ou sem certificado SSL neste ambiente")
    assert len(serie) >= 4
    assert serie[-1]["ano"] >= 2021
    assert serie[-1]["valor_mil_reais"] > 0


def test_collect_ibge_includes_pib_serie_fields():
    payload = collect_ibge_municipality("2611606")
    if not payload.get("pib_total_mil_reais"):
        pytest.skip("API IBGE indisponível ou sem certificado SSL neste ambiente")
    assert payload.get("pib_total_mil_reais")
    assert isinstance(payload.get("pib_serie"), list)
    assert len(payload["pib_serie"]) >= 5
    assert payload.get("idh") == 0.772
