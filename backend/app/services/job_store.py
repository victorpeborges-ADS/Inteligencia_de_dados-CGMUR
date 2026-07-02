"""Persistência opcional de jobs administrativos em Redis."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_KEY_PREFIX = "sinidu:jobs:"
_INDEX_KEY = "sinidu:jobs:index"
_TTL_SECONDS = 7 * 86400


def _enabled() -> bool:
    return settings.JOB_STORE_REDIS


def _client():
    if not _enabled():
        return None
    try:
        import redis

        return redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as exc:
        logger.warning("Redis indisponível para job store: %s", exc)
        return None


def save_job(job: dict[str, Any]) -> None:
    client = _client()
    if not client:
        return
    job_id = job.get("id")
    if not job_id:
        return
    try:
        payload = json.dumps(job, ensure_ascii=False, default=str)
        client.setex(f"{_KEY_PREFIX}{job_id}", _TTL_SECONDS, payload)
        client.zadd(_INDEX_KEY, {job_id: _created_ts(job)})
        client.expire(_INDEX_KEY, _TTL_SECONDS)
    except Exception as exc:
        logger.debug("Falha ao persistir job %s: %s", job_id, exc)


def load_job(job_id: str) -> dict[str, Any] | None:
    client = _client()
    if not client:
        return None
    try:
        raw = client.get(f"{_KEY_PREFIX}{job_id}")
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug("Falha ao carregar job %s: %s", job_id, exc)
        return None


def list_persisted_jobs(limit: int = 20) -> list[dict[str, Any]]:
    client = _client()
    if not client:
        return []
    try:
        ids = client.zrevrange(_INDEX_KEY, 0, max(limit - 1, 0))
        rows: list[dict[str, Any]] = []
        for job_id in ids:
            job = load_job(job_id)
            if job:
                rows.append(job)
        return rows
    except Exception as exc:
        logger.debug("Falha ao listar jobs Redis: %s", exc)
        return []


def _created_ts(job: dict[str, Any]) -> float:
    from datetime import datetime

    raw = job.get("created_at") or ""
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0
