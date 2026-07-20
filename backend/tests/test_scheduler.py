"""Testes do scheduler de integrações."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.data_connectors import scheduler as sched


def setup_function() -> None:
    sched._scheduler = None


def teardown_function() -> None:
    if sched._scheduler is not None:
        try:
            sched._scheduler.shutdown(wait=False)
        except Exception:
            pass
    sched._scheduler = None


def test_scheduler_status_when_stopped():
    sched._scheduler = None
    assert sched.scheduler_status() == {"running": False, "jobs": []}


@patch("app.data_connectors.scheduler.BackgroundScheduler")
def test_start_integration_scheduler_registers_jobs(mock_bg):
    instance = MagicMock()
    instance.running = False
    mock_bg.return_value = instance

    with patch("app.config.settings") as cfg:
        cfg.SCHEDULED_PIPELINE_ENABLED = False
        out = sched.start_integration_scheduler()

    assert out is instance
    assert instance.add_job.call_count >= 5
    instance.start.assert_called_once()

    instance.running = True
    instance.get_jobs.return_value = [
        MagicMock(id="weekly_public_data_sync", name="weekly", next_run_time=None, trigger="cron"),
    ]
    sched._scheduler = instance
    status = sched.scheduler_status()
    assert status["running"] is True
    assert status["jobs"][0]["id"] == "weekly_public_data_sync"


@patch("app.data_connectors.scheduler.record_scheduler_job")
@patch("app.data_connectors.scheduler.SessionLocal")
@patch("app.data_connectors.scheduler.IntegrationOrchestrator")
def test_run_weekly_sync_ok(mock_orch, mock_session, mock_record):
    db = MagicMock()
    mock_session.return_value = db
    mock_orch.return_value.sync_all.return_value = {"ibge": 1}
    sched._run_weekly_sync()
    mock_record.assert_called_with("weekly_public_data_sync", True)
    db.close.assert_called_once()


@patch("app.data_connectors.scheduler.record_scheduler_job")
@patch("app.data_connectors.scheduler.SessionLocal")
@patch("app.data_connectors.scheduler.IntegrationOrchestrator", side_effect=RuntimeError("boom"))
def test_run_weekly_sync_failure(mock_orch, mock_session, mock_record):
    db = MagicMock()
    mock_session.return_value = db
    sched._run_weekly_sync()
    mock_record.assert_called_with("weekly_public_data_sync", False)


@patch("app.data_connectors.scheduler.record_scheduler_job")
@patch("app.data_connectors.scheduler.run_postgis_backup", return_value={"ok": True})
def test_run_postgis_backup_job(mock_backup, mock_record):
    sched._run_postgis_backup()
    mock_backup.assert_called_once()
    mock_record.assert_called_with("postgis_backup", True)


@patch("app.data_connectors.scheduler.record_scheduler_job")
def test_scheduled_pipeline_skipped_when_disabled(mock_record):
    with patch("app.config.settings") as cfg:
        cfg.SCHEDULED_PIPELINE_ENABLED = False
        sched._run_scheduled_pipeline()
    mock_record.assert_not_called()


@patch("app.data_connectors.scheduler.record_scheduler_job")
@patch("app.data_connectors.scheduler.SessionLocal")
@patch("app.data_connectors.scheduler.cleanup_old_records", return_value={"deleted": 1})
def test_run_cleanup_ok(mock_cleanup, mock_session, mock_record):
    mock_session.return_value = MagicMock()
    sched._run_cleanup()
    mock_cleanup.assert_called_once()
    mock_record.assert_called_with("monitoring_ttl_cleanup", True)


@patch("app.data_connectors.scheduler.record_scheduler_job")
@patch("app.services.background_jobs.run_scheduled_pipeline", return_value="job-1")
def test_scheduled_pipeline_when_enabled(mock_pipe, mock_record):
    with patch("app.config.settings") as cfg:
        cfg.SCHEDULED_PIPELINE_ENABLED = True
        sched._run_scheduled_pipeline()
    mock_pipe.assert_called_once()
    mock_record.assert_called_with("scheduled_territorial_pipeline", True)
