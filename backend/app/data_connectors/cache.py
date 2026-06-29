from __future__ import annotations

import json
import os
from typing import Any, Optional

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None

_redis_client = None
_memory_cache: dict[str, tuple[float, str]] = {}


def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if redis is None:
        return None
    url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        _redis_client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        _redis_client.ping()
    except Exception:
        _redis_client = None
    return _redis_client


def cache_get_json(key: str) -> Optional[Any]:
    client = get_redis_client()
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass

    import time

    entry = _memory_cache.get(key)
    if not entry:
        return None
    expires_at, raw = entry
    if expires_at < time.time():
        _memory_cache.pop(key, None)
        return None
    return json.loads(raw)


def cache_set_json(key: str, value: Any, ttl: int = 3600) -> None:
    raw = json.dumps(value, ensure_ascii=False)
    client = get_redis_client()
    if client is not None:
        try:
            client.setex(key, ttl, raw)
            return
        except Exception:
            pass

    import time

    _memory_cache[key] = (time.time() + ttl, raw)
