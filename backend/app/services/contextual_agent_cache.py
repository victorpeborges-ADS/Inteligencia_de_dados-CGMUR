"""Cache do agente contextual (bundle municipal + respostas frequentes)."""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

from app.data_connectors.cache import cache_get_json, cache_set_json

BUNDLE_CACHE_TTL = int(os.getenv("CONTEXTUAL_AGENT_BUNDLE_TTL", str(30 * 60)))
RESPONSE_CACHE_TTL = int(os.getenv("CONTEXTUAL_AGENT_RESPONSE_TTL", str(2 * 3600)))
CACHE_ENABLED = os.getenv("CONTEXTUAL_AGENT_CACHE_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)


def _ibge(code: str) -> str:
    return str(code).strip().zfill(7)[:7]


def bundle_cache_key(codigo_ibge: str) -> str:
    return f"sinidu:agent:bundle:{_ibge(codigo_ibge)}"


def _normalize_message(message: str) -> str:
    text = message.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text[:500]


def response_cache_key(codigo_ibge: str, pagina: str, message: str) -> str:
    norm = _normalize_message(message)
    digest = hashlib.sha256(f"{_ibge(codigo_ibge)}|{pagina}|{norm}".encode()).hexdigest()[:24]
    return f"sinidu:agent:resp:{digest}"


def get_cached_bundle(codigo_ibge: str) -> dict[str, Any] | None:
    if not CACHE_ENABLED:
        return None
    data = cache_get_json(bundle_cache_key(codigo_ibge))
    return data if isinstance(data, dict) else None


def set_cached_bundle(codigo_ibge: str, bundle: dict[str, Any]) -> None:
    if not CACHE_ENABLED:
        return
    cache_set_json(bundle_cache_key(codigo_ibge), bundle, ttl=BUNDLE_CACHE_TTL)


def get_cached_response(codigo_ibge: str, pagina: str, message: str) -> dict[str, Any] | None:
    if not CACHE_ENABLED:
        return None
    data = cache_get_json(response_cache_key(codigo_ibge, pagina, message))
    return data if isinstance(data, dict) and data.get("response") else None


def set_cached_response(
    codigo_ibge: str,
    pagina: str,
    message: str,
    *,
    response: str,
    ai_provider: str | None = None,
    ai_model: str | None = None,
) -> None:
    if not CACHE_ENABLED or not response.strip():
        return
    cache_set_json(
        response_cache_key(codigo_ibge, pagina, message),
        {
            "response": response.strip(),
            "ai_provider": ai_provider,
            "ai_model": ai_model,
            "from_cache": True,
        },
        ttl=RESPONSE_CACHE_TTL,
    )


def municipal_context_cache_key(codigo_ibge: str) -> str:
    return f"sinidu:assistant:ctx:{_ibge(codigo_ibge)}"


def get_cached_municipal_context(codigo_ibge: str) -> dict[str, Any] | None:
    if not CACHE_ENABLED:
        return None
    data = cache_get_json(municipal_context_cache_key(codigo_ibge))
    return data if isinstance(data, dict) else None


def set_cached_municipal_context(codigo_ibge: str, context: dict[str, Any]) -> None:
    if not CACHE_ENABLED:
        return
    cache_set_json(municipal_context_cache_key(codigo_ibge), context, ttl=BUNDLE_CACHE_TTL)
