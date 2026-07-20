"""Visão operacional consolidada — homologação e admin."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.health import _ai_fallback_status, _check_db, _check_ollama, _inspect_tls_cert
from app.boot import boot_status
from app.config import settings
from app.data_connectors.orchestrator import IntegrationOrchestrator
from app.data_connectors.mapbiomas_collector import mapbiomas_status
from app.data_connectors.scheduler import scheduler_status
from app.db import get_db
from app.models import AuditLog, Municipio, MunicipioSeed
from app.security.auth import Role, User, require_role
from app.security.oidc import check_oidc_connectivity, oidc_configured

router = APIRouter()


class CheckStatus(BaseModel):
    ok: bool
    detail: str


class SystemOverview(BaseModel):
    timestamp: str
    platform: str
    environment: str
    auth: dict
    checks: dict
    boot: dict
    municipalities: dict
    onboarding: dict
    integrations: dict
    mapbiomas: dict
    dem: dict
    tls: dict
    scheduler: dict
    audit: dict
    routing: dict
    batch_coverage: dict
    ctm: dict
    homologation: dict


@router.get("/overview", response_model=SystemOverview)
def system_overview(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    db_ok, db_msg = _check_db()
    ollama_ok, ollama_msg, ollama_details = _check_ollama()

    oidc_meta: dict = {"configured": oidc_configured(), "reachable": None, "detail": None}
    if oidc_configured():
        oidc_ok, oidc_detail, oidc_extra = check_oidc_connectivity()
        oidc_meta.update({"reachable": oidc_ok, "detail": oidc_detail, **oidc_extra})

    loaded_count = db.query(func.count(Municipio.codigo_ibge)).scalar() or 0
    seed_count = db.query(func.count(MunicipioSeed.codigo_ibge)).scalar() or 0

    onboarding_rows = (
        db.query(MunicipioSeed.onboarding_status, func.count(MunicipioSeed.codigo_ibge))
        .group_by(MunicipioSeed.onboarding_status)
        .all()
    )
    onboarding_by_status = {str(status or "pendente"): count for status, count in onboarding_rows}

    audit_total = db.query(func.count(AuditLog.id)).scalar() or 0
    audit_recent = (
        db.query(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(8)
        .all()
    )

    orchestrator = IntegrationOrchestrator(db)
    sources = orchestrator.status()
    integrated = sum(1 for s in sources if s.get("status") == "OK")
    failed = sum(1 for s in sources if s.get("status") == "FALHA")

    from app.services.dem_processor import dem_status
    from app.services.batch_export_service import batch_coverage_summary
    from app.services.homologation_readiness_service import build_homologation_readiness
    from app.services.institutional_gaps_service import build_ctm_operational_summary

    batch_cov = batch_coverage_summary(db)
    ctm_summary = build_ctm_operational_summary(db)
    dem_meta = dem_status(limit=61)
    boot_codes = settings.BOOT_PRIORITY_IBGE_CODES
    from app.services.dem_processor import is_processed

    dem_meta["boot_processed"] = sum(1 for code in boot_codes if is_processed(code))
    dem_meta["boot_total"] = len(boot_codes)
    tls_meta = _inspect_tls_cert(os.getenv("TLS_FULLCHAIN", "/etc/nginx/certs/fullchain.pem"))
    routing_meta = _routing_overview()
    from app.services.gotify_notifier import gotify_status
    from app.services.postgis_backup import latest_backup_status

    sched_meta = scheduler_status()
    homologation = build_homologation_readiness(
        db,
        oidc_meta=oidc_meta,
        tls_meta=tls_meta,
        batch_coverage=batch_cov,
        ctm_summary=ctm_summary,
        dem_summary=dem_meta,
        osrm_meta=routing_meta,
        backup_meta=latest_backup_status(),
        gotify_meta=gotify_status(),
        scheduler_meta=sched_meta,
    )

    return SystemOverview(
        timestamp=datetime.now(timezone.utc).isoformat(),
        platform=settings.PROJECT_NAME,
        environment=os.getenv("ENVIRONMENT", "development"),
        auth={
            "enabled": settings.AUTH_ENABLED,
            "multi_tenant": settings.MULTI_TENANT_ENABLED,
            "oidc_enabled": settings.OIDC_ENABLED,
            "password_login": settings.AUTH_PASSWORD_LOGIN_ENABLED,
            "public_base_url": settings.PUBLIC_BASE_URL,
        },
        checks={
            "database": CheckStatus(ok=db_ok, detail=db_msg).model_dump(),
            "ollama": {
                "ok": ollama_ok,
                "detail": ollama_msg,
                **ollama_details,
            },
            "ai_fallback": _ai_fallback_status(),
            "oidc": oidc_meta,
            "overall": "healthy" if db_ok else "degraded",
        },
        boot=boot_status.to_dict(),
        municipalities={
            "prioritarios_seed": seed_count,
            "carregados_db": loaded_count,
            "piloto_ibge": settings.PILOT_IBGE_CODE,
            "piloto_nome": settings.PILOT_NAME,
            "boot_priority_ibge": settings.BOOT_PRIORITY_IBGE_CODES,
        },
        onboarding={
            "by_status": onboarding_by_status,
            "pendentes": onboarding_by_status.get("pendente", 0),
            "concluidos": onboarding_by_status.get("concluido", 0),
        },
        integrations={
            "total": len(sources),
            "integradas": integrated,
            "com_falha": failed,
            "sources": sources,
        },
        mapbiomas=mapbiomas_status(db),
        dem=dem_meta,
        tls=tls_meta,
        scheduler=sched_meta,
        audit={
            "total_eventos": audit_total,
            "top_acoes": [{"action": action, "count": count} for action, count in audit_recent],
        },
        routing=routing_meta,
        batch_coverage=batch_cov,
        ctm=ctm_summary,
        homologation=homologation,
    )


def _routing_overview() -> dict:
    from app.services.osrm_router import osrm_status

    return osrm_status()


@router.get("/jobs")
def list_background_jobs(
    limit: int = 20,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    from app.services.background_jobs import list_jobs

    return {"items": list_jobs(limit=limit)}


@router.get("/jobs/{job_id}")
def get_background_job(
    job_id: str,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    from app.services.background_jobs import get_job

    job = get_job(job_id)
    if not job:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Job não encontrado")
    return job


@router.post("/jobs/onboarding-batch")
def start_onboarding_batch_job(
    limit: int = 61,
    status: str = "pendente",
    force: bool = False,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    from app.services.background_jobs import get_job, run_onboarding_batch_job

    job_id = run_onboarding_batch_job(limit=min(limit, 61), status_filter=status, force=force)
    return {"job_id": job_id, "job": get_job(job_id)}


@router.post("/jobs/mapbiomas-batch")
def start_mapbiomas_batch_job(
    limit: int = 61,
    force: bool = False,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    from app.services.background_jobs import get_job, run_mapbiomas_batch_job

    job_id = run_mapbiomas_batch_job(limit=min(limit, 61), force=force)
    return {"job_id": job_id, "job": get_job(job_id)}


@router.post("/jobs/pipeline")
def start_pipeline_job(
    onboarding_limit: int = 61,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    from app.services.background_jobs import get_job, run_pipeline_job

    job_id = run_pipeline_job(onboarding_limit=min(onboarding_limit, 61))
    return {"job_id": job_id, "job": get_job(job_id)}


@router.post("/jobs/diagnostics-batch")
def start_diagnostics_batch_job(
    limit: int = 61,
    codigos: str | None = None,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    from app.services.background_jobs import find_active_job, get_job, run_diagnostics_batch_job

    existing = find_active_job("diagnostics_batch")
    if existing:
        return {"job_id": existing["id"], "job": existing, "reused": True}

    codes = [c.strip().zfill(7)[:7] for c in codigos.split(",") if c.strip()] if codigos else None
    job_id = run_diagnostics_batch_job(limit=min(limit, 61), codigos=codes)
    return {"job_id": job_id, "job": get_job(job_id), "reused": False}


@router.post("/jobs/reports-batch")
def start_reports_batch_job(
    limit: int = 61,
    force: bool = False,
    codigos: str | None = None,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    from app.services.background_jobs import find_active_job, get_job, run_reports_batch_job

    existing = find_active_job("reports_batch")
    if existing:
        return {"job_id": existing["id"], "job": existing, "reused": True}

    codes = [c.strip().zfill(7)[:7] for c in codigos.split(",") if c.strip()] if codigos else None
    job_id = run_reports_batch_job(limit=min(limit, 61), force=force, codigos=codes)
    return {"job_id": job_id, "job": get_job(job_id), "reused": False}


@router.post("/jobs/fontes-externas-batch")
def start_external_sources_batch_job(
    limit: int = 61,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    from app.services.background_jobs import get_job, run_external_sources_batch_job

    job_id = run_external_sources_batch_job(limit=min(limit, 61))
    return {"job_id": job_id, "job": get_job(job_id)}


@router.post("/jobs/bairros-batch")
def start_bairros_batch_job(
    limit: int = 61,
    force: bool = False,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    from app.services.background_jobs import get_job, run_bairros_batch_job

    job_id = run_bairros_batch_job(limit=min(limit, 61), force=force)
    return {"job_id": job_id, "job": get_job(job_id)}


@router.post("/jobs/ctm-batch")
def start_ctm_batch_job(
    force: bool = False,
    codigos: str | None = None,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    """Importa malhas CTM dos geoportais cadastrados (A.6 — escopo BAIXA/MÉDIA)."""
    from app.services.background_jobs import find_active_job, get_job, run_ctm_batch_job

    existing = find_active_job("ctm_batch")
    if existing:
        return {"job_id": existing["id"], "job": existing, "reused": True}

    codes = [c.strip().zfill(7)[:7] for c in codigos.split(",") if c.strip()] if codigos else None
    job_id = run_ctm_batch_job(force=force, codigos=codes)
    return {"job_id": job_id, "job": get_job(job_id), "reused": False}


@router.post("/jobs/dem-batch")
def start_dem_batch_job(
    limit: int = 61,
    force: bool = False,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    from app.services.background_jobs import get_job, run_dem_batch_job

    job_id = run_dem_batch_job(limit=min(limit, 61), force=force)
    return {"job_id": job_id, "job": get_job(job_id)}


@router.post("/jobs/homologation-full")
def start_homologation_full_job(
    onboarding_limit: int = 61,
    force_dem: bool = False,
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    from app.services.background_jobs import get_job, run_full_homologation_job

    job_id = run_full_homologation_job(
        onboarding_limit=min(onboarding_limit, 61),
        force_dem=force_dem,
    )
    return {"job_id": job_id, "job": get_job(job_id)}
