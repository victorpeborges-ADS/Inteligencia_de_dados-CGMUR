"""Autenticação JWT com roles — desligável via AUTH_ENABLED=false (dev)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12


class Role(str, Enum):
    ADMIN = "admin"
    GESTOR = "gestor_municipal"
    LEITOR = "leitor"


ROLE_LEVEL = {
    Role.LEITOR: 1,
    Role.GESTOR: 2,
    Role.ADMIN: 3,
}


class TokenPayload(BaseModel):
    sub: str
    role: Role
    exp: int


class User(BaseModel):
    username: str
    role: Role
    tenant_uf: str | None = None
    tenant_ibge_codes: list[str] | None = None


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _build_user_store() -> dict[str, dict]:
    """Usuários definidos por variáveis de ambiente (MVP sem tabela users)."""
    from app.security.tenant import tenant_config_for_username

    store: dict[str, dict] = {}

    def add(username: str, password: str, role: Role) -> None:
        if username and password:
            tenant_uf, tenant_ibge = tenant_config_for_username(username, role)
            store[username] = {
                "password_hash": _hash_password(password),
                "role": role,
                "tenant_uf": tenant_uf,
                "tenant_ibge_codes": tenant_ibge,
            }

    add(settings.AUTH_ADMIN_USER, settings.AUTH_ADMIN_PASSWORD, Role.ADMIN)
    add(settings.AUTH_GESTOR_USER, settings.AUTH_GESTOR_PASSWORD, Role.GESTOR)
    add(settings.AUTH_LEITOR_USER, settings.AUTH_LEITOR_PASSWORD, Role.LEITOR)
    return store


_USER_STORE: dict[str, dict] | None = None


def _get_user_store() -> dict[str, dict]:
    global _USER_STORE
    if _USER_STORE is None:
        _USER_STORE = _build_user_store()
    return _USER_STORE


def authenticate_user(username: str, password: str) -> User | None:
    store = _get_user_store()
    record = store.get(username)
    if not record or not verify_password(password, record["password_hash"]):
        return None
    return User(
        username=username,
        role=record["role"],
        tenant_uf=record.get("tenant_uf"),
        tenant_ibge_codes=record.get("tenant_ibge_codes"),
    )


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user.username,
        "role": user.role.value,
        "exp": expire,
        "tenant_uf": user.tenant_uf,
        "tenant_ibge": user.tenant_ibge_codes or [],
    }
    return jwt.encode(payload, settings.AUTH_JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> User:
    try:
        data = jwt.decode(token, settings.AUTH_JWT_SECRET, algorithms=[ALGORITHM])
        ibge_raw = data.get("tenant_ibge") or []
        ibge_codes = [str(code) for code in ibge_raw if str(code).strip()] or None
        return User(
            username=data["sub"],
            role=Role(data["role"]),
            tenant_uf=data.get("tenant_uf"),
            tenant_ibge_codes=ibge_codes,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if not settings.AUTH_ENABLED:
        return User(username="dev", role=Role.ADMIN)

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(credentials.credentials)


def require_role(min_role: Role):
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not settings.AUTH_ENABLED:
            return user
        if ROLE_LEVEL[user.role] < ROLE_LEVEL[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão insuficiente (requer {min_role.value})",
            )
        return user

    return dependency


# Paths públicos mesmo com auth ligado
PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/login",
    "/api/v1/auth/status",
}

AUTH_PUBLIC_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/status",
    "/api/v1/auth/oidc/login",
    "/api/v1/auth/oidc/callback",
    "/api/v1/auth/oidc/status",
}

PUBLIC_PREFIXES = (
    "/health",
    "/metrics",
    "/static/",
)


def _is_public_path(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


# POST/PUT que exigem gestor_municipal ou superior
GESTOR_WRITE_PREFIXES = (
    "/api/v1/onboarding/",
    "/api/v1/geoportal/",
    "/api/v1/reports/",
    "/api/v1/diagnostic/",
    "/api/v1/action-plan/",
    "/api/v1/simulations/",
    "/api/v1/contingency/",
    "/api/v1/predictions/",
    "/api/v1/maturity/",
    "/api/v1/terrain/",
    "/api/v1/assistant/chat",
    "/api/v1/assistant/providers/status",
    "/api/v1/assistant/providers/test",
)

ADMIN_WRITE_PATHS = {
    ("POST", "/api/v1/integrations/sync"),
}


def required_role_for_request(method: str, path: str) -> Role | None:
    """None = sem auth necessário."""
    if not settings.AUTH_ENABLED:
        return None
    if _is_public_path(path):
        return None
    if path in AUTH_PUBLIC_PATHS:
        return None
    if path.startswith("/api/v1/auth/"):
        return Role.LEITOR
    if path.startswith("/ws/"):
        return None

    for admin_method, admin_path in ADMIN_WRITE_PATHS:
        if method == admin_method and path == admin_path:
            return Role.ADMIN

    if method in ("POST", "PUT", "PATCH", "DELETE"):
        if any(path.startswith(prefix) for prefix in GESTOR_WRITE_PREFIXES):
            return Role.GESTOR
        if path.startswith("/api/v1/"):
            return Role.GESTOR

    if method == "GET" and path.startswith("/api/v1/"):
        return Role.LEITOR

    return None


def extract_bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.query_params.get("token")


def authorize_request(request: Request) -> User | None:
    role_needed = required_role_for_request(request.method, request.url.path)
    if role_needed is None:
        return None

    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = decode_token(token)
    if ROLE_LEVEL[user.role] < ROLE_LEVEL[role_needed]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permissão insuficiente (requer {role_needed.value})",
        )
    return user
