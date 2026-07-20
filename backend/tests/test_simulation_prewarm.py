"""Testes de pré-aquecimento de simulação pluvial."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.simulation_prewarm import (
    prewarm_boot_priority_municipalities,
    schedule_compare_prewarm,
    schedule_rainfall_prewarm,
)


@patch("app.services.simulation_prewarm.threading.Thread")
@patch("app.services.simulation_prewarm.schedule_compare_prewarm")
@patch("app.services.simulation_prewarm.schedule_rainfall_prewarm")
def test_boot_prewarm_schedules_rain_and_compare(mock_rain, mock_compare, mock_thread):
    prewarm_boot_priority_municipalities()
    assert mock_rain.call_count >= 1
    assert mock_compare.call_count >= 1


@patch("app.services.simulation_prewarm.threading.Thread")
def test_schedule_compare_prewarm_idempotent(mock_thread):
    first = schedule_compare_prewarm("2611606", 80.0, 120.0)
    second = schedule_compare_prewarm("2611606", 80.0, 120.0)
    assert first["status"] == "scheduled"
    assert second["status"] == "already_running"
    assert mock_thread.call_count == 1


@patch("app.services.simulation_prewarm.schedule_compare_prewarm")
@patch("app.services.simulation_prewarm.threading.Thread")
def test_schedule_rainfall_triggers_compare_when_both_mm(mock_thread, mock_compare):
    schedule_rainfall_prewarm("2611606", 120.0, extra_mm=[80.0])
    mock_compare.assert_called_once()
    args = mock_compare.call_args[0]
    assert args[0] == "2611606"
    assert args[1] == 80.0
    assert args[2] == 120.0


@patch("app.services.simulation_prewarm.compare_rainfall_cached")
def test_prewarm_municipality_rainfall_compare(mock_compare):
    from app.services.simulation_prewarm import prewarm_municipality_rainfall_compare

    mock_compare.return_value = {"from_cache": False}
    db = MagicMock()
    muni = MagicMock()
    muni.id = 7
    db.query.return_value.filter.return_value.first.return_value = muni

    out = prewarm_municipality_rainfall_compare(db, "2611606", 80.0, 120.0)
    assert out["ok"] is True
    mock_compare.assert_called_once_with(db, 7, "2611606", 80.0, 120.0)
