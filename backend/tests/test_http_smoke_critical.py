"""Testes HTTP smoke — routers críticos (Fase 20a.1).

Sem Postgres: overrides de get_db + patches dos serviços.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import config as config_module
from app.db import get_db
import app.security.auth as auth_module
from main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", False)
    monkeypatch.setattr(config_module.settings, "REPORTS_DIR", str(tmp_path))
    auth_module._USER_STORE = None

    def _override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    auth_module._USER_STORE = None


def test_integrations_status_http(client: TestClient):
    with patch("app.api.integrations.IntegrationOrchestrator") as orch_cls:
        orch = orch_cls.return_value
        orch.status.return_value = [
            {"source": "ibge", "status": "ok", "records_count": 6, "last_sync": None},
        ]
        res = client.get("/api/v1/integrations/status")
    assert res.status_code == 200
    assert "sources" in res.json()
    assert res.json()["sources"][0]["source"] == "ibge"


def test_monitoring_map_overview_http(client: TestClient):
    with patch("app.api.monitoring.filter_municipio_query") as fq:
        q = MagicMock()
        q.order_by.return_value.all.return_value = []
        fq.return_value = q
        res = client.get("/api/v1/monitoring/map-overview")
    assert res.status_code == 200
    body = res.json()
    assert body["total_municipios"] == 0
    assert body["municipios"] == []


def test_export_kmz_http(client: TestClient, tmp_path: Path):
    muni = SimpleNamespace(codigo_ibge="2611606", nome="Recife", uf="PE", id=1)
    sim = {
        "scenario_type": "ExtremeRainfall",
        "input_value": 120.0,
        "geometry": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[-34.9, -8.1], [-34.8, -8.1], [-34.8, -8.0], [-34.9, -8.1]]],
                    },
                    "properties": {"layer_type": "flood_band", "depth_band": "leve"},
                }
            ],
        },
    }
    with (
        patch("app.api.simulations.get_accessible_municipio", return_value=muni),
        patch("app.api.simulations.log_audit"),
    ):
        res = client.post(
            "/api/v1/simulations/export/kmz",
            json={"codigo_ibge": "2611606", "simulation": sim},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["format"] == "kmz"
    assert body["nome_arquivo"].endswith(".kmz")
    assert "download_url" in body


def test_agent_tools_are_read_only():
    """20a.3 — agente não deve expor tools de escrita sensível."""
    from app.services.contextual_agent_tools import TOOL_DEFINITIONS

    names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    forbidden = ("activate_", "disseminate_", "sync_", "delete_", "send_")
    for name in names:
        assert name.startswith(("get_", "recommend_", "explain_")), name
        assert not any(name.startswith(p) for p in forbidden)
