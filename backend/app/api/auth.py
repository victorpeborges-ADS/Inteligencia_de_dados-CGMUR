"""Endpoints de autenticação."""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.security.auth import Role, User, authenticate_user, create_access_token, get_current_user
from app.security.oidc import (
    build_authorization_url,
    complete_oidc_login,
    consume_authorization_state,
    create_authorization_state,
    oidc_configured,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    expires_hours: int = 12
    tenant_uf: str | None = None
    tenant_ibge_codes: list[str] = Field(default_factory=list)


class AuthStatusResponse(BaseModel):
    enabled: bool
    roles: list[str]
    multi_tenant_enabled: bool
    oidc_enabled: bool
    oidc_login_url: str | None = None
    password_login_enabled: bool = True


class MeResponse(BaseModel):
    username: str
    role: str
    tenant_uf: str | None = None
    tenant_ibge_codes: list[str] = Field(default_factory=list)


class OidcStatusResponse(BaseModel):
    configured: bool
    issuer: str | None = None
    login_url: str | None = None


def _login_response(user: User) -> LoginResponse:
    return LoginResponse(
        access_token=create_access_token(user),
        username=user.username,
        role=user.role.value,
        tenant_uf=user.tenant_uf,
        tenant_ibge_codes=user.tenant_ibge_codes or [],
    )


@router.get("/status", response_model=AuthStatusResponse)
def auth_status():
    oidc_ready = oidc_configured()
    return AuthStatusResponse(
        enabled=settings.AUTH_ENABLED,
        roles=[r.value for r in Role],
        multi_tenant_enabled=settings.MULTI_TENANT_ENABLED,
        oidc_enabled=oidc_ready,
        oidc_login_url=f"{settings.API_V1_STR}/auth/oidc/login" if oidc_ready else None,
        password_login_enabled=settings.AUTH_PASSWORD_LOGIN_ENABLED,
    )


@router.get("/oidc/status", response_model=OidcStatusResponse)
def oidc_status():
    ready = oidc_configured()
    return OidcStatusResponse(
        configured=ready,
        issuer=settings.OIDC_ISSUER_URL or None,
        login_url=f"{settings.API_V1_STR}/auth/oidc/login" if ready else None,
    )


@router.get("/oidc/login")
def oidc_login():
    if not oidc_configured():
        raise HTTPException(status_code=503, detail="OIDC não configurado.")
    state = create_authorization_state()
    return RedirectResponse(build_authorization_url(state), status_code=302)


@router.get("/oidc/callback")
def oidc_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    if error:
        raise HTTPException(status_code=400, detail=f"OIDC recusado: {error}")
    if not code or not state or not consume_authorization_state(state):
        raise HTTPException(status_code=400, detail="State OIDC inválido ou expirado.")

    try:
        user, jwt_token = complete_oidc_login(code)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Falha na troca OIDC: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao concluir login OIDC: {exc}") from exc

    params = urlencode(
        {
            "access_token": jwt_token,
            "username": user.username,
            "role": user.role.value,
        }
    )
    base = settings.OIDC_FRONTEND_REDIRECT.rstrip("/")
    separator = "&" if "?" in base else "?"
    return RedirectResponse(f"{base}{separator}{params}", status_code=302)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    if not settings.AUTH_ENABLED:
        return LoginResponse(
            access_token="dev",
            username="dev",
            role=Role.ADMIN.value,
        )

    if not settings.AUTH_PASSWORD_LOGIN_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Login por senha desabilitado. Use OIDC/SSO.",
        )

    user = authenticate_user(body.username, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
        )

    return _login_response(user)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(
        username=user.username,
        role=user.role.value,
        tenant_uf=user.tenant_uf,
        tenant_ibge_codes=user.tenant_ibge_codes or [],
    )
