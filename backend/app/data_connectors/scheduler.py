from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.db import SessionLocal
from app.data_connectors.orchestrator import IntegrationOrchestrator
from app.observability.metrics import record_scheduler_job
from app.services.cemaden_monitor import emit_recent_alerts, sync_cemaden_alerts
from app.services.postgis_backup import run_postgis_backup
from app.services.weather_monitor import cleanup_old_records, sync_weather_for_municipalities

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _run_weekly_sync() -> None:
    db = SessionLocal()
    ok = True
    try:
        summary = IntegrationOrchestrator(db).sync_all()
        logger.info("Integração semanal concluída: %s", summary)
    except Exception as exc:
        ok = False
        logger.exception("Falha na integração semanal: %s", exc)
    finally:
        db.close()
        record_scheduler_job("weekly_public_data_sync", ok)


def _run_cemaden_sync() -> None:
    import asyncio

    db = SessionLocal()
    ok = True
    try:
        result = sync_cemaden_alerts(db)
        logger.info("CEMADEN sync: %s", result)
        asyncio.run(emit_recent_alerts(db))
    except Exception as exc:
        ok = False
        logger.exception("CEMADEN sync falhou: %s", exc)
    finally:
        db.close()
        record_scheduler_job("cemaden_alerts_sync", ok)


def _run_weather_sync() -> None:
    import asyncio

    db = SessionLocal()
    ok = True
    try:
        result = asyncio.run(sync_weather_for_municipalities(db))
        logger.info("OpenMeteo sync: %s", result)
    except Exception as exc:
        ok = False
        logger.exception("Weather sync falhou: %s", exc)
    finally:
        db.close()
        record_scheduler_job("openmeteo_weather_sync", ok)


def _run_cleanup() -> None:
    db = SessionLocal()
    ok = True
    try:
        result = cleanup_old_records(db, days=7)
        logger.info("Cleanup monitoramento: %s", result)
    except Exception as exc:
        ok = False
        logger.exception("Cleanup falhou: %s", exc)
    finally:
        db.close()
        record_scheduler_job("monitoring_ttl_cleanup", ok)


def _run_postgis_backup() -> None:
    ok = True
    try:
        result = run_postgis_backup()
        logger.info("Backup PostGIS: %s", result)
    except Exception as exc:
        ok = False
        logger.exception("Backup PostGIS falhou: %s", exc)
    finally:
        record_scheduler_job("postgis_backup", ok)


def _run_scheduled_pipeline() -> None:
    from app.config import settings

    if not settings.SCHEDULED_PIPELINE_ENABLED:
        return
    ok = True
    try:
        from app.services.background_jobs import run_scheduled_pipeline

        job_id = run_scheduled_pipeline()
        logger.info("Pipeline territorial agendado disparado (job=%s)", job_id)
    except Exception as exc:
        ok = False
        logger.exception("Pipeline agendado falhou: %s", exc)
    finally:
        record_scheduler_job("scheduled_territorial_pipeline", ok)


def start_integration_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    _scheduler.add_job(
        _run_weekly_sync,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="weekly_public_data_sync",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_cemaden_sync,
        IntervalTrigger(minutes=30),
        id="cemaden_alerts_sync",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_weather_sync,
        IntervalTrigger(minutes=55),
        id="openmeteo_weather_sync",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_cleanup,
        CronTrigger(hour=4, minute=15),
        id="monitoring_ttl_cleanup",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_postgis_backup,
        CronTrigger(hour=2, minute=30),
        id="postgis_backup",
        replace_existing=True,
    )

    from app.config import settings

    if settings.SCHEDULED_PIPELINE_ENABLED:
        _scheduler.add_job(
            _run_scheduled_pipeline,
            CronTrigger(day_of_week="sun", hour=4, minute=30),
            id="scheduled_territorial_pipeline",
            replace_existing=True,
        )

    _scheduler.start()
    logger.info(
        "Scheduler iniciado: integrações + CEMADEN (30min) + OpenMeteo (55min) + cleanup + backup (02:30)"
        + (" + pipeline domingo 04:30." if settings.SCHEDULED_PIPELINE_ENABLED else ".")
    )
    return _scheduler


def scheduler_status() -> dict[str, Any]:
    if not _scheduler or not _scheduler.running:
        return {"running": False, "jobs": []}
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return {"running": True, "jobs": jobs}
