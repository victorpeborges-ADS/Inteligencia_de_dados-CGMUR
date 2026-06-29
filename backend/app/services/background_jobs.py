"""Jobs administrativos em background (onboarding, ETL, MapBiomas)."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from app.db import SessionLocal
from app.config import settings

logger = logging.getLogger(__name__)

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(job_type: str, *, label: str = "") -> str:
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "type": job_type,
            "label": label or job_type,
            "status": "queued",
            "progress": 0,
            "created_at": _utcnow(),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
        }
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with _lock:
        rows = sorted(_jobs.values(), key=lambda item: item["created_at"], reverse=True)
        return [dict(row) for row in rows[:limit]]


def _update(job_id: str, **fields: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def _notify_job_finished(job_id: str) -> None:
    if not settings.JOB_GOTIFY_NOTIFY:
        return
    job = get_job(job_id)
    if not job:
        return
    detail = ""
    if job.get("error"):
        detail = str(job["error"])
    elif isinstance(job.get("result"), dict):
        parts = []
        for key, val in job["result"].items():
            if isinstance(val, dict) and "processed" in val:
                parts.append(f"{key}: {val.get('processed')}/{val.get('requested', '?')}")
        if parts:
            detail = ", ".join(parts)
    try:
        from app.services.gotify_notifier import push_job_status

        push_job_status(job["label"], job_id, job["status"], detail)
    except Exception as exc:
        logger.debug("Notificação Gotify ignorada: %s", exc)


def run_in_background(job_id: str, fn: Callable[[], Any]) -> None:
    def _runner() -> None:
        _update(job_id, status="running", started_at=_utcnow())
        try:
            result = fn()
            _update(job_id, status="completed", progress=100, finished_at=_utcnow(), result=result)
        except Exception as exc:
            logger.exception("Job %s falhou: %s", job_id, exc)
            _update(job_id, status="failed", finished_at=_utcnow(), error=str(exc))
        finally:
            _notify_job_finished(job_id)

    threading.Thread(target=_runner, daemon=True, name=f"job-{job_id}").start()


def run_onboarding_batch_job(limit: int, status_filter: str, force: bool) -> str:
    job_id = create_job("onboarding_batch", label=f"Onboarding ({limit} × {status_filter})")

    def _task() -> dict[str, Any]:
        from app.services.onboarding_engine import run_batch_onboarding

        db = SessionLocal()
        try:
            return run_batch_onboarding(db, limit=limit, status_filter=status_filter, force=force)
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_mapbiomas_batch_job(limit: int, force: bool) -> str:
    job_id = create_job("mapbiomas_batch", label=f"MapBiomas ({limit} municípios)")

    def _task() -> dict[str, Any]:
        from app.data_connectors.mapbiomas_collector import sync_mapbiomas_batch

        db = SessionLocal()
        try:
            return sync_mapbiomas_batch(db, limit=limit, force=force)
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_pipeline_job(onboarding_limit: int = 61) -> str:
    job_id = create_job("full_pipeline", label="Pipeline territorial completo")

    def _task() -> dict[str, Any]:
        from app.data_connectors.mapbiomas_collector import sync_mapbiomas_batch
        from app.data_connectors.orchestrator import IntegrationOrchestrator
        from app.services.onboarding_engine import run_batch_onboarding

        db = SessionLocal()
        try:
            etl = IntegrationOrchestrator(db).sync_all()
            onboarding = run_batch_onboarding(db, limit=onboarding_limit, status_filter="pendente", force=False)
            mapbiomas = sync_mapbiomas_batch(db, limit=onboarding_limit, force=False)
            return {"etl": etl, "onboarding": onboarding, "mapbiomas": mapbiomas}
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_scheduled_pipeline() -> str | None:
    """Disparado pelo APScheduler quando SCHEDULED_PIPELINE_ENABLED=true."""
    limit = min(max(settings.SCHEDULED_PIPELINE_LIMIT, 1), 61)
    logger.info("Pipeline territorial agendado iniciando (limit=%s)", limit)
    return run_pipeline_job(onboarding_limit=limit)


def run_diagnostics_batch_job(limit: int = 61) -> str:
    job_id = create_job("diagnostics_batch", label=f"Diagnósticos executivos ({limit})")

    def _task() -> dict[str, Any]:
        from app.services.batch_export_service import run_batch_diagnostics

        db = SessionLocal()
        try:
            return run_batch_diagnostics(db, limit=limit)
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_reports_batch_job(limit: int = 61, force: bool = False) -> str:
    job_id = create_job("reports_batch", label=f"Relatórios PDF ({limit})")

    def _task() -> dict[str, Any]:
        from app.services.batch_export_service import run_batch_reports

        db = SessionLocal()
        try:
            return run_batch_reports(db, limit=limit, force=force)
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_external_sources_batch_job(limit: int = 61) -> str:
    job_id = create_job("fontes_externas_batch", label=f"Fontes externas ({limit})")

    def _task() -> dict[str, Any]:
        from app.data_connectors.constants import TARGET_IBGE_CODES
        from app.data_connectors.external_sources_collector import sync_external_sources_batch

        db = SessionLocal()
        try:
            codigos = TARGET_IBGE_CODES[: min(limit, 61)]
            return sync_external_sources_batch(db, codigos)
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id
