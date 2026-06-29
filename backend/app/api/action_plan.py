from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PlanoAcaoMunicipal
from app.security.municipio_access import assert_codigo_ibge_access, get_accessible_municipio
from app.services.action_plan_engine import action_plan_to_dict, generate_action_plan

router = APIRouter()


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

    class Config:
        extra = "ignore"


@router.post("/generate/{codigo_ibge}", response_model=ActionPlanResponse)
def generate_municipal_action_plan(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        record = generate_action_plan(db, codigo_ibge, origem="manual")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return action_plan_to_dict(record)


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
