"""Testes do policy gate (20a.3) e hardening de secrets (20a.2)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import config as config_module
from app.boot import validate_auth_secrets_for_environment, boot_status
from app.db import get_db
from app.security.policy_gate import require_human_confirm
import app.security.auth as auth_module
from main import app


def test_require_human_confirm_blocks_without_flag():
    with pytest.raises(HTTPException) as exc:
        require_human_confirm(False, action="contingency.activate")
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "human_confirm_required"


def test_require_human_confirm_allows_true():
    require_human_confirm(True, action="alert.disseminate")


def test_validate_auth_warns_default_secret(monkeypatch):
    boot_status.errors.clear()
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", False)
    monkeypatch.setattr(
        config_module.settings,
        "AUTH_JWT_SECRET",
        "sinidu-dev-secret-trocar-em-producao",
    )
    monkeypatch.setattr(config_module.settings, "AUTH_ADMIN_PASSWORD", "admin")
    validate_auth_secrets_for_environment()
    assert any("AUTH_JWT_SECRET" in e for e in boot_status.errors)


def test_validate_auth_fails_production_with_weak_secret(monkeypatch):
    boot_status.errors.clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_JWT_SECRET", "curto")
    monkeypatch.setattr(config_module.settings, "AUTH_ADMIN_PASSWORD", "forte-admin-xyz")
    with pytest.raises(RuntimeError, match="AUTH_JWT_SECRET"):
        validate_auth_secrets_for_environment()


def test_validate_auth_fails_production_default_passwords(monkeypatch):
    boot_status.errors.clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_JWT_SECRET", "x" * 40)
    monkeypatch.setattr(config_module.settings, "AUTH_ADMIN_PASSWORD", "admin")
    with pytest.raises(RuntimeError, match="Senha default"):
        validate_auth_secrets_for_environment()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", False)
    auth_module._USER_STORE = None

    def _override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def test_activate_plan_requires_confirm(client: TestClient):
    plan = MagicMock()
    plan.id = 7
    plan.municipio_id = 1
    plan.cenario_tipo = "INUNDACAO"
    plan.nivel_alerta = "LARANJA"
    plan.status = "RASCUNHO"
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = plan

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    with patch("app.api.contingency.get_accessible_municipio_by_id") as muni:
        muni.return_value = MagicMock(codigo_ibge="2611606")
        res = client.post("/api/v1/contingency/7/activate")
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "human_confirm_required"


def test_activate_plan_with_confirm(client: TestClient):
    plan = MagicMock()
    plan.id = 7
    plan.municipio_id = 1
    plan.cenario_tipo = "INUNDACAO"
    plan.nivel_alerta = "LARANJA"
    plan.status = "RASCUNHO"
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = plan
    db.query.return_value.filter.return_value.update.return_value = None

    def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db
    with (
        patch("app.api.contingency.get_accessible_municipio_by_id") as muni,
        patch("app.api.contingency.plan_to_dict", return_value={"id": 7, "status": "ATIVO"}),
        patch("app.api.contingency.log_audit"),
    ):
        muni.return_value = MagicMock(codigo_ibge="2611606")
        res = client.post("/api/v1/contingency/7/activate?confirm=true")
    assert res.status_code == 200
    assert res.json()["status"] == "ATIVO"


def test_disseminate_requires_confirm(client: TestClient):
    with patch("app.api.monitoring.assert_codigo_ibge_access"):
        res = client.post(
            "/api/v1/monitoring/disseminate/2611606",
            json={"nivel": "LARANJA", "mensagem": "teste", "canais": ["checklist_dc"]},
        )
    assert res.status_code == 409
