"""Escopo multi-tenant por UF ou códigos IBGE — Fase 4.3."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from app.security.auth import Role, User


@dataclass(frozen=True)
class TenantScope:
    uf: str | None = None
    ibge_codes: frozenset[str] | None = None

    def allows(self, codigo_ibge: str, uf: str) -> bool:
        code = str(codigo_ibge).zfill(7)[:7]
        if self.ibge_codes is not None:
            return code in self.ibge_codes
        if self.uf is not None:
            return uf.upper() == self.uf.upper()
        return False


def multi_tenant_enabled() -> bool:
    return settings.MULTI_TENANT_ENABLED


def tenant_scope_for_user(user: User) -> TenantScope | None:
    """None = acesso nacional (admin ou multi-tenant desligado)."""
    from app.security.auth import Role

    if not multi_tenant_enabled():
        return None
    if user.role == Role.ADMIN:
        return None
    return TenantScope(uf=user.tenant_uf, ibge_codes=_codes_frozen(user.tenant_ibge_codes))


def can_access_municipio(user: User, codigo_ibge: str, uf: str) -> bool:
    scope = tenant_scope_for_user(user)
    if scope is None:
        return True
    return scope.allows(codigo_ibge, uf)


def _codes_frozen(codes: list[str] | None) -> frozenset[str] | None:
    if not codes:
        return None
    normalized = {str(code).zfill(7)[:7] for code in codes if str(code).strip()}
    return frozenset(normalized) if normalized else None


def _read_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def tenant_config_for_username(username: str, role: Role) -> tuple[str | None, list[str] | None]:
    """Resolve tenant a partir de variáveis de ambiente por usuário ou role."""
    from app.security.auth import Role as AuthRole

    key = username.upper().replace("-", "_")
    uf = _read_env(f"AUTH_TENANT_{key}_UF")
    ibge_raw = _read_env(f"AUTH_TENANT_{key}_IBGE")

    if role == AuthRole.GESTOR and not uf and not ibge_raw:
        uf = _read_env("AUTH_GESTOR_TENANT_UF")
        ibge_raw = ibge_raw or _read_env("AUTH_GESTOR_TENANT_IBGE")
    elif role == AuthRole.LEITOR and not uf and not ibge_raw:
        uf = _read_env("AUTH_LEITOR_TENANT_UF")
        ibge_raw = ibge_raw or _read_env("AUTH_LEITOR_TENANT_IBGE")

    codes = None
    if ibge_raw:
        codes = [part.strip() for part in ibge_raw.split(",") if part.strip()]
    return uf, codes
