from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.data_connectors.mapbiomas_collector import (
    collect_mapbiomas_municipality,
    get_urban_series,
    mapbiomas_status,
    sync_mapbiomas_batch,
)
from app.data_connectors.s2id_collector import collect_s2id_municipality
from app.data_connectors.saude_collector import collect_saude_municipality
from app.data_connectors.territorial_mesh_collector import collect_territorial_municipality, import_bairros_from_geojson
from app.data_connectors.ctm_collector import collect_ctm_municipality, catalog_ctm_targets
from app.db import get_db
from app.data_connectors.orchestrator import IntegrationOrchestrator
from app.models import Municipio
from app.schemas import GeoJSONFeatureCollection, IntegrationStatusResponse, IntegrationSyncResponse
from app.security.municipio_access import get_accessible_municipio
from app.security.auth import Role, User, require_role

router = APIRouter()


@router.get("/status", response_model=IntegrationStatusResponse)
def integration_status(db: Session = Depends(get_db)):
    orchestrator = IntegrationOrchestrator(db)
    return {"sources": orchestrator.status()}


@router.post("/sync", response_model=IntegrationSyncResponse)
def integration_sync(db: Session = Depends(get_db)):
    summary = IntegrationOrchestrator(db).sync_all()
    return {"summary": summary, "sources": IntegrationOrchestrator(db).status()}


@router.get("/mapbiomas/status")
def mapbiomas_integration_status(
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return mapbiomas_status(db, codigo_ibge)


@router.get("/mapbiomas/{codigo_ibge}")
def mapbiomas_municipality_series(codigo_ibge: str, db: Session = Depends(get_db)):
    code = str(codigo_ibge).strip().zfill(7)[:7]
    series = get_urban_series(db, code)
    if not series:
        raise HTTPException(status_code=404, detail="Série MapBiomas indisponível para o município.")
    return {
        "codigo_ibge": code,
        "urban_series": series,
        "status": mapbiomas_status(db, code),
    }


@router.post("/mapbiomas/sync/{codigo_ibge}")
def mapbiomas_sync_municipality(
    codigo_ibge: str,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    return collect_mapbiomas_municipality(db, codigo_ibge, force=force)


@router.post("/mapbiomas/sync-batch")
def mapbiomas_sync_batch(
    limit: int = Query(default=61, ge=1, le=100),
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    return sync_mapbiomas_batch(db, limit=limit, force=force)


@router.post("/socioeconomic/sync")
def socioeconomic_sync(
    codigo_ibge: str = Query(...),
    db: Session = Depends(get_db),
):
    """Recalibra renda por setor/bairro com PIB IBGE e gradiente intra-urbano."""
    from app.models import Municipio
    from app.services.socioeconomic_engine import enrich_municipal_socioeconomics, ranking_bairros_por_renda

    code = str(codigo_ibge).strip().zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise HTTPException(status_code=404, detail=f"Município {code} não encontrado no PostGIS.")
    summary = enrich_municipal_socioeconomics(db, muni)
    ranking = ranking_bairros_por_renda(db, muni, limit=5)
    return {"calibracao": summary, "ranking": ranking}


@router.post("/s2id/sync/{codigo_ibge}")
def s2id_sync_municipality(
    codigo_ibge: str,
    force: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Carrega eventos S2ID curados (piloto) ou distribuídos por bairro (estimativa)."""
    return collect_s2id_municipality(db, codigo_ibge, force=force)


@router.post("/saude/sync/{codigo_ibge}")
def saude_sync_municipality(
    codigo_ibge: str,
    force: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Carrega estabelecimentos CNES ou malha curada de saúde por município."""
    return collect_saude_municipality(db, codigo_ibge, force=force)


@router.post("/territorial/sync/{codigo_ibge}")
def territorial_sync_municipality(
    codigo_ibge: str,
    force: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Atualiza malha territorial — IBGE oficial (prioritário) ou Voronoi estimado."""
    return collect_territorial_municipality(db, codigo_ibge, force=force)


@router.post("/territorial/fetch-ibge/{codigo_ibge}")
def territorial_fetch_ibge(
    codigo_ibge: str,
    request: Request,
    force: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Baixa e importa malha oficial IBGE Censo 2022 (bairros + setores censitários)."""
    from app.data_connectors.official_bairros_collector import import_official_ibge_mesh

    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return import_official_ibge_mesh(db, muni, force=force)


@router.post("/territorial/import/{codigo_ibge}")
def territorial_import_geojson(
    codigo_ibge: str,
    payload: GeoJSONFeatureCollection,
    request: Request,
    db: Session = Depends(get_db),
):
    """Importa malha oficial de bairros (GeoJSON CTM / geoportal municipal)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return import_bairros_from_geojson(db, muni, payload.model_dump())


@router.get("/territorial/ctm/catalog")
def territorial_ctm_catalog():
    """Inventário de fontes CTM para municípios abaixo do patamar Salvador/Recife."""
    return {"municipios": catalog_ctm_targets()}


@router.post("/territorial/ctm/sync/{codigo_ibge}")
def territorial_ctm_sync(
    codigo_ibge: str,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Baixa malha CTM do geoportal municipal cadastrado e importa bairros nomeados."""
    return collect_ctm_municipality(db, codigo_ibge, force=force)
