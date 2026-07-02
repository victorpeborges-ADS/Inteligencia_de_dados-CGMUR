"""Testes job store Redis."""
from __future__ import annotations

import json

from app.services import job_store as js


def test_save_and_load_job(monkeypatch):
    store: dict[str, str] = {}

    class FakeRedis:
        def setex(self, key, _ttl, val):
            store[key] = val

        def get(self, key):
            return store.get(key)

        def zadd(self, *_a, **_k):
            return 1

        def expire(self, *_a, **_k):
            return True

        def zrevrange(self, *_a, **_k):
            return []

    monkeypatch.setattr(js, "_enabled", lambda: True)
    monkeypatch.setattr(js, "_client", lambda: FakeRedis())

    job = {"id": "abc123", "status": "completed", "created_at": "2026-06-30T12:00:00+00:00"}
    js.save_job(job)
    loaded = js.load_job("abc123")
    assert loaded is not None
    assert loaded["status"] == "completed"
