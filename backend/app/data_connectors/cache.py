from __future__ import annotations

import base64
import json
import os
import time
from typing import Any, Optional

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None

_redis_client = None
_redis_binary = None
_memory_cache: dict[str, tuple[float, str]] = {}
_memory_bytes: dict[str, tuple[float, bytes]] = {}


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


def get_redis_binary():
    """Cliente Redis sem decode — para MVT/GLB."""
    global _redis_binary
    if _redis_binary is not None:
        return _redis_binary
    if redis is None:
        return None
    url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        _redis_binary = redis.from_url(url, decode_responses=False, socket_connect_timeout=2)
        _redis_binary.ping()
    except Exception:
        _redis_binary = None
    return _redis_binary


def cache_get_json(key: str) -> Optional[Any]:
    client = get_redis_client()
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass

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

    _memory_cache[key] = (time.time() + ttl, raw)


def cache_get_bytes(key: str) -> Optional[bytes]:
    client = get_redis_binary()
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                return bytes(raw)
        except Exception:
            pass

    wrapped = cache_get_json(f"{key}:b64")
    if isinstance(wrapped, dict) and wrapped.get("b64"):
        try:
            return base64.b64decode(wrapped["b64"])
        except Exception:
            pass

    entry = _memory_bytes.get(key)
    if not entry:
        return None
    expires_at, raw = entry
    if expires_at < time.time():
        _memory_bytes.pop(key, None)
        return None
    return raw


def cache_set_bytes(key: str, value: bytes, ttl: int = 3600) -> None:
    client = get_redis_binary()
    if client is not None:
        try:
            client.setex(key, ttl, value)
            return
        except Exception:
            pass

    try:
        cache_set_json(f"{key}:b64", {"b64": base64.b64encode(value).decode("ascii")}, ttl=ttl)
        return
    except Exception:
        pass

    _memory_bytes[key] = (time.time() + ttl, value)


def cache_delete_prefix(prefix: str) -> int:
    """Invalida chaves Redis com prefixo (best-effort)."""
    deleted = 0
    client = get_redis_client()
    if client is not None:
        try:
            for key in client.scan_iter(match=f"{prefix}*", count=200):
                client.delete(key)
                deleted += 1
        except Exception:
            pass
    binary = get_redis_binary()
    if binary is not None:
        try:
            for key in binary.scan_iter(match=f"{prefix}*", count=200):
                binary.delete(key)
                deleted += 1
        except Exception:
            pass
    for store in (_memory_cache, _memory_bytes):
        for key in list(store.keys()):
            if key.startswith(prefix):
                store.pop(key, None)
                deleted += 1
    return deleted
