"""Testes de jobs expirados e pré-aquecimento de simulação."""

from datetime import datetime, timedelta, timezone

from app.services.background_jobs import _is_stale_running, recover_stale_jobs


def test_stale_running_job_detected():
    started = (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat()
    job = {
        "id": "abc123",
        "type": "diagnostics_batch",
        "status": "running",
        "progress": 0,
        "started_at": started,
    }
    assert _is_stale_running(job) is True


def test_recent_running_job_not_stale():
    started = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    job = {
        "id": "def456",
        "type": "rainfall_simulation",
        "status": "running",
        "progress": 40,
        "started_at": started,
    }
    assert _is_stale_running(job) is False


def test_recover_stale_jobs_idempotent():
    # Não deve lançar mesmo sem Redis/jobs em memória
    count = recover_stale_jobs()
    assert count >= 0
