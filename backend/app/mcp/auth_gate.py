"""Auth e rate-limit para o servidor MCP Sinidu (20c.2).

Read-only por design — sem tools de escrita.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import HTTPException

from app.security.auth import Role, User, decode_token


class McpAuthError(PermissionError):
    """Falha de autenticação/autorização do MCP."""


_rate_lock = threading.Lock()
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


def mcp_rate_limit_per_minute() -> int:
    return max(1, int(os.getenv("SINIDU_MCP_RATE_LIMIT_PER_MIN", "60")))


def _check_rate_limit(key: str) -> None:
    limit = mcp_rate_limit_per_minute()
    now = time.monotonic()
    window = 60.0
    with _rate_lock:
        bucket = _rate_buckets[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise McpAuthError(
                f"Rate limit MCP excedido ({limit}/min). Aguarde e tente de novo."
            )
        bucket.append(now)


def resolve_mcp_user(*, token: str | None = None) -> User:
    """Resolve usuário MCP via JWT ou token estático de equipe.

    Ordem:
      1. `token` explícito (argumento da tool / Bearer)
      2. env `SINIDU_MCP_JWT`
      3. env `SINIDU_MCP_TOKEN` (shared secret → role leitor admin-like)
      4. `SINIDU_MCP_ALLOW_ANON=1` → user dev (só testes locais)
    """
    candidate = (token or "").strip() or (os.getenv("SINIDU_MCP_JWT") or "").strip()
    static = (os.getenv("SINIDU_MCP_TOKEN") or "").strip()
    allow_anon = os.getenv("SINIDU_MCP_ALLOW_ANON", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    user: User | None = None

    if candidate:
        if static and candidate == static:
            user = User(username="mcp_team", role=Role.ADMIN)
        else:
            try:
                user = decode_token(candidate)
            except HTTPException as exc:
                raise McpAuthError(str(exc.detail)) from exc
    elif static:
        # Sem token na chamada, mas secret configurado: exige que o host
        # injete SINIDU_MCP_TOKEN no ambiente do processo (Cursor mcp.json).
        user = User(username="mcp_team", role=Role.ADMIN)
    elif allow_anon:
        user = User(username="mcp_anon", role=Role.LEITOR)
    else:
        raise McpAuthError(
            "Autenticação MCP necessária. Configure SINIDU_MCP_TOKEN "
            "(ou SINIDU_MCP_JWT / argumento token)."
        )

    _check_rate_limit(user.username)
    return user


def assert_read_only_tool(name: str) -> None:
    """Bloqueia nomes de tools sensíveis mesmo se alguém registrar por engano."""
    forbidden_prefixes = (
        "activate_",
        "disseminate_",
        "sync_",
        "delete_",
        "send_",
        "generate_",
        "bootstrap_",
        "write_",
        "create_",
        "update_",
    )
    lowered = name.lower()
    if any(lowered.startswith(p) for p in forbidden_prefixes):
        raise McpAuthError(f"Tool de escrita bloqueada no MCP: {name}")


def json_safe(payload: Any) -> Any:
    """Garante estrutura serializável (datas → iso)."""
    if payload is None or isinstance(payload, (str, int, float, bool)):
        return payload
    if isinstance(payload, dict):
        return {str(k): json_safe(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [json_safe(v) for v in payload]
    if hasattr(payload, "isoformat"):
        try:
            return payload.isoformat()
        except Exception:
            return str(payload)
    return str(payload)
