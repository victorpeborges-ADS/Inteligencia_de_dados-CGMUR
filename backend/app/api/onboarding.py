from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MunicipioSeed
from app.security.municipio_access import assert_codigo_ibge_access
from app.security.tenant import can_access_municipio
from app.services.audit_service import resolve_actor, log_audit
from app.services.municipio_loader import ensure_municipality_loaded
from app.security.auth import Role, User, require_role
from app.services.onboarding_engine import (
    list_onboarding_statuses,
    onboarding_status_dict,
    run_batch_onboarding,
    run_onboarding,
    validate_ibge_code,
)

router = APIRouter()


class OnboardingValidateRequest(BaseModel):
    codigo_ibge: str = Field(..., min_length=1, max_length=7)


class OnboardingRunRequest(BaseModel):
    codigo_ibge: str = Field(..., min_length=1, max_length=7)
    force: bool = False


def _normalize_ibge(value: str) -> str:
    code = str(value).strip().replace(".", "").zfill(7)[:7]
    if not code.isdigit() or len(code) != 7:
        raise HTTPException(status_code=400, detail="Código IBGE deve conter 7 dígitos numéricos.")
    return code


@router.get("/status")
def list_status(
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    actor = resolve_actor(request)
    items = list_onboarding_statuses(db, limit=limit)
    filtered = [
        item
        for item in items
        if can_access_municipio(actor, item.get("codigo_ibge", ""), item.get("uf", ""))
    ]
    return {"items": filtered}


@router.post("/ensure/{codigo_ibge}")
def ensure_municipality(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    code = _normalize_ibge(codigo_ibge)
    actor = resolve_actor(request)
    assert_codigo_ibge_access(db, code, request=request)
    try:
        result = ensure_municipality_loaded(db, code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao carregar município: {exc}") from exc
    log_audit(
        db,
        user=actor,
        action="onboarding.ensure",
        resource_type="municipio",
        codigo_ibge=code,
        metadata={"loaded": result.get("loaded"), "nome": result.get("nome")},
        request=request,
    )
    return result


@router.get("/{codigo_ibge}")
def get_status(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    code = assert_codigo_ibge_access(db, codigo_ibge, request=request)
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == code).first()
    if not seed:
        raise HTTPException(status_code=404, detail="Município não cadastrado no onboarding.")
    return onboarding_status_dict(db, seed)


@router.post("/validate")
def validate_municipality(body: OnboardingValidateRequest):
    code = _normalize_ibge(body.codigo_ibge)
    try:
        return validate_ibge_code(code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run")
def run_municipality_onboarding(body: OnboardingRunRequest, request: Request, db: Session = Depends(get_db)):
    code = _normalize_ibge(body.codigo_ibge)
    actor = resolve_actor(request)
    assert_codigo_ibge_access(db, code, request=request)
    try:
        result = run_onboarding(db, code, force=body.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha no onboarding: {exc}") from exc
    log_audit(
        db,
        user=actor,
        action="onboarding.run",
        resource_type="municipio_seed",
        codigo_ibge=code,
        metadata={"status": result.get("onboarding_status"), "force": body.force},
        request=request,
    )
    return result


@router.post("/run-batch")
def run_batch(
    limit: int = Query(default=5, ge=1, le=20),
    status: str = Query(default="pendente"),
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    """Onboarding em lote — admin, até 20 municípios por chamada."""
    try:
        return run_batch_onboarding(db, limit=limit, status_filter=status, force=force)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha no lote: {exc}") from exc
