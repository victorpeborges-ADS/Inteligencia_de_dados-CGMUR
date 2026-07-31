"""Jobs administrativos em background (onboarding, ETL, MapBiomas)."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from app.db import SessionLocal
from app.config import settings
from app.services.job_store import load_job as load_persisted_job
from app.services.job_store import save_job as persist_job
from app.services.job_store import list_persisted_jobs
from app.timeutil import utc_now_iso_z

logger = logging.getLogger(__name__)

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()
STALE_JOB_HOURS = int(getattr(settings, "STALE_JOB_HOURS", 6) or 6)


def _utcnow() -> str:
    return utc_now_iso_z()


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def _is_stale_running(job: dict[str, Any]) -> bool:
    if job.get("status") != "running":
        return False
    anchor = _parse_ts(job.get("started_at")) or _parse_ts(job.get("created_at"))
    if not anchor:
        return False
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - anchor
    return age > timedelta(hours=STALE_JOB_HOURS)


def _mark_stale(job_id: str, job: dict[str, Any]) -> dict[str, Any]:
    updated = {
        **job,
        "status": "failed",
        "finished_at": _utcnow(),
        "error": "Job expirado (processo reiniciado ou interrompido)",
    }
    with _lock:
        _jobs[job_id] = updated
        persist_job(updated)
    logger.warning("Job %s (%s) marcado como expirado", job_id, job.get("type"))
    return updated


def recover_stale_jobs() -> int:
    """Marca jobs 'running' antigos como falhos após restart."""
    recovered = 0
    rows = list_persisted_jobs(limit=100)
    with _lock:
        rows.extend(_jobs.values())
    seen: set[str] = set()
    for job in rows:
        job_id = str(job.get("id") or "")
        if not job_id or job_id in seen:
            continue
        seen.add(job_id)
        if _is_stale_running(job):
            _mark_stale(job_id, job)
            recovered += 1
    if recovered:
        logger.info("Recuperados %s job(s) expirado(s)", recovered)
    return recovered


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
        persist_job(_jobs[job_id])
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            if _is_stale_running(job):
                job = _mark_stale(job_id, job)
            return dict(job)
    persisted = load_persisted_job(job_id)
    if persisted:
        if _is_stale_running(persisted):
            persisted = _mark_stale(job_id, persisted)
        with _lock:
            _jobs[job_id] = persisted
        return dict(persisted)
    return None


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    recover_stale_jobs()
    with _lock:
        memory_rows = sorted(_jobs.values(), key=lambda item: item["created_at"], reverse=True)
    if memory_rows:
        return [dict(row) for row in memory_rows[:limit]]
    rows = list_persisted_jobs(limit)[:limit]
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        job_id = str(row.get("id") or "")
        if job_id and _is_stale_running(row):
            row = _mark_stale(job_id, row)
        cleaned.append(dict(row))
    return cleaned


def _update(job_id: str, **fields: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)
            persist_job(_jobs[job_id])


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


def run_uf_bootstrap_job(uf: str, *, limit: int = 20, skip_existing: bool = True) -> str:
    """Job de bootstrap mínimo por UF (18c.1)."""
    from app.services.uf_bootstrap_service import normalize_uf

    uf_code = normalize_uf(uf)
    existing = find_active_job("uf_bootstrap")
    if existing:
        return str(existing["id"])

    job_id = create_job(
        "uf_bootstrap",
        label=f"Bootstrap UF {uf_code} (até {limit})",
    )

    def _task() -> dict[str, Any]:
        from app.services.uf_bootstrap_service import bootstrap_uf

        db = SessionLocal()
        try:
            return bootstrap_uf(
                db,
                uf_code,
                limit=limit,
                skip_existing=skip_existing,
            )
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


def run_pipeline_job(onboarding_limit: int = 6) -> str:
    job_id = create_job("full_pipeline", label="Pipeline territorial completo")

    def _task() -> dict[str, Any]:
        from app.data_connectors.mapbiomas_collector import sync_mapbiomas_batch
        from app.data_connectors.orchestrator import IntegrationOrchestrator
        from app.services.onboarding_engine import run_batch_onboarding

        db = SessionLocal()
        try:
            # Onboarding primeiro — libera geometria PostGIS para diagnósticos/PDFs;
            # ETL de indicadores e MapBiomas em seguida.
            onboarding = run_batch_onboarding(db, limit=onboarding_limit, status_filter="pendente", force=False)
            etl = IntegrationOrchestrator(db).sync_all()
            mapbiomas = sync_mapbiomas_batch(db, limit=onboarding_limit, force=False)
            return {"onboarding": onboarding, "etl": etl, "mapbiomas": mapbiomas}
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_scheduled_pipeline() -> str | None:
    """Disparado pelo APScheduler quando SCHEDULED_PIPELINE_ENABLED=true."""
    limit = min(max(settings.SCHEDULED_PIPELINE_LIMIT, 1), 6)
    logger.info("Pipeline territorial agendado iniciando (limit=%s)", limit)
    return run_pipeline_job(onboarding_limit=limit)


def find_active_job(job_type: str) -> dict[str, Any] | None:
    """Retorna job ativo do tipo, após recuperar expirados."""
    recover_stale_jobs()
    for job in list_jobs(limit=50):
        if job.get("type") == job_type and job.get("status") in {"queued", "running"}:
            return job
    return None


def run_diagnostics_batch_job(limit: int = 6, *, codigos: list[str] | None = None) -> str:
    existing = find_active_job("diagnostics_batch")
    if existing:
        return str(existing["id"])

    label = f"Diagnósticos executivos ({limit})"
    job_id = create_job("diagnostics_batch", label=label)

    def _task() -> dict[str, Any]:
        from app.services.batch_export_service import run_batch_diagnostics

        db = SessionLocal()
        try:
            return run_batch_diagnostics(db, limit=limit, codigos=codigos)
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_reports_batch_job(
    limit: int = 6,
    force: bool = False,
    *,
    codigos: list[str] | None = None,
) -> str:
    existing = find_active_job("reports_batch")
    if existing:
        return str(existing["id"])

    job_id = create_job("reports_batch", label=f"Relatórios PDF ({limit})")

    def _task() -> dict[str, Any]:
        from app.services.batch_export_service import run_batch_reports

        db = SessionLocal()
        try:
            return run_batch_reports(db, limit=limit, force=force, codigos=codigos)
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_external_sources_batch_job(limit: int = 6) -> str:
    job_id = create_job("fontes_externas_batch", label=f"Fontes externas ({limit})")

    def _task() -> dict[str, Any]:
        from app.data_connectors.constants import TARGET_IBGE_CODES
        from app.data_connectors.external_sources_collector import sync_external_sources_batch

        db = SessionLocal()
        try:
            codigos = TARGET_IBGE_CODES[: min(limit, 6)]
            return sync_external_sources_batch(db, codigos)
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_bairros_batch_job(limit: int = 6, force: bool = False) -> str:
    job_id = create_job("bairros_batch", label=f"Malha oficial IBGE ({limit})")

    def _task() -> dict[str, Any]:
        from app.data_connectors.official_bairros_collector import sync_official_bairros_batch

        db = SessionLocal()
        try:
            return sync_official_bairros_batch(db, limit=limit, force=force)
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_buildings_osm_queue_job(*, max_items: int = 20) -> str:
    """Drena a fila de footprints OSM com rate-limit (18c.2)."""
    existing = find_active_job("buildings_osm_queue")
    if existing:
        return str(existing["id"])

    job_id = create_job(
        "buildings_osm_queue",
        label=f"Footprints OSM (até {max_items})",
    )

    def _task() -> dict[str, Any]:
        from app.services.building_osm_queue_service import drain_queue

        return drain_queue(max_items=max_items)

    run_in_background(job_id, _task)
    return job_id


def run_ctm_batch_job(*, force: bool = False, codigos: list[str] | None = None) -> str:
    from app.data_connectors.ctm_registry import CTM_BY_CODE, CTM_TARGET_CODES

    targets = codigos or [c for c in CTM_TARGET_CODES if c in CTM_BY_CODE]
    job_id = create_job("ctm_batch", label=f"CTM / geoportal ({len(targets)})")

    def _task() -> dict[str, Any]:
        from app.data_connectors.ctm_collector import collect_ctm_batch

        db = SessionLocal()
        try:
            return collect_ctm_batch(db, codigos=targets or None, force=force)
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_dem_batch_job(limit: int = 6, force: bool = False) -> str:
    job_id = create_job("dem_batch", label=f"DEM LiDAR/SRTM ({limit})")

    def _task() -> dict[str, Any]:
        from app.services.dem_processor import sync_dem_batch

        db = SessionLocal()
        try:
            return sync_dem_batch(db, limit=limit, force=force)
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_full_homologation_job(onboarding_limit: int = 6, force_dem: bool = False) -> str:
    job_id = create_job("homologation_full", label="Pipeline MCID completo (piloto 6)")

    def _task() -> dict[str, Any]:
        from app.data_connectors.mapbiomas_collector import sync_mapbiomas_batch
        from app.data_connectors.orchestrator import IntegrationOrchestrator
        from app.services.batch_export_service import run_batch_diagnostics
        from app.services.dem_processor import sync_dem_batch
        from app.services.onboarding_engine import run_batch_onboarding

        db = SessionLocal()
        try:
            onboarding = run_batch_onboarding(
                db, limit=onboarding_limit, status_filter="pendente", force=False,
            )
            etl = IntegrationOrchestrator(db).sync_all()
            mapbiomas = sync_mapbiomas_batch(db, limit=onboarding_limit, force=False)
            dem = sync_dem_batch(db, limit=onboarding_limit, force=force_dem)
            diagnostics = run_batch_diagnostics(db, limit=onboarding_limit, ensure_dem=False)
            return {
                "onboarding": onboarding,
                "etl": etl,
                "mapbiomas": mapbiomas,
                "dem": dem,
                "diagnostics": diagnostics,
            }
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_catalog_refresh_job(codigo_ibge: str) -> str:
    """Recarrega fontes Integrado do catálogo municipal com progresso visível."""
    job_id = create_job("catalog_refresh", label=f"Catálogo {codigo_ibge}")

    def _progress(payload: dict[str, Any]) -> None:
        _update(job_id, progress=payload.get("progress", 0), result=payload)

    def _task() -> dict[str, Any]:
        from app.services.catalog_sync_service import refresh_integrated_sources

        db = SessionLocal()
        try:
            return refresh_integrated_sources(
                db,
                codigo_ibge,
                job_id=job_id,
                progress_callback=_progress,
            )
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id
