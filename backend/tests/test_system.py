"""Testes do painel operacional /system."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config as config_module
import app.security.auth as auth_module
from main import app
from tests.conftest import requires_postgres


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_auth(monkeypatch):
    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", False)
    auth_module._USER_STORE = None
    yield
    auth_module._USER_STORE = None


@requires_postgres
def test_system_overview_auth_off(client: TestClient):
    res = client.get("/api/v1/system/overview")
    assert res.status_code == 200
    body = res.json()
    assert body["platform"]
    assert "checks" in body
    assert "integrations" in body
    assert "batch_coverage" in body
    assert "homologation" in body
    assert "score_pct" in body["homologation"]
    assert body["auth"]["enabled"] is False


@requires_postgres
def test_system_overview_requires_admin_when_auth_on(client: TestClient, monkeypatch):
    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_ADMIN_PASSWORD", "admin")
    monkeypatch.setattr(config_module.settings, "AUTH_GESTOR_PASSWORD", "gestor")
    monkeypatch.setattr(config_module.settings, "AUTH_LEITOR_PASSWORD", "leitor")
    auth_module._USER_STORE = None

    res = client.get("/api/v1/system/overview")
    assert res.status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "leitor", "password": "leitor"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    res_leitor = client.get(
        "/api/v1/system/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_leitor.status_code == 403

    admin = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert admin.status_code == 200
    token_admin = admin.json()["access_token"]
    res_admin = client.get(
        "/api/v1/system/overview",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["municipalities"]["piloto_ibge"]


def test_background_jobs_lifecycle(client: TestClient):
    res = client.post("/api/v1/system/jobs/onboarding-batch?limit=1&status=pendente")
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert job_id

    detail = client.get(f"/api/v1/system/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == job_id

    listing = client.get("/api/v1/system/jobs?limit=5")
    assert listing.status_code == 200
    assert any(item["id"] == job_id for item in listing.json()["items"])


def test_ctm_batch_job_enqueue(client: TestClient):
    res = client.post("/api/v1/system/jobs/ctm-batch")
    assert res.status_code == 200
    body = res.json()
    assert body["job_id"]
    assert body["job"]["type"] == "ctm_batch"


@requires_postgres
def test_data_catalog_national_auth_off(client: TestClient):
    res = client.get("/api/v1/data-catalog/national")
    # Sem seeds no banco de teste pode retornar 404; com seeds retorna 200
    assert res.status_code in (200, 404)
    if res.status_code == 200:
        body = res.json()
        assert "total_municipios" in body
        assert "bases" in body
        assert "municipios" in body
