"""Testes 17d.1 potencial solar e 17d.2 telhado verde."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.solar_rooftop_service import (
    compute_building_solar,
    _hsp_from_lat,
)
from app.services.green_roof_mitigation_service import impermeability_offset_from_green_roofs


def test_hsp_recife_range():
    assert 5.0 <= _hsp_from_lat(-8.05) <= 5.5


def test_compute_building_solar():
    out = compute_building_solar(100.0, hsp=5.2)
    assert out["area_telhado_m2"] == 100.0
    assert out["area_util_m2"] == 70.0
    assert out["potencia_kwp"] == round(70 * 0.15, 2)
    assert out["geracao_kwh_ano"] > 0


def test_impermeability_offset_scales_with_pct():
    a = impermeability_offset_from_green_roofs(1e6, 10e6, 0)
    b = impermeability_offset_from_green_roofs(1e6, 10e6, 50)
    c = impermeability_offset_from_green_roofs(1e6, 10e6, 100)
    assert a == 0.0
    assert b < 0
    assert c < b
    assert c >= -0.25


def test_solar_potential_empty_muni():
    from app.services.solar_rooftop_service import compute_solar_potential

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    try:
        compute_solar_potential(db, "9999999", ensure_buildings=False)
        assert False
    except ValueError:
        pass


def test_green_roof_runs_two_simulations():
    from app.services.green_roof_mitigation_service import run_green_roof_mitigation

    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    muni.nome = "Recife"
    muni.uf = "PE"
    muni.geom = object()

    baseline = {
        "affected_area_km2": 2.0,
        "affected_population": 1000,
        "affected_bairros": ["A"],
        "geometry": {"type": "FeatureCollection", "features": []},
        "simulation_meta": {"max_depth_m": 0.8, "mean_impermeability": 0.7},
    }
    mitigated = {
        "affected_area_km2": 1.5,
        "affected_population": 700,
        "affected_bairros": ["A"],
        "geometry": {"type": "FeatureCollection", "features": []},
        "simulation_meta": {"max_depth_m": 0.6, "mean_impermeability": 0.65},
        "contours": None,
        "flow_paths": None,
        "risk_context": [],
    }

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = muni
    db.query.return_value.filter.return_value.count.return_value = 10
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = []

    with patch(
        "app.services.green_roof_mitigation_service.AnalyticalEngine.run_chuva_extrema_simulation",
        side_effect=[baseline, mitigated],
    ) as mocked:
        with patch(
            "app.services.green_roof_mitigation_service._roof_area_total_m2",
            return_value=500_000.0,
        ):
            with patch(
                "app.services.green_roof_mitigation_service._muni_area_m2",
                return_value=10_000_000.0,
            ):
                out = run_green_roof_mitigation(
                    db, "2611606", precipitacao_mm=100, telhado_verde_pct=40, ensure_buildings=False
                )

    assert out["scenario_type"] == "telhado_verde_permeabilidade"
    assert out["delta"]["area_evitada_km2"] == 0.5
    assert out["delta"]["populacao_evitada"] == 300
    assert mocked.call_count == 2
    # second call has negative offset
    assert mocked.call_args_list[1].kwargs.get("impermeability_offset", 0) < 0
