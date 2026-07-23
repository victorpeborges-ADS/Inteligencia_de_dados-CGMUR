"""Testes 17d.4 infraverde×calor e 17d.5 comparador."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_green_infra_heat_delta():
    from app.services.green_infra_heat_service import run_green_infra_heat

    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    muni.nome = "Recife"
    muni.uf = "PE"

    baseline = {
        "impact_value": 4.0,
        "affected_population": 1000,
        "affected_area_km2": 5.0,
        "affected_bairros": ["A"],
        "geometry": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {
                    "name": "A",
                    "temp_increase_celsius": 4.0,
                    "temp_local_celsius": 40.0,
                    "populacao_exposta": 1000,
                    "resfriamento_celsius": 0,
                },
                "geometry": None,
            }],
        },
        "simulation_meta": {"max_delta_t_c": 4.0, "resfriamento_medio_c": 0},
    }
    mitigated = {
        "impact_value": 2.5,
        "affected_population": 700,
        "affected_area_km2": 4.0,
        "affected_bairros": ["A"],
        "geometry": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {
                    "name": "A",
                    "temp_increase_celsius": 2.5,
                    "temp_local_celsius": 38.5,
                    "populacao_exposta": 700,
                    "resfriamento_celsius": 1.5,
                },
                "geometry": None,
            }],
        },
        "simulation_meta": {"max_delta_t_c": 2.5, "resfriamento_medio_c": 1.5},
    }

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = muni

    with patch(
        "app.services.green_infra_heat_service.run_heat_island_simulation",
        side_effect=[baseline, mitigated],
    ):
        out = run_green_infra_heat(db, "2611606", arborizacao_pct=30, temperatura_pico_c=36)

    assert out["scenario_type"] == "infraestrutura_verde_calor"
    assert out["delta"]["resfriamento_max_c"] == 1.5
    assert out["delta"]["populacao_menos_exposta"] == 300
    assert out["ranking_bairros"][0]["bairro"] == "A"


def test_compare_interventions_routes_tipos():
    from app.services.intervention_comparator_service import compare_interventions

    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    muni.nome = "Recife"
    muni.uf = "PE"
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = muni

    with patch(
        "app.services.solar_rooftop_service.compute_solar_potential",
        return_value={
            "potencia_total_kwp": 100,
            "potencia_total_mwp": 0.1,
            "geracao_total_mwh_ano": 150,
            "edificios_avaliados": 10,
            "affected_area_km2": 0.01,
            "geometry": {"type": "FeatureCollection", "features": []},
        },
    ):
        solar = compare_interventions(db, "2611606", tipo="solar")
    assert solar["tipo"] == "solar"
    assert solar["delta"]["potencia_kwp"] == 100

    with patch(
        "app.services.green_infra_heat_service.run_green_infra_heat",
        return_value={
            "baseline": {"max_delta_t_c": 4},
            "mitigated": {"max_delta_t_c": 2},
            "delta": {"resfriamento_max_c": 2, "populacao_menos_exposta": 50},
            "geometry": {"type": "FeatureCollection", "features": []},
            "metric_impact": "x",
            "impact_value": 2,
            "affected_area_km2": 1,
            "affected_population": 10,
            "affected_bairros": [],
            "simulation_meta": {},
        },
    ):
        heat = compare_interventions(db, "2611606", tipo="infraverde_calor", arborizacao_pct=20)
    assert heat["tipo"] == "infraverde_calor"
    assert "Resfriamento" in heat["delta"]["resumo"]
