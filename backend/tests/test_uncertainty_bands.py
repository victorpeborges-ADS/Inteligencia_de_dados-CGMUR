"""Testes das bandas de incerteza (17g.2c)."""

from unittest.mock import MagicMock, patch

from app.services.uncertainty_bands_service import attach_uncertainty_bands


def test_attach_uncertainty_bands_envelope():
    expected = {
        "scenario_type": "ExtremeRainfall",
        "input_value": 100.0,
        "affected_area_km2": 10.0,
        "affected_population": 1000,
        "simulation_meta": {"max_depth_m": 1.0, "flood_patches": 5},
    }
    opt = {
        "scenario_type": "ExtremeRainfall",
        "input_value": 85.0,
        "affected_area_km2": 7.0,
        "affected_population": 700,
        "simulation_meta": {"max_depth_m": 0.7, "flood_patches": 3},
    }
    pes = {
        "scenario_type": "ExtremeRainfall",
        "input_value": 115.0,
        "affected_area_km2": 14.0,
        "affected_population": 1400,
        "simulation_meta": {"max_depth_m": 1.4, "flood_patches": 8},
    }

    db = MagicMock()
    with patch(
        "app.services.uncertainty_bands_service.run_rainfall_cached",
        side_effect=[opt, pes],
    ):
        out = attach_uncertainty_bands(db, 1, "2611606", expected, delta_pct=15)

    bands = out["simulation_meta"]["uncertainty_bands"]
    assert bands["precip_delta_pct"] == 15.0
    assert bands["optimistic"]["max_depth_m"] == 0.7
    assert bands["expected"]["max_depth_m"] == 1.0
    assert bands["pessimistic"]["max_depth_m"] == 1.4
    assert bands["optimistic"]["affected_area_km2"] <= bands["pessimistic"]["affected_area_km2"]


def test_skip_non_rainfall():
    result = {"scenario_type": "HeatIsland", "input_value": 36}
    out = attach_uncertainty_bands(MagicMock(), 1, "2611606", result)
    assert "uncertainty_bands" not in (out.get("simulation_meta") or {})
