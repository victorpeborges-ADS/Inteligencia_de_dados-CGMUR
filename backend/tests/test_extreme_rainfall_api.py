"""Teste de integração — simulação pluvial extrema (Recife)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config as config_module
import app.security.auth as auth_module
from main import app

RECIFE_IBGE = "2611606"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_auth(monkeypatch):
    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", False)
    auth_module._USER_STORE = None
    yield
    auth_module._USER_STORE = None


def _flood_band_features(geometry: dict) -> list[dict]:
    return [
        f
        for f in geometry.get("features", [])
        if f.get("properties", {}).get("layer_type") == "flood_band"
    ]


def test_extreme_rainfall_recife_api(client: TestClient):
    res = client.post(
        "/api/v1/simulations/extreme-rainfall",
        json={"precipitacao_mm": 120.0, "codigo_ibge": RECIFE_IBGE},
    )
    if res.status_code == 404:
        pytest.skip("Município Recife (2611606) não carregado no banco de testes.")

    assert res.status_code == 200, res.text
    body = res.json()

    assert body["scenario_type"] == "ExtremeRainfall"
    assert body["input_value"] == 120.0
    assert body["affected_area_km2"] > 0
    assert isinstance(body.get("affected_bairros"), list)

    meta = body.get("simulation_meta") or {}
    assert meta.get("dem_available") is True
    assert meta.get("method") == "dem_pluvial_d8_twi"
    assert meta.get("model_version") == "2.3"
    assert meta.get("dem_resolution_m") is not None
    assert meta.get("contour_interval_m") is not None
    assert meta.get("flow_accumulation_applied") is True
    assert meta.get("impermeability_applied") is True
    assert meta.get("flood_patches", 0) >= 1
    assert meta.get("max_depth_m", 0) > 0.05
    assert meta.get("bairros_atingidos_count", 0) >= 1
    assert isinstance(meta.get("bairros_exposicao"), list)
    assert meta["bairros_exposicao"][0]["exposicao_pct"] > 0

    flood_bands = _flood_band_features(body.get("geometry") or {})
    assert len(flood_bands) >= 1
    assert len(flood_bands) == meta.get("flood_patches")

    bands = {f["properties"]["depth_band"] for f in flood_bands}
    assert bands & {"superficial", "moderada", "critica"}


def test_extreme_rainfall_recife_higher_precip_expands_impact(client: TestClient):
    low = client.post(
        "/api/v1/simulations/extreme-rainfall",
        json={"precipitacao_mm": 60.0, "codigo_ibge": RECIFE_IBGE},
    )
    high = client.post(
        "/api/v1/simulations/extreme-rainfall",
        json={"precipitacao_mm": 180.0, "codigo_ibge": RECIFE_IBGE},
    )
    if low.status_code == 404 or high.status_code == 404:
        pytest.skip("Município Recife (2611606) não carregado no banco de testes.")

    assert low.status_code == 200
    assert high.status_code == 200

    low_meta = low.json().get("simulation_meta") or {}
    high_meta = high.json().get("simulation_meta") or {}

    assert high_meta.get("max_depth_m", 0) >= low_meta.get("max_depth_m", 0)
    assert high.json()["affected_area_km2"] >= low.json()["affected_area_km2"]
