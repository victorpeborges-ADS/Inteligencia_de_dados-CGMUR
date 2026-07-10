from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models import MunicipioSeed
from app.security.municipio_access import filter_seed_query, get_accessible_municipio
from app.security.auth import User, require_role, Role
from app.services.audit_service import resolve_actor
from app.services.catalog_coverage import BASE_CATALOG, coverage_for_code
from app.services.catalog_impact_service import (
    analyze_fonte_impact,
    build_maturity_detail,
    enrich_bases,
    rank_lacunas,
)
from app.services.catalog_sync_service import (
    get_source_preview,
    get_source_sync_meta,
    refresh_catalog_source,
)
from app.data_connectors.singedlab_rs_collector import row_to_dict, sync_singedlab_batch
from app.models import MunicipioSingedlabRs
from app.services.singedlab_import_service import run_singedlab_csv_import

router = APIRouter()

@router.get("/coverage")
def get_data_coverage(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    maturidade, bases, gaps = coverage_for_code(muni.codigo_ibge, db)
    enriched = enrich_bases(db, muni.codigo_ibge, bases)
    lacunas_ranking = rank_lacunas(bases)
    maturity_detail = build_maturity_detail(db, muni.codigo_ibge)
    return {
        "municipio": {
            "codigo_ibge": muni.codigo_ibge,
            "nome": muni.nome,
            "uf": muni.uf,
        },
        "maturidade_percentual": maturidade,
        "classificacao": "Alta" if maturidade >= 75 else ("Media" if maturidade >= 50 else "Baixa"),
        "bases": enriched,
        "lacunas_prioritarias": gaps[:5],
        "lacunas_ranking": lacunas_ranking,
        "maturity_detail": maturity_detail,
        "resumo": f"{muni.nome} possui {maturidade}% de maturidade informacional no radar Sinidu+Clima.",
    }


@router.get("/national")
def get_national_data_coverage(
    request: Request,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role(Role.GESTOR)),
):
    """Panorama agregado do catálogo nos municípios prioritários (respeita multi-tenant)."""
    actor = resolve_actor(request)
    query = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge.in_(settings.TARGET_IBGE_CODES))
    query = filter_seed_query(query, actor)
    seeds = query.order_by(MunicipioSeed.prioridade.asc()).all()

    if not seeds:
        raise HTTPException(status_code=404, detail="Nenhum município prioritário no escopo do perfil.")

    base_totals: dict[str, dict[str, int]] = {}
    municipio_rows = []
    gap_counter: dict[str, int] = {}

    for seed in seeds:
        maturidade, bases, gaps = coverage_for_code(seed.codigo_ibge, db)
        municipio_rows.append({
            "codigo_ibge": seed.codigo_ibge,
            "nome": seed.nome,
            "uf": seed.uf,
            "maturidade_percentual": maturidade,
            "onboarding_status": seed.onboarding_status,
            "lacunas_count": len(gaps),
        })
        for item in bases:
            bucket = base_totals.setdefault(item["id"], {"nome": item["nome"], "Integrado": 0, "Estimado": 0, "Em integracao": 0, "Ausente": 0, "Nao aplicavel": 0})
            status = item["status"]
            if status in bucket:
                bucket[status] += 1
        for gap in gaps:
            gap_counter[gap["id"]] = gap_counter.get(gap["id"], 0) + 1

    total = len(seeds)
    media_maturidade = round(sum(row["maturidade_percentual"] for row in municipio_rows) / total)
    bases_summary = []
    for base_id, counts in base_totals.items():
        integrado_pct = round((counts["Integrado"] / total) * 100)
        bases_summary.append({
            "id": base_id,
            "nome": counts["nome"],
            "integrado_pct": integrado_pct,
            "totals": {k: v for k, v in counts.items() if k != "nome"},
        })
    bases_summary.sort(key=lambda row: row["integrado_pct"])

    top_gaps = sorted(
        [{"id": k, "nome": base_totals[k]["nome"], "municipios": v} for k, v in gap_counter.items()],
        key=lambda row: row["municipios"],
        reverse=True,
    )[:8]

    return {
        "total_municipios": total,
        "media_maturidade_percentual": media_maturidade,
        "classificacao": "Alta" if media_maturidade >= 75 else ("Media" if media_maturidade >= 50 else "Baixa"),
        "bases": bases_summary,
        "lacunas_frequentes": top_gaps,
        "municipios": sorted(municipio_rows, key=lambda row: row["maturidade_percentual"]),
        "resumo": f"Panorama de {total} municípios prioritários — maturidade média {media_maturidade}%.",
    }


@router.get("/impact-analysis/{codigo_ibge}/{fonte_id}")
def get_impact_analysis(
    codigo_ibge: str,
    fonte_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        return analyze_fonte_impact(db, codigo_ibge, fonte_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/source-preview/{codigo_ibge}/{fonte_id}")
def get_source_data_preview(
    codigo_ibge: str,
    fonte_id: str,
    request: Request,
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    get_accessible_municipio(db, codigo_ibge, request=request)
    return {
        "fonte_id": fonte_id,
        "codigo_ibge": codigo_ibge,
        "meta": get_source_sync_meta(db, codigo_ibge, fonte_id),
        "registros": get_source_preview(db, codigo_ibge, fonte_id, limit=limit),
    }


@router.post("/refresh-source/{codigo_ibge}/{fonte_id}")
def refresh_source(
    codigo_ibge: str,
    fonte_id: str,
    request: Request,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    get_accessible_municipio(db, codigo_ibge, request=request)
    result = refresh_catalog_source(db, codigo_ibge, fonte_id, force=force)
    if not result.get("ok") and result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/refresh-all/{codigo_ibge}")
def refresh_all_integrated_sources(
    codigo_ibge: str,
    request: Request,
    db: Session = Depends(get_db),
):
    get_accessible_municipio(db, codigo_ibge, request=request)
    from app.services.background_jobs import run_catalog_refresh_job

    job_id = run_catalog_refresh_job(codigo_ibge)
    return {"job_id": job_id, "status": "queued"}


@router.get("/singedlab/{codigo_ibge}")
def get_singedlab_exposure(
    codigo_ibge: str,
    request: Request,
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    row = db.query(MunicipioSingedlabRs).filter(MunicipioSingedlabRs.codigo_ibge == codigo_ibge).first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Exposição SINGED Lab ainda não sincronizada — use refresh da fonte ibge_singedlab_rs.",
        )
    payload = row_to_dict(row)
    payload["municipio"] = {"codigo_ibge": muni.codigo_ibge, "nome": muni.nome, "uf": muni.uf}
    return payload


@router.post("/singedlab/sync-all")
def sync_singedlab_all_municipios(
    request: Request,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role(Role.GESTOR)),
):
    """Recarrega CSV curado para os 61 municípios prioritários."""
    summary = sync_singedlab_batch(db, force=True)
    return summary


@router.post("/singedlab/import-csv")
async def import_singedlab_csv(
    request: Request,
    file: UploadFile = File(...),
    sync_db: bool = Query(default=True, description="Sincroniza banco após merge no seed CSV"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_role(Role.GESTOR)),
):
    """Importa export CSV do portal IBGE SINGED Lab para o seed curado e opcionalmente sincroniza o banco."""
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .csv exportado do portal IBGE SINGED Lab.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo CSV vazio.")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Arquivo excede o limite de 5 MB.")

    try:
        return run_singedlab_csv_import(
            content,
            filename=filename,
            db=db if sync_db else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/refresh-job/{job_id}")
def get_refresh_job_status(job_id: str, request: Request):
    from app.services.background_jobs import get_job

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return job
