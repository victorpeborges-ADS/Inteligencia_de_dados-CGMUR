"""Teste de integração — comparação de cenários pluviais."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config as config_module
import app.security.auth as auth_module
from main import app
from tests.conftest import requires_postgres

RECIFE_IBGE = "2611606"

pytestmark = requires_postgres


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_auth(monkeypatch):
    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", False)
    auth_module._USER_STORE = None
    yield
    auth_module._USER_STORE = None


def test_compare_rainfall_recife_api(client: TestClient):
    res = client.post(
        "/api/v1/simulations/extreme-rainfall/compare",
        json={"baseline_mm": 80.0, "scenario_mm": 160.0, "codigo_ibge": RECIFE_IBGE},
    )
    if res.status_code == 404:
        pytest.skip("Município Recife (2611606) não carregado no banco de testes.")

    assert res.status_code == 200, res.text
    body = res.json()
    delta = body["delta"]

    assert body["baseline"]["input_value"] == 80.0
    assert body["scenario"]["input_value"] == 160.0
    assert delta["affected_area_km2"] >= 0
    assert delta["affected_population"] >= 0
    assert delta["max_depth_m"] >= 0
    assert isinstance(delta["bairros_novos"], list)

    assert float(body["scenario"]["affected_area_km2"]) >= float(body["baseline"]["affected_area_km2"])
    scen_depth = (body["scenario"].get("simulation_meta") or {}).get("max_depth_m", 0)
    base_depth = (body["baseline"].get("simulation_meta") or {}).get("max_depth_m", 0)
    assert scen_depth >= base_depth
