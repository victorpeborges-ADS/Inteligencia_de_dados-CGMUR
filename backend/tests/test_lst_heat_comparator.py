"""Testes do comparador LST × simulação de calor."""

from unittest.mock import MagicMock, patch

from app.services.georedus_lst_service import _parse_lst_point_payload
from app.services.lst_heat_comparator import (
    _sim_temps_by_bairro,
    compare_heat_simulation_with_lst,
)


def test_parse_lst_point_payload():
    data = {
        "values": [
            ["s3://tile.tif", [None], ["b1"]],
            ["s3://tile2.tif", [42.3], ["b1"]],
        ]
    }
    assert _parse_lst_point_payload(data) == 42.3


def test_sim_temps_by_bairro_from_meta():
    sim = {
        "simulation_meta": {
            "bairros_exposicao": [
                {"bairro": "Boa Viagem", "temp_local_c": 38.5, "faixa_calor": "severa"},
                {"bairro": "Centro", "temp_superficie_c": 36.0},
            ]
        }
    }
    temps = _sim_temps_by_bairro(sim)
    assert temps["Boa Viagem"] == 38.5
    assert temps["Centro"] == 36.0


@patch("app.services.lst_heat_comparator.fetch_lst_point")
@patch("app.services.lst_heat_comparator._bairro_centroids")
def test_compare_heat_simulation_with_lst(mock_centroids, mock_fetch):
    mock_centroids.return_value = {
        "Bairro A": (-34.88, -8.05),
        "Bairro B": (-34.90, -8.07),
    }
    mock_fetch.side_effect = lambda lon, lat: 40.0 if lon == -34.88 else 37.5

    muni = MagicMock()
    muni.id = 1
    muni.nome = "Recife"
    muni.uf = "PE"
    muni.codigo_ibge = "2611606"

    simulation = {
        "impact_value": 4.2,
        "simulation_meta": {
            "temperatura_pico_c": 36.0,
            "max_delta_t_c": 4.2,
            "bairros_exposicao": [
                {"bairro": "Bairro A", "temp_local_c": 41.0, "faixa_calor": "severa"},
                {"bairro": "Bairro B", "temp_local_c": 39.0, "faixa_calor": "moderada"},
            ],
        },
    }

    db = MagicMock()
    result = compare_heat_simulation_with_lst(db, muni, simulation)

    assert result["disponivel"] is True
    assert result["amostras_validas"] == 2
    assert result["lst_mediana_c"] == 38.8
    assert result["sim_temp_mediana_c"] == 40.0
    assert result["divergencia_mediana_c"] == 1.2
    assert len(result["bairros"]) == 2
