from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.data_connectors.mapbiomas_collector import (
    collect_mapbiomas_municipality,
    get_urban_series,
    mapbiomas_status,
    sync_mapbiomas_batch,
)
from app.db import get_db
from app.data_connectors.orchestrator import IntegrationOrchestrator
from app.schemas import IntegrationStatusResponse, IntegrationSyncResponse
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
