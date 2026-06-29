from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Municipio, MunicipioSeed, RelatorioMunicipal
from app.schemas import MunicipalReportHistoryItem, MunicipalReportResponse, SeiExportPackage
from app.services.audit_service import log_audit, resolve_actor
from app.security.municipio_access import (
    get_accessible_municipio,
    get_accessible_municipio_by_id,
)
from app.services.maturity_engine import PRATA_MIN_SCORE, compute_maturity
from app.services.report_generator import MunicipalReportGenerator
from app.services.sei_export import build_municipal_sei_package

router = APIRouter()


def _get_municipio(db: Session, municipio_id: int, request: Request) -> Municipio:
    return get_accessible_municipio_by_id(db, municipio_id, request=request)


def _report_response(record: RelatorioMunicipal) -> MunicipalReportResponse:
    return MunicipalReportResponse(
        id=record.id,
        municipio_id=record.municipio_id,
        codigo_ibge=record.codigo_ibge,
        nome_arquivo=record.nome_arquivo,
        tamanho_bytes=record.tamanho_bytes,
        status=record.status,
        sha256_hash=record.sha256_hash,
        gerado_em=record.gerado_em,
        download_url=f"/api/v1/reports/{record.id}/download",
        sei_export_url=f"/api/v1/reports/{record.id}/sei-export",
    )


def _assert_pdf_maturity_gate(db: Session, codigo_ibge: str, force: bool = False) -> None:
    if force:
        return
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == codigo_ibge).first()
    score = float(seed.maturity_score) if seed and seed.maturity_score is not None else None
    if score is None:
        try:
            score = float(compute_maturity(db, codigo_ibge)["score"])
        except Exception:
            score = 0.0
    if score < PRATA_MIN_SCORE:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Relatório PDF formal bloqueado: maturidade {score:.0f}% "
                f"(mínimo Prata = {PRATA_MIN_SCORE}%). "
                "Conclua o onboarding ou use ?force=true para override administrativo."
            ),
        )


@router.post("/municipal/{municipio_id}", response_model=MunicipalReportResponse)
def generate_municipal_report(
    municipio_id: int,
    request: Request,
    force: bool = Query(default=False, description="Override admin — ignora gate de maturidade Prata"),
    db: Session = Depends(get_db),
):
    """Compila dados PostGIS + integrações e gera PDF municipal."""
    actor = resolve_actor(request)
    muni = _get_municipio(db, municipio_id, request)
    _assert_pdf_maturity_gate(db, muni.codigo_ibge, force=force)
    try:
        record = MunicipalReportGenerator(db).generate(municipio_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao gerar relatório: {exc}") from exc

    if record.status != "concluido":
        raise HTTPException(status_code=500, detail=record.erro_mensagem or "Geração falhou.")

    log_audit(
        db,
        user=actor,
        action="report.force_override" if force else "report.generate",
        resource_type="relatorio_municipal",
        resource_id=record.id,
        codigo_ibge=muni.codigo_ibge,
        metadata={"force": force, "nome_arquivo": record.nome_arquivo, "sha256": record.sha256_hash},
        request=request,
    )
    return _report_response(record)


@router.post("/municipal/codigo/{codigo_ibge}", response_model=MunicipalReportResponse)
def generate_municipal_report_by_codigo(
    codigo_ibge: str,
    request: Request,
    force: bool = Query(default=False, description="Override admin — ignora gate de maturidade Prata"),
    db: Session = Depends(get_db),
):
    """Gera PDF a partir do código IBGE (alternativa ao id interno)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return generate_municipal_report(muni.id, request=request, force=force, db=db)


@router.get("/municipal/codigo/{codigo_ibge}/history", response_model=list[MunicipalReportHistoryItem])
def list_municipal_reports_by_codigo(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return list_municipal_reports(muni.id, request, db)


@router.get("/municipal/{municipio_id}/history", response_model=list[MunicipalReportHistoryItem])
def list_municipal_reports(municipio_id: int, request: Request, db: Session = Depends(get_db)):
    _get_municipio(db, municipio_id, request)
    rows = (
        db.query(RelatorioMunicipal)
        .filter(RelatorioMunicipal.municipio_id == municipio_id)
        .order_by(RelatorioMunicipal.gerado_em.desc())
        .limit(20)
        .all()
    )
    return [
        MunicipalReportHistoryItem(
            id=row.id,
            municipio_id=row.municipio_id,
            codigo_ibge=row.codigo_ibge,
            nome_arquivo=row.nome_arquivo,
            tamanho_bytes=row.tamanho_bytes,
            status=row.status,
            sha256_hash=row.sha256_hash,
            gerado_em=row.gerado_em,
            download_url=f"/api/v1/reports/{row.id}/download",
            sei_export_url=f"/api/v1/reports/{row.id}/sei-export",
        )
        for row in rows
    ]


@router.get("/{report_id}/sei-export", response_model=SeiExportPackage)
def export_sei_package(report_id: int, request: Request, db: Session = Depends(get_db)):
    record = db.query(RelatorioMunicipal).filter(RelatorioMunicipal.id == report_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
    if record.status != "concluido":
        raise HTTPException(status_code=409, detail="Relatório ainda não está disponível para exportação SEI.")

    get_accessible_municipio_by_id(db, record.municipio_id, request=request)
    muni = db.query(Municipio).filter(Municipio.id == record.municipio_id).first()
    base_url = str(request.base_url).rstrip("/")
    package = build_municipal_sei_package(record, muni, base_url=base_url)

    actor = resolve_actor(request)
    log_audit(
        db,
        user=actor,
        action="report.sei_export",
        resource_type="relatorio_municipal",
        resource_id=record.id,
        codigo_ibge=record.codigo_ibge,
        metadata={"sha256": package["integridade"]["hash"]},
        request=request,
    )
    return package


@router.get("/{report_id}/download")
def download_report(report_id: int, request: Request, db: Session = Depends(get_db)):
    record = db.query(RelatorioMunicipal).filter(RelatorioMunicipal.id == report_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")
    if record.status != "concluido":
        raise HTTPException(status_code=409, detail="Relatório ainda não está disponível para download.")

    get_accessible_municipio_by_id(db, record.municipio_id, request=request)
    path = Path(record.caminho_arquivo)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo PDF não encontrado no volume.")

    actor = resolve_actor(request)
    log_audit(
        db,
        user=actor,
        action="report.download",
        resource_type="relatorio_municipal",
        resource_id=record.id,
        codigo_ibge=record.codigo_ibge,
        metadata={"nome_arquivo": record.nome_arquivo},
        request=request,
    )

    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=record.nome_arquivo,
    )
