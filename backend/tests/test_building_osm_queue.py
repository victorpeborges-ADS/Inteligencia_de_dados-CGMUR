"""Testes fila OSM footprints (18c.2)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services import building_osm_queue_service as q


@pytest.fixture(autouse=True)
def _clean_queue(monkeypatch):
    monkeypatch.setattr(q, "MIN_INTERVAL_S", 0.0)
    with q._lock:
        q._queue.clear()
        q._history.clear()
        q._processing = False
        q._last_overpass_at = 0.0
    yield
    with q._lock:
        q._queue.clear()
        q._history.clear()
        q._processing = False


def test_enqueue_dedup():
    a = q.enqueue_buildings("2611606", force=False)
    b = q.enqueue_buildings("2611606", force=True)
    assert a["enqueued"] is True
    assert b["enqueued"] is False
    assert b["reason"] == "already_queued"
    assert q.queue_status()["pending"] == 1


@patch("app.data_connectors.building_footprints_collector.collect_buildings_municipality")
def test_process_next_ok(mock_collect):
    mock_collect.return_value = {"status": "ok", "count": 12, "fonte": "osm"}
    q.enqueue_buildings("2611606")
    out = q.process_next(MagicMock())
    assert out["status"] == "ok"
    assert out["count"] == 12
    assert q.queue_status()["pending"] == 0


@patch("app.data_connectors.building_footprints_collector.collect_buildings_municipality")
def test_process_next_requeues_rate_limit(mock_collect):
    mock_collect.return_value = {
        "status": "rate_limited",
        "retryable": True,
        "error": "HTTP 429",
        "count": 0,
    }
    q.enqueue_buildings("2604106")
    out = q.process_next(MagicMock())
    assert out["status"] == "requeued"
    assert q.queue_status()["pending"] == 1


@patch("app.data_connectors.building_footprints_collector.fetch_osm_buildings")
def test_collect_returns_rate_limited(mock_fetch):
    from app.data_connectors.building_footprints_collector import (
        OverpassRateLimitError,
        collect_buildings_municipality,
    )

    mock_fetch.side_effect = OverpassRateLimitError("HTTP 429")
    db = MagicMock()
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    muni.geom = None
    db.query.return_value.filter.return_value.first.return_value = muni
    db.query.return_value.filter.return_value.count.return_value = 0

    out = collect_buildings_municipality(db, "2611606", force=True)
    assert out["status"] == "rate_limited"
    assert out["retryable"] is True
