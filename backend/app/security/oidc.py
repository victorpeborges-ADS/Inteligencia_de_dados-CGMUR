"""OpenID Connect (Keycloak / gov.br) — emite JWT Sinidu após login federado."""

from __future__ import annotations

import base64
import json
import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.data_connectors.cache import cache_get_json, cache_set_json
from app.security.auth import Role, User, create_access_token
from app.security.tenant import tenant_config_for_username

logger = logging.getLogger(__name__)

_STATE_TTL_SECONDS = 600
_DISCOVERY_TTL_SECONDS = 3600


def _decode_jwt_payload_unverified(token: str) -> dict[str, Any]:
    """Extrai claims do payload JWT sem verificar assinatura (claims já validados pelo IdP na troca do code)."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        segment = parts[1]
        padding = "=" * (-len(segment) % 4)
        payload = base64.urlsafe_b64decode(segment + padding)
        data = json.loads(payload)
        return data if isinstance(data, dict) else {}
    except (ValueError, json.JSONDecodeError, TypeError) as exc:
        logger.warning("Falha ao decodificar id_token: %s", exc)
        return {}


def oidc_configured() -> bool:
    return bool(
        settings.OIDC_ENABLED
        and settings.OIDC_ISSUER_URL
        and settings.OIDC_CLIENT_ID
        and settings.OIDC_REDIRECT_URI
    )


def _discovery_cache_key() -> str:
    return f"oidc:discovery:{settings.OIDC_ISSUER_URL.rstrip('/')}"


def fetch_discovery() -> dict[str, Any]:
    cached = cache_get_json(_discovery_cache_key())
    if cached:
        return cached

    issuer = settings.OIDC_ISSUER_URL.rstrip("/")
    url = f"{issuer}/.well-known/openid-configuration"
    with httpx.Client(timeout=15.0) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()

    cache_set_json(_discovery_cache_key(), data, ttl=_DISCOVERY_TTL_SECONDS)
    return data


def create_authorization_state() -> str:
    state = secrets.token_urlsafe(32)
    cache_set_json(f"oidc:state:{state}", True, ttl=_STATE_TTL_SECONDS)
    return state


def consume_authorization_state(state: str) -> bool:
    if not state:
        return False
    key = f"oidc:state:{state}"
    valid = cache_get_json(key)
    if not valid:
        return False
    cache_set_json(key, False, ttl=1)
    return True


def build_authorization_url(state: str) -> str:
    discovery = fetch_discovery()
    params = {
        "client_id": settings.OIDC_CLIENT_ID,
        "response_type": "code",
        "scope": settings.OIDC_SCOPES,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "state": state,
    }
    return f"{discovery['authorization_endpoint']}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    discovery = fetch_discovery()
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "client_id": settings.OIDC_CLIENT_ID,
    }
    if settings.OIDC_CLIENT_SECRET:
        payload["client_secret"] = settings.OIDC_CLIENT_SECRET

    with httpx.Client(timeout=15.0) as client:
        response = client.post(discovery["token_endpoint"], data=payload)
        response.raise_for_status()
        return response.json()


def fetch_userinfo(access_token: str) -> dict[str, Any]:
    discovery = fetch_discovery()
    userinfo_endpoint = discovery.get("userinfo_endpoint")
    if not userinfo_endpoint:
        return {}

    with httpx.Client(timeout=15.0) as client:
        response = client.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


def _claim_groups(claims: dict[str, Any]) -> list[str]:
    raw = claims.get(settings.OIDC_ROLE_CLAIM)
    if raw is None and "realm_access" in claims:
        raw = claims["realm_access"].get("roles")
    if raw is None and "resource_access" in claims:
        # Keycloak / gov.br — roles por client
        collected: list[str] = []
        client_id = settings.OIDC_CLIENT_ID
        if client_id and client_id in claims["resource_access"]:
            collected.extend(claims["resource_access"][client_id].get("roles") or [])
        for resource in claims["resource_access"].values():
            if isinstance(resource, dict):
                collected.extend(resource.get("roles") or [])
        raw = collected
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, dict):
        return [str(key) for key in raw.keys()]
    return [str(item) for item in raw]


def _split_groups(value: str) -> set[str]:
    return {part.strip() for part in value.split(",") if part.strip()}


def map_role_from_claims(claims: dict[str, Any]) -> Role:
    groups = set(_claim_groups(claims))
    if groups & _split_groups(settings.OIDC_ADMIN_GROUPS):
        return Role.ADMIN
    if groups & _split_groups(settings.OIDC_GESTOR_GROUPS):
        return Role.GESTOR
    if groups & _split_groups(settings.OIDC_LEITOR_GROUPS):
        return Role.LEITOR
    try:
        return Role(settings.OIDC_DEFAULT_ROLE)
    except ValueError:
        return Role.LEITOR


def user_from_oidc_claims(claims: dict[str, Any]) -> User:
    username = (
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("sub")
        or "oidc-user"
    )
    role = map_role_from_claims(claims)
    tenant_uf = claims.get(settings.OIDC_TENANT_UF_CLAIM) or None
    tenant_ibge_raw = claims.get(settings.OIDC_TENANT_IBGE_CLAIM)
    tenant_ibge_codes = None
    if tenant_ibge_raw:
        if isinstance(tenant_ibge_raw, str):
            tenant_ibge_codes = [part.strip() for part in tenant_ibge_raw.split(",") if part.strip()]
        elif isinstance(tenant_ibge_raw, list):
            tenant_ibge_codes = [str(code) for code in tenant_ibge_raw]

    if not tenant_uf and not tenant_ibge_codes:
        env_uf, env_ibge = tenant_config_for_username(str(username), role)
        tenant_uf = tenant_uf or env_uf
        tenant_ibge_codes = tenant_ibge_codes or env_ibge

    return User(
        username=str(username),
        role=role,
        tenant_uf=str(tenant_uf) if tenant_uf else None,
        tenant_ibge_codes=tenant_ibge_codes,
    )


def complete_oidc_login(code: str) -> tuple[User, str]:
    tokens = exchange_code_for_tokens(code)
    access_token = tokens.get("access_token", "")

    id_token_claims: dict[str, Any] = {}
    if tokens.get("id_token"):
        id_token_claims = _decode_jwt_payload_unverified(tokens["id_token"])

    userinfo = fetch_userinfo(access_token) if access_token else {}
    claims = {**id_token_claims, **userinfo}
    if not claims and tokens.get("id_token"):
        claims = {"sub": tokens.get("id_token", "")[:32]}

    user = user_from_oidc_claims(claims)
    jwt_token = create_access_token(user)
    return user, jwt_token


def check_oidc_connectivity() -> tuple[bool, str, dict[str, Any]]:
    """Verifica se o IdP responde ao discovery document."""
    if not oidc_configured():
        return False, "OIDC desabilitado ou incompleto", {}

    try:
        discovery = fetch_discovery()
        return True, "ok", {
            "issuer": settings.OIDC_ISSUER_URL,
            "authorization_endpoint": discovery.get("authorization_endpoint"),
            "token_endpoint": discovery.get("token_endpoint"),
        }
    except Exception as exc:
        return False, str(exc), {"issuer": settings.OIDC_ISSUER_URL}
