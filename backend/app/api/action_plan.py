from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PlanoAcaoMunicipal
from app.security.municipio_access import assert_codigo_ibge_access, get_accessible_municipio
from app.services.action_plan_engine import action_plan_to_dict, generate_action_plan
from app.services.action_tracking_service import (
    get_acompanhamento_summary,
    patch_action_status,
    reavaliar_risco,
)
from app.services.audit_service import log_audit, resolve_actor

router = APIRouter()


class ActionStatusPatch(BaseModel):
    status: str = Field(..., description="planejada | em_andamento | executada | cancelada")
    nota: Optional[str] = None
    responsavel: Optional[str] = None


class ReavaliarRequest(BaseModel):
    nota: Optional[str] = None


class ActionPlanItem(BaseModel):
    id: str
    titulo: str
    descricao: str
    horizonte: str
    custo: str
    prioridade: str
    justificativa: str
    fonte: str
    orgao: str
    bairros_alvo: list[str] = []


class ActionPlanResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    municipio_id: int | None = None
    codigo_ibge: str
    versao: int | None = None
    diagnostic_id: int | None = None
    status: str | None = None
    severidade: str
    score_sinidu: int
    headline: str
    origem: str | None = None
    gerado_em: str | None = None
    acoes_curto_prazo: list[ActionPlanItem]
    acoes_medio_prazo: list[ActionPlanItem]
    acoes_longo_prazo: list[ActionPlanItem]
    total_acoes: int
    programas_financiamento: list[dict]
    capacidade_fiscal: dict
    lacunas: list[str]
    fontes_consultadas: list[dict]
    municipio: dict
    ranking_bairros: list[dict] = []
    maturidade: dict | None = None


@router.post("/generate/{codigo_ibge}", response_model=ActionPlanResponse)
def generate_municipal_action_plan(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request)
    get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        record = generate_action_plan(db, codigo_ibge, origem="manual")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    payload = action_plan_to_dict(record)
    log_audit(
        db,
        user=actor,
        action="action_plan.generate",
        resource_type="plano_acao",
        resource_id=record.id,
        codigo_ibge=codigo_ibge,
        metadata={"versao": record.versao, "total_acoes": payload.get("total_acoes")},
        request=request,
    )
    return payload


@router.get("/{codigo_ibge}", response_model=ActionPlanResponse)
def get_latest_action_plan(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    record = (
        db.query(PlanoAcaoMunicipal)
        .filter(PlanoAcaoMunicipal.codigo_ibge == codigo_ibge)
        .order_by(PlanoAcaoMunicipal.gerado_em.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Nenhum plano de ação gerado para este município.")
    return action_plan_to_dict(record)


@router.get("/{codigo_ibge}/history")
def list_action_plan_history(codigo_ibge: str, request: Request, limit: int = 10, db: Session = Depends(get_db)):
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    rows = (
        db.query(PlanoAcaoMunicipal)
        .filter(PlanoAcaoMunicipal.codigo_ibge == codigo_ibge)
        .order_by(PlanoAcaoMunicipal.gerado_em.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "versao": row.versao,
                "severidade": row.severidade,
                "headline": row.headline,
                "origem": row.origem,
                "gerado_em": row.gerado_em.isoformat() if row.gerado_em else None,
            }
            for row in rows
        ]
    }


def _latest_plan(db: Session, codigo_ibge: str) -> PlanoAcaoMunicipal:
    record = (
        db.query(PlanoAcaoMunicipal)
        .filter(PlanoAcaoMunicipal.codigo_ibge == codigo_ibge)
        .order_by(PlanoAcaoMunicipal.gerado_em.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Nenhum plano de ação gerado para este município.")
    return record


@router.get("/{codigo_ibge}/acompanhamento")
def get_action_acompanhamento(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """Resumo de execução das ações do plano mais recente (17h.3e)."""
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    return get_acompanhamento_summary(_latest_plan(db, codigo_ibge))


@router.patch("/{codigo_ibge}/acoes/{action_id}")
def patch_action_execution(
    codigo_ibge: str,
    action_id: str,
    body: ActionStatusPatch,
    request: Request,
    db: Session = Depends(get_db),
):
    """Atualiza status de uma ação do plano (planejada → executada)."""
    actor = resolve_actor(request)
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    record = _latest_plan(db, codigo_ibge)
    try:
        payload = patch_action_status(
            db,
            record,
            action_id,
            status=body.status,
            nota=body.nota,
            responsavel=body.responsavel or getattr(actor, "username", None),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_audit(
        db,
        user=actor,
        action="action_plan.patch_status",
        resource_type="plano_acao",
        resource_id=record.id,
        codigo_ibge=codigo_ibge,
        metadata={"action_id": action_id, "status": body.status},
        request=request,
    )
    return payload


@router.post("/{codigo_ibge}/reavaliar")
def reavaliar_action_plan(
    codigo_ibge: str,
    request: Request,
    body: ReavaliarRequest | None = None,
    db: Session = Depends(get_db),
):
    """Reavalia o risco (semáforo) e grava delta no acompanhamento do plano."""
    actor = resolve_actor(request)
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    record = _latest_plan(db, codigo_ibge)
    try:
        out = reavaliar_risco(db, record, nota=(body.nota if body else None))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_audit(
        db,
        user=actor,
        action="action_plan.reavaliar",
        resource_type="plano_acao",
        resource_id=record.id,
        codigo_ibge=codigo_ibge,
        metadata={"reavaliacao": out.get("reavaliacao")},
        request=request,
    )
    return out
