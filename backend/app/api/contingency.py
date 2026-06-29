from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ContingencyPlan, ContingencyPlanRevision, Municipio
from app.services.cobrade_templates import default_acoes_por_nivel
from app.services.contingency_planner import (
    generate_plan_from_simulation,
    plan_to_dict,
    save_revision,
    update_plan,
)
from app.services.audit_service import log_audit, resolve_actor
from app.security.municipio_access import get_accessible_municipio, get_accessible_municipio_by_id

router = APIRouter()
logger = logging.getLogger(__name__)


class ContingencyPlanCreate(BaseModel):
    codigo_ibge: str
    cenario_tipo: Literal["INUNDACAO", "DESLIZAMENTO", "MULTIPLO"] = "INUNDACAO"
    nivel_alerta: str = "VERDE"
    criado_por: str = "usuario"
    zonas_evacuacao: list = Field(default_factory=list)
    rotas_fuga: list = Field(default_factory=list)
    pontos_apoio: list = Field(default_factory=list)
    contatos_defesa_civil: list = Field(default_factory=list)
    acoes_por_nivel: dict = Field(default_factory=dict)
    status: str = "RASCUNHO"


class ContingencyPlanUpdate(BaseModel):
    cenario_tipo: Optional[str] = None
    nivel_alerta: Optional[str] = None
    zonas_evacuacao: Optional[list] = None
    rotas_fuga: Optional[list] = None
    pontos_apoio: Optional[list] = None
    contatos_defesa_civil: Optional[list] = None
    acoes_por_nivel: Optional[dict] = None
    status: Optional[str] = None


class GenerateFromSimulation(BaseModel):
    codigo_ibge: str
    cenario_tipo: str = "INUNDACAO"
    risk_geojson: dict
    buffer_m: float = 500
    simulacao_ref: Optional[dict] = None


@router.get("/templates/acoes")
def get_action_templates(cenario_tipo: str = "INUNDACAO"):
    return default_acoes_por_nivel(cenario_tipo.upper())


@router.get("/municipio/{codigo_ibge}")
def list_plans(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    plans = (
        db.query(ContingencyPlan)
        .filter(ContingencyPlan.municipio_id == muni.id)
        .order_by(ContingencyPlan.updated_at.desc())
        .all()
    )
    return [plan_to_dict(p, muni) for p in plans]


@router.get("/municipio/{codigo_ibge}/ativo")
def get_active_plan(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    plan = (
        db.query(ContingencyPlan)
        .filter(ContingencyPlan.municipio_id == muni.id, ContingencyPlan.status == "ATIVO")
        .order_by(ContingencyPlan.updated_at.desc())
        .first()
    )
    if not plan:
        return None
    return plan_to_dict(plan, muni)


@router.get("/{plan_id}")
def get_plan(plan_id: int, request: Request, db: Session = Depends(get_db)):
    plan = db.query(ContingencyPlan).filter(ContingencyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plano não encontrado")
    muni = get_accessible_municipio_by_id(db, plan.municipio_id, request=request)
    return plan_to_dict(plan, muni)


@router.get("/{plan_id}/revisions")
def list_revisions(plan_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(ContingencyPlanRevision)
        .filter(ContingencyPlanRevision.plan_id == plan_id)
        .order_by(ContingencyPlanRevision.versao.desc())
        .all()
    )
    return [
        {"id": r.id, "versao": r.versao, "revisado_em": r.revisado_em.isoformat(), "revisado_por": r.revisado_por}
        for r in rows
    ]


@router.post("/")
def create_plan(body: ContingencyPlanCreate, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, body.codigo_ibge, request=request)
    acoes = body.acoes_por_nivel or default_acoes_por_nivel(body.cenario_tipo)
    plan = ContingencyPlan(
        municipio_id=muni.id,
        cenario_tipo=body.cenario_tipo,
        nivel_alerta=body.nivel_alerta,
        criado_por=body.criado_por,
        zonas_evacuacao=body.zonas_evacuacao,
        rotas_fuga=body.rotas_fuga,
        pontos_apoio=body.pontos_apoio,
        contatos_defesa_civil=body.contatos_defesa_civil,
        acoes_por_nivel=acoes,
        status=body.status,
    )
    db.add(plan)
    db.flush()
    save_revision(db, plan, body.criado_por)
    db.commit()
    db.refresh(plan)
    return plan_to_dict(plan, muni)


@router.post("/generate-from-simulation")
def generate_from_simulation(body: GenerateFromSimulation, request: Request, db: Session = Depends(get_db)):
    get_accessible_municipio(db, body.codigo_ibge, request=request)
    try:
        plan = generate_plan_from_simulation(
            db,
            body.codigo_ibge,
            body.cenario_tipo,
            body.risk_geojson,
            buffer_m=body.buffer_m,
            simulacao_ref=body.simulacao_ref,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    muni = db.query(Municipio).filter(Municipio.id == plan.municipio_id).first()
    return plan_to_dict(plan, muni)


@router.put("/{plan_id}")
def update_plan_endpoint(plan_id: int, body: ContingencyPlanUpdate, request: Request, db: Session = Depends(get_db)):
    plan = db.query(ContingencyPlan).filter(ContingencyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plano não encontrado")
    get_accessible_municipio_by_id(db, plan.municipio_id, request=request)
    try:
        plan = update_plan(db, plan_id, body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    muni = get_accessible_municipio_by_id(db, plan.municipio_id, request=request)
    return plan_to_dict(plan, muni)


@router.post("/{plan_id}/activate")
def activate_plan(plan_id: int, request: Request, db: Session = Depends(get_db)):
    plan = db.query(ContingencyPlan).filter(ContingencyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plano não encontrado")
    muni = get_accessible_municipio_by_id(db, plan.municipio_id, request=request)
    db.query(ContingencyPlan).filter(
        ContingencyPlan.municipio_id == plan.municipio_id,
        ContingencyPlan.status == "ATIVO",
    ).update({"status": "ARQUIVADO"})
    plan.status = "ATIVO"
    db.commit()
    actor = resolve_actor(request)
    log_audit(
        db,
        user=actor,
        action="contingency.activate",
        resource_type="contingency_plan",
        resource_id=plan.id,
        codigo_ibge=muni.codigo_ibge if muni else None,
        metadata={"cenario_tipo": plan.cenario_tipo, "nivel_alerta": plan.nivel_alerta},
        request=request,
    )
    return plan_to_dict(plan, muni)


@router.post("/{plan_id}/export-pdf")
def export_pdf(plan_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.contingency_report import generate_contingency_pdf
    plan = db.query(ContingencyPlan).filter(ContingencyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plano não encontrado")
    muni = get_accessible_municipio_by_id(db, plan.municipio_id, request=request)
    path = generate_contingency_pdf(plan, muni)
    actor = resolve_actor(request)
    log_audit(
        db,
        user=actor,
        action="contingency.export_pdf",
        resource_type="contingency_plan",
        resource_id=plan.id,
        codigo_ibge=muni.codigo_ibge if muni else None,
        metadata={"filename": path.name},
        request=request,
    )
    return {
        "status": "ok",
        "filename": path.name,
        "download_url": f"/api/v1/contingency/{plan_id}/download-pdf",
    }


@router.get("/{plan_id}/download-pdf")
def download_pdf(plan_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.contingency_report import generate_contingency_pdf
    plan = db.query(ContingencyPlan).filter(ContingencyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plano não encontrado")
    muni = get_accessible_municipio_by_id(db, plan.municipio_id, request=request)
    path = generate_contingency_pdf(plan, muni)
    if not path.exists():
        raise HTTPException(404, "PDF não encontrado")
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name,
    )
