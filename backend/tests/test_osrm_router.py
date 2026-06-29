"""Testes de roteamento OSRM."""

from __future__ import annotations

from unittest.mock import patch

from app.services import osrm_router


def test_fallback_route_haversine_distance():
    origin = (-34.88, -8.05)
    destination = (-34.87, -8.06)
    feat = osrm_router._fallback_route(origin, destination)
    props = feat["properties"]
    assert props["aproximada"] is True
    assert props["fonte"] == "fallback"
    assert props["distancia_m"] > 0
    assert props["duracao_s"] > 0


def test_osrm_status_when_unreachable():
    with patch("app.services.osrm_router.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.side_effect = OSError("offline")
        status = osrm_router.osrm_status()
    assert status["available"] is False
    assert "covered_ufs" in status
    assert status["region"]


def test_route_uses_fallback_outside_covered_uf(monkeypatch):
    monkeypatch.setattr(osrm_router, "OSRM_COVERED_UFS", {"PE"})
    feat = osrm_router.route((-46.6, -23.5), (-46.61, -23.51), uf="SP")
    assert feat is not None
    assert feat["properties"]["fonte"] == "fallback"


def test_routes_from_zones_empty():
    assert osrm_router.routes_from_zones_to_support_points([], [{"nome": "A", "coordinates": [0, 0]}]) == []
