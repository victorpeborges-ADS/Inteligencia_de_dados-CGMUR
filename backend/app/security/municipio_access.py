"""Acesso a municípios com isolamento multi-tenant."""

from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.orm import Query, Session

from app.config import settings
from app.models import Municipio, MunicipioSeed
from app.security.auth import User
from app.security.tenant import can_access_municipio, multi_tenant_enabled, tenant_scope_for_user
from app.services.audit_service import resolve_actor


def normalize_ibge(codigo_ibge: str) -> str:
    return str(codigo_ibge).strip().replace(".", "").zfill(7)[:7]


def assert_municipio_access(user: User, codigo_ibge: str, uf: str) -> None:
    if can_access_municipio(user, codigo_ibge, uf):
        return
    raise HTTPException(
        status_code=403,
        detail="Município fora do escopo do perfil (multi-tenant).",
    )


def get_accessible_municipio(
    db: Session,
    codigo_ibge: str | None = None,
    *,
    request: Request | None = None,
    user: User | None = None,
) -> Municipio:
    code = normalize_ibge(codigo_ibge or settings.PILOT_IBGE_CODE)
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise HTTPException(status_code=404, detail=f"Município IBGE {code} não encontrado.")
    actor = user or resolve_actor(request)
    assert_municipio_access(actor, muni.codigo_ibge, muni.uf)
    return muni


def get_accessible_municipio_by_id(
    db: Session,
    municipio_id: int,
    *,
    request: Request | None = None,
    user: User | None = None,
) -> Municipio:
    muni = db.query(Municipio).filter(Municipio.id == municipio_id).first()
    if not muni:
        raise HTTPException(status_code=404, detail=f"Município id={municipio_id} não encontrado.")
    actor = user or resolve_actor(request)
    assert_municipio_access(actor, muni.codigo_ibge, muni.uf)
    return muni


def assert_codigo_ibge_access(
    db: Session,
    codigo_ibge: str,
    *,
    request: Request | None = None,
    user: User | None = None,
) -> str:
    """Valida escopo sem exigir município carregado no PostGIS."""
    code = normalize_ibge(codigo_ibge)
    actor = user or resolve_actor(request)
    if not multi_tenant_enabled() or actor.role.value == "admin":
        return code

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if muni:
        assert_municipio_access(actor, muni.codigo_ibge, muni.uf)
        return code

    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == code).first()
    if seed:
        assert_municipio_access(actor, seed.codigo_ibge, seed.uf)
        return code

    scope = tenant_scope_for_user(actor)
    if scope is None:
        return code
    if scope.ibge_codes and code in scope.ibge_codes:
        return code
    raise HTTPException(status_code=403, detail="Município fora do escopo do perfil (multi-tenant).")


def filter_municipio_query(query: Query, user: User) -> Query:
    scope = tenant_scope_for_user(user)
    if scope is None:
        return query
    if scope.ibge_codes is not None:
        return query.filter(Municipio.codigo_ibge.in_(sorted(scope.ibge_codes)))
    if scope.uf is not None:
        return query.filter(Municipio.uf == scope.uf.upper())
    return query.filter(False)


def filter_seed_query(query: Query, user: User) -> Query:
    scope = tenant_scope_for_user(user)
    if scope is None:
        return query
    if scope.ibge_codes is not None:
        return query.filter(MunicipioSeed.codigo_ibge.in_(sorted(scope.ibge_codes)))
    if scope.uf is not None:
        return query.filter(MunicipioSeed.uf == scope.uf.upper())
    return query.filter(False)
