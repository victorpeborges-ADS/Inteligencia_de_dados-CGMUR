"""API de recarga e auditoria municipal."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.models import Municipio
from app.security.municipio_access import get_accessible_municipio
from app.services.municipio_audit_service import audit_municipio
from app.services.municipio_recarga_service import get_recarga_status, iniciar_recarga_background

router = APIRouter()


class RecargaRequest(BaseModel):
    fontes: list[str] = Field(
        default_factory=lambda: ["malha_ibge", "socioeconomico_censo", "s2id", "cemaden"]
    )


@router.get("/{codigo_ibge}/auditoria")
def get_auditoria_municipio(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return audit_municipio(db, muni, persist=False)


@router.post("/{codigo_ibge}/recarregar-dados-reais")
def recarregar_dados_reais(
    codigo_ibge: str,
    payload: RecargaRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    get_accessible_municipio(db, codigo_ibge, request=request)
    allowed = {"malha_ibge", "socioeconomico_censo", "s2id", "cemaden", "educacao_inep", "seguranca_sinesp", "territorios_especiais"}
    fontes = [f for f in payload.fontes if f in allowed]
    if not fontes:
        raise HTTPException(status_code=400, detail="Nenhuma fonte válida informada.")
    return iniciar_recarga_background(SessionLocal, codigo_ibge, fontes)


@router.get("/{codigo_ibge}/status-recarga")
def status_recarga(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    get_accessible_municipio(db, codigo_ibge, request=request)
    status = get_recarga_status(codigo_ibge)
    return status
