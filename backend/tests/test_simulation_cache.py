"""Testes cache e compare paralelo de simulação pluvial."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services import simulation_cache as sc


@pytest.fixture(autouse=True)
def enable_cache(monkeypatch):
    monkeypatch.setattr(sc, "SIMULATION_CACHE_ENABLED", True)
    # Isola do Redis compartilhado com dev/docker — sem isso, uma chave residual de
    # execução anterior faz o "primeiro" run já vir de cache, quebrando o teste.
    fake_cache: dict[str, object] = {}
    monkeypatch.setattr(sc, "cache_get_json", lambda key: fake_cache.get(key))
    monkeypatch.setattr(sc, "cache_set_json", lambda key, value, ttl=None: fake_cache.__setitem__(key, value))


def test_rainfall_cache_hit(monkeypatch):
    calls = {"n": 0}

    def fake_run(db, muni_id, mm, **kwargs):
        calls["n"] += 1
        return {"scenario_type": "ExtremeRainfall", "input_value": mm, "impact_value": 1}

    monkeypatch.setattr(sc.AnalyticalEngine, "run_chuva_extrema_simulation", fake_run)
    db = MagicMock()

    first = sc.run_rainfall_cached(db, 1, "2611606", 120.0)
    second = sc.run_rainfall_cached(db, 1, "2611606", 120.0)

    assert calls["n"] == 1
    assert first["from_cache"] is False
    assert second["from_cache"] is True


def test_compare_delta_bairros():
    baseline = {"affected_bairros": ["A", "B"], "affected_area_km2": 10, "affected_population": 100, "simulation_meta": {"max_depth_m": 1.0, "flood_patches": 2}}
    scenario = {"affected_bairros": ["B", "C"], "affected_area_km2": 12, "affected_population": 120, "simulation_meta": {"max_depth_m": 1.5, "flood_patches": 4}}
    delta = sc.get_compare_delta(baseline, scenario, 80, 120)
    assert delta["bairros_novos"] == ["C"]
    assert delta["bairros_removidos"] == ["A"]
    assert delta["affected_area_km2"] == 2.0
