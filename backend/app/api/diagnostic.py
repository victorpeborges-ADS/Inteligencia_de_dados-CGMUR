from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DiagnosticoExecutivo, Municipio
from app.security.municipio_access import assert_codigo_ibge_access, get_accessible_municipio
from app.services.audit_service import log_audit, resolve_actor
from app.services.diagnostic_report import ensure_diagnostic_pdf
from app.services.executive_diagnostic_engine import (
    diagnostic_to_dict,
    generate_executive_diagnostic,
)
from app.services.presentation_service import build_presentation_payload

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
    narrativa_ia: str | None = None
    narrativa_ia_meta: dict | None = None
    origem: str
    gerado_em: str | None
    nome_arquivo: str | None = None
    tamanho_bytes: int | None = None
    download_url: str | None = None


@router.post("/generate/{codigo_ibge}", response_model=ExecutiveDiagnosticResponse)
def generate_diagnostic(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request)
    get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        record = generate_executive_diagnostic(db, codigo_ibge, origem="manual")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    conteudo = record.conteudo or {}
    log_audit(
        db,
        user=actor,
        action="diagnostic.generate",
        resource_type="diagnostico_executivo",
        resource_id=record.id,
        codigo_ibge=codigo_ibge,
        metadata={
            "versao": record.versao,
            "score": conteudo.get("score_sinidu"),
            "origem": record.origem,
        },
        request=request,
    )
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


@router.get("/{codigo_ibge}/presentation")
def get_presentation_data(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request)
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    try:
        payload = build_presentation_payload(db, codigo_ibge)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    log_audit(
        db,
        user=actor,
        action="presentation.view",
        resource_type="apresentacao",
        codigo_ibge=codigo_ibge,
        metadata={"slides": 8},
        request=request,
    )
    return payload


@router.get("/{codigo_ibge}/download-pdf")
def download_diagnostic_pdf(
    codigo_ibge: str,
    request: Request,
    versao: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    actor = resolve_actor(request)
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    query = db.query(DiagnosticoExecutivo).filter(DiagnosticoExecutivo.codigo_ibge == codigo_ibge)
    if versao is not None:
        record = query.filter(DiagnosticoExecutivo.versao == versao).first()
    else:
        record = query.order_by(DiagnosticoExecutivo.gerado_em.desc()).first()
    if not record:
        raise HTTPException(status_code=404, detail="Diagnóstico não encontrado.")

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise HTTPException(status_code=404, detail="Município não encontrado.")

    try:
        path = ensure_diagnostic_pdf(record, muni)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao gerar PDF: {exc}") from exc

    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo PDF não encontrado.")

    log_audit(
        db,
        user=actor,
        action="diagnostic.download_pdf",
        resource_type="diagnostico_executivo",
        resource_id=record.id,
        codigo_ibge=codigo_ibge,
        metadata={"versao": record.versao, "arquivo": path.name},
        request=request,
    )

    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name,
    )


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
                **diagnostic_to_dict(row),
                "id": row.id,
                "versao": row.versao,
                "headline": row.headline,
                "origem": row.origem,
                "gerado_em": row.gerado_em.isoformat() if row.gerado_em else None,
            }
            for row in rows
        ]
    }
