"""Testes unitários do módulo de autenticação."""

from __future__ import annotations

import pytest

from app.security.auth import (
    Role,
    authenticate_user,
    create_access_token,
    decode_token,
    required_role_for_request,
)


@pytest.fixture(autouse=True)
def reset_user_store(monkeypatch):
    import app.security.auth as auth_module
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_ADMIN_PASSWORD", "admin123")
    monkeypatch.setattr(config_module.settings, "AUTH_GESTOR_PASSWORD", "gestor123")
    monkeypatch.setattr(config_module.settings, "AUTH_LEITOR_PASSWORD", "leitor123")
    auth_module._USER_STORE = None
    yield
    auth_module._USER_STORE = None


def test_authenticate_admin():
    user = authenticate_user("admin", "admin123")
    assert user is not None
    assert user.role == Role.ADMIN


def test_authenticate_invalid_password():
    assert authenticate_user("admin", "wrong") is None


def test_token_roundtrip():
    from app.security.auth import User

    user = User(username="gestor", role=Role.GESTOR)
    token = create_access_token(user)
    decoded = decode_token(token)
    assert decoded.username == "gestor"
    assert decoded.role == Role.GESTOR


def test_required_role_public_health():
    assert required_role_for_request("GET", "/health/live") is None


def test_required_role_get_api_needs_leitor():
    assert required_role_for_request("GET", "/api/v1/indicators/executive") == Role.LEITOR


def test_required_role_post_onboarding_needs_gestor():
    assert required_role_for_request("POST", "/api/v1/onboarding/run") == Role.GESTOR


def test_required_role_sync_needs_admin():
    assert required_role_for_request("POST", "/api/v1/integrations/sync") == Role.ADMIN


def test_auth_disabled_skips_requirement(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", False)
    assert required_role_for_request("GET", "/api/v1/indicators/executive") is None
