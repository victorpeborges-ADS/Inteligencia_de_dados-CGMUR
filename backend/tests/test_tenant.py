"""Testes multi-tenant — Fase 4.3."""

from __future__ import annotations

import pytest

from app.security.auth import Role, User
from app.security.tenant import TenantScope, can_access_municipio, tenant_config_for_username, tenant_scope_for_user


@pytest.fixture(autouse=True)
def enable_multi_tenant(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "MULTI_TENANT_ENABLED", True)


def test_tenant_scope_by_uf():
    user = User(username="gestor_pe", role=Role.GESTOR, tenant_uf="PE")
    scope = tenant_scope_for_user(user)
    assert scope is not None
    assert scope.allows("2611606", "PE")
    assert not scope.allows("3550308", "SP")


def test_tenant_scope_by_ibge_list():
    user = User(username="gestor", role=Role.GESTOR, tenant_ibge_codes=["2611606", "2806701"])
    scope = tenant_scope_for_user(user)
    assert scope is not None
    assert scope.allows("2611606", "PE")
    assert scope.allows("2806701", "SE")
    assert not scope.allows("3550308", "SP")


def test_admin_has_no_scope():
    user = User(username="admin", role=Role.ADMIN)
    assert tenant_scope_for_user(user) is None
    assert can_access_municipio(user, "3550308", "SP")


def test_tenant_config_from_env(monkeypatch):
    monkeypatch.setenv("AUTH_TENANT_GESTOR_UF", "SE")
    uf, codes = tenant_config_for_username("gestor", Role.GESTOR)
    assert uf == "SE"
    assert codes is None


def test_tenant_scope_disabled(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "MULTI_TENANT_ENABLED", False)
    user = User(username="gestor", role=Role.GESTOR, tenant_uf="PE")
    assert tenant_scope_for_user(user) is None
    assert can_access_municipio(user, "3550308", "SP")
