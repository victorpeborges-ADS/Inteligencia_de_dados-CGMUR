"""Testes OIDC — mapeamento de roles e state."""

from __future__ import annotations

import pytest

from app.security.auth import Role
from app.security.oidc import (
    consume_authorization_state,
    create_authorization_state,
    map_role_from_claims,
    oidc_configured,
    user_from_oidc_claims,
    _decode_jwt_payload_unverified,
)


@pytest.fixture(autouse=True)
def oidc_env(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "OIDC_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "OIDC_ISSUER_URL", "https://idp.example/realms/mcid")
    monkeypatch.setattr(config_module.settings, "OIDC_CLIENT_ID", "sinidu")
    monkeypatch.setattr(config_module.settings, "OIDC_REDIRECT_URI", "http://localhost/api/v1/auth/oidc/callback")
    monkeypatch.setattr(config_module.settings, "OIDC_ADMIN_GROUPS", "sinidu-admin")
    monkeypatch.setattr(config_module.settings, "OIDC_GESTOR_GROUPS", "sinidu-gestor")
    monkeypatch.setattr(config_module.settings, "OIDC_LEITOR_GROUPS", "sinidu-leitor")
    monkeypatch.setattr(config_module.settings, "OIDC_DEFAULT_ROLE", "leitor")
    monkeypatch.setattr(config_module.settings, "MULTI_TENANT_ENABLED", False)


def test_oidc_configured():
    assert oidc_configured() is True


def test_map_role_admin_from_groups():
    role = map_role_from_claims({"groups": ["sinidu-admin", "outro"]})
    assert role == Role.ADMIN


def test_map_role_gestor_from_keycloak_realm_access():
    role = map_role_from_claims({"realm_access": {"roles": ["sinidu-gestor"]}})
    assert role == Role.GESTOR


def test_user_from_oidc_claims_username():
    user = user_from_oidc_claims({"preferred_username": "analista.pe", "groups": ["sinidu-leitor"]})
    assert user.username == "analista.pe"
    assert user.role == Role.LEITOR


def test_oidc_state_roundtrip():
    state = create_authorization_state()
    assert consume_authorization_state(state) is True
    assert consume_authorization_state(state) is False


def test_decode_id_token_payload():
    import base64
    import json

    raw = base64.urlsafe_b64encode(
        json.dumps({"preferred_username": "analista", "groups": ["sinidu-admin"]}).encode()
    ).decode().rstrip("=")
    token = f"eyJhbGciOiJub25lIn0.{raw}.sig"
    claims = _decode_jwt_payload_unverified(token)
    assert claims["preferred_username"] == "analista"
    assert claims["groups"] == ["sinidu-admin"]


def test_user_from_id_token_style_claims():
    user = user_from_oidc_claims(
        {"preferred_username": "admin.sinidu", "realm_access": {"roles": ["sinidu-admin"]}}
    )
    assert user.username == "admin.sinidu"
    assert user.role == Role.ADMIN
