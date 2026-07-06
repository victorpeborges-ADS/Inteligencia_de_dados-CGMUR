"""API de casos de sucesso — busca semântica e adaptação IA."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import CasoSucessoOut
from app.services.casos_sucesso_service import (
    adapt_case_for_municipio,
    get_caso,
    list_filter_options,
    search_casos,
    seed_casos_sucesso,
)

router = APIRouter()


class CaseSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    municipio_codigo: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)
    regiao: Optional[str] = None
    tipo_intervencao: Optional[str] = None
    faixa_populacao: Optional[str] = None
    programa_financiador: Optional[str] = None


class CaseSearchResponse(BaseModel):
    items: list[CasoSucessoOut]
    total: int
    search_mode: str = "semantic"


@router.post("/search", response_model=CaseSearchResponse)
def post_search_cases(body: CaseSearchRequest, db: Session = Depends(get_db)):
    items = search_casos(
        db,
        query=body.query,
        municipio_codigo=body.municipio_codigo,
        top_k=body.top_k,
        regiao=body.regiao,
        tipo_intervencao=body.tipo_intervencao,
        faixa_populacao=body.faixa_populacao,
    )
    if body.programa_financiador:
        needle = body.programa_financiador.lower()
        items = [i for i in items if needle in (i.get("programa_financiador") or "").lower()]
    mode = "semantic" if any(i.get("similarity") for i in items) else "keyword"
    return CaseSearchResponse(items=items, total=len(items), search_mode=mode)


@router.get("/filters")
def get_case_filters(db: Session = Depends(get_db)):
    return list_filter_options(db)


@router.get("/{case_id}", response_model=CasoSucessoOut)
def get_case_detail(case_id: int, db: Session = Depends(get_db)):
    row = get_caso(db, case_id)
    if not row:
        raise HTTPException(status_code=404, detail="Caso não encontrado")
    return row


@router.post("/{case_id}/adapt")
def adapt_case(case_id: int, codigo_ibge: str = Query(...), db: Session = Depends(get_db)):
    try:
        return adapt_case_for_municipio(db, case_id, codigo_ibge)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/seed")
def reseed_cases(
    force: bool = Query(default=False),
    embed: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    return seed_casos_sucesso(db, force=force, embed=embed)
