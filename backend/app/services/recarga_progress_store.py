"""Progresso de recarga municipal em Redis."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_PREFIX = "sinidu:recarga:"
_TTL = 7 * 86400


def _client():
    if not settings.JOB_STORE_REDIS:
        return None
    try:
        import redis

        return redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as exc:
        logger.debug("Redis recarga indisponível: %s", exc)
        return None


def _key(codigo_ibge: str) -> str:
    return f"{_PREFIX}{str(codigo_ibge).strip().zfill(7)[:7]}"


def save_recarga_status(codigo_ibge: str, payload: dict[str, Any]) -> None:
    client = _client()
    if not client:
        return
    try:
        client.setex(_key(codigo_ibge), _TTL, json.dumps(payload, ensure_ascii=False, default=str))
    except Exception as exc:
        logger.debug("Falha ao salvar recarga %s: %s", codigo_ibge, exc)


def load_recarga_status(codigo_ibge: str) -> dict[str, Any] | None:
    client = _client()
    if not client:
        return None
    try:
        raw = client.get(_key(codigo_ibge))
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug("Falha ao carregar recarga %s: %s", codigo_ibge, exc)
        return None


def init_recarga(codigo_ibge: str, fontes: list[str]) -> dict[str, Any]:
    payload = {
        "codigo_ibge": codigo_ibge,
        "status": "em_andamento",
        "progresso_pct": 0,
        "etapa_atual": "iniciando",
        "fontes": fontes,
        "etapas_concluidas": [],
        "iniciado_em": datetime.now(timezone.utc).isoformat(),
        "finalizado_em": None,
        "resultado": {},
        "erro": None,
    }
    save_recarga_status(codigo_ibge, payload)
    return payload


def update_recarga(codigo_ibge: str, **fields: Any) -> dict[str, Any]:
    current = load_recarga_status(codigo_ibge) or init_recarga(codigo_ibge, [])
    current.update(fields)
    save_recarga_status(codigo_ibge, current)
    return current
