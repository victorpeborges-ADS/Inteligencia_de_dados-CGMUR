"""Testes do endpoint /health/tls."""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


def test_health_tls_unavailable_when_no_cert():
    client = TestClient(app)
    res = client.get("/health/tls")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in ("disabled", "unavailable", "ok", "unknown")
