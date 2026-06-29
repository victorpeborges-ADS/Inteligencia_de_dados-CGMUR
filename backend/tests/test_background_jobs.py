"""Testes de jobs em background."""

from __future__ import annotations

from app.services.background_jobs import create_job, get_job, list_jobs


def test_create_and_get_job():
    job_id = create_job("test", label="Teste")
    job = get_job(job_id)
    assert job is not None
    assert job["status"] == "queued"
    assert job["type"] == "test"
    items = list_jobs(limit=5)
    assert any(item["id"] == job_id for item in items)
