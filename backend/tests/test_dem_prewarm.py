"""Testes de pré-aquecimento DEM municipal."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.dem_prewarm import (
    prewarm_boot_priority_dem,
    prewarm_municipality_dem,
    schedule_dem_prewarm,
)


@patch("app.services.dem_prewarm.is_processed", return_value=True)
def test_prewarm_municipality_dem_skips_when_processed(mock_processed):
    db = MagicMock()
    out = prewarm_municipality_dem(db, "2611606")
    assert out["skipped"] is True
    assert out["reason"] == "already_processed"
    mock_processed.assert_called_once_with("2611606")


@patch("app.services.dem_prewarm.process_municipality_dem")
@patch("app.services.dem_prewarm.is_processed", return_value=False)
def test_prewarm_municipality_dem_processes(mock_processed, mock_process):
    db = MagicMock()
    muni = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = muni
    mock_process.return_value = {"dem_source": "DEM local", "dem_resolution_m": 2.0}

    out = prewarm_municipality_dem(db, "2611606")
    assert out["ok"] is True
    assert out["dem_source"] == "DEM local"
    mock_process.assert_called_once_with(db, "2611606", force=False)


@patch("app.services.dem_prewarm.prewarm_municipality_dem")
@patch("app.services.dem_prewarm.SessionLocal")
@patch("app.services.dem_prewarm.settings")
def test_prewarm_boot_priority_dem_iterates_codes(mock_settings, mock_session_local, mock_prewarm):
    mock_settings.BOOT_PRIORITY_IBGE_CODES = ["2611606", "2800308"]
    mock_prewarm.return_value = {"ok": True}
    db = MagicMock()
    mock_session_local.return_value = db

    outcomes = prewarm_boot_priority_dem()
    assert len(outcomes) == 2
    assert mock_prewarm.call_count == 2
    db.close.assert_called_once()


@patch("app.services.dem_prewarm.threading.Thread")
@patch("app.services.dem_prewarm.is_processed", return_value=False)
def test_schedule_dem_prewarm_idempotent(mock_processed, mock_thread):
    first = schedule_dem_prewarm("2611606")
    second = schedule_dem_prewarm("2611606")
    assert first["status"] == "scheduled"
    assert second["status"] == "already_running"
    assert mock_thread.call_count == 1
