from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DiagnosticoExecutivo, Municipio
from app.security.municipio_access import assert_codigo_ibge_access, get_accessible_municipio
from app.services.executive_diagnostic_engine import (
    diagnostic_to_dict,
    generate_executive_diagnostic,
)

router = APIRouter()


class ExecutiveDiagnosticResponse(BaseModel):
    id: int
    municipio_id: int
    codigo_ibge: str
    versao: int
    status: str
    headline: str
    conteudo: dict
    narrativa_md: str
    origem: str
    gerado_em: str | None


@router.post("/generate/{codigo_ibge}", response_model=ExecutiveDiagnosticResponse)
def generate_diagnostic(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        record = generate_executive_diagnostic(db, codigo_ibge, origem="manual")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return diagnostic_to_dict(record)


@router.get("/{codigo_ibge}", response_model=ExecutiveDiagnosticResponse)
def get_latest_diagnostic(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    record = (
        db.query(DiagnosticoExecutivo)
        .filter(DiagnosticoExecutivo.codigo_ibge == codigo_ibge)
        .order_by(DiagnosticoExecutivo.gerado_em.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Nenhum diagnóstico executivo gerado para este município.")
    return diagnostic_to_dict(record)


@router.get("/{codigo_ibge}/history")
def list_diagnostic_history(codigo_ibge: str, request: Request, limit: int = 10, db: Session = Depends(get_db)):
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    rows = (
        db.query(DiagnosticoExecutivo)
        .filter(DiagnosticoExecutivo.codigo_ibge == codigo_ibge)
        .order_by(DiagnosticoExecutivo.gerado_em.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "versao": row.versao,
                "headline": row.headline,
                "origem": row.origem,
                "gerado_em": row.gerado_em.isoformat() if row.gerado_em else None,
            }
            for row in rows
        ]
    }
