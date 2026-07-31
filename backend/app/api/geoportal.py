"""API Geoportal municipal — publicação CTM (Fase 16d.5)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.data_connectors.ctm_collector import catalog_ctm_targets, collect_ctm_municipality
from app.db import get_db
from app.security.municipio_access import get_accessible_municipio
from app.security.auth import Role, User, require_role
from app.services.geoportal_service import (
    get_geoportal_status,
    import_geoportal_publication,
    probe_geoportal_url,
    register_geoportal_api,
    register_geoportal_upload,
)

router = APIRouter()


class GeoportalApiRegisterRequest(BaseModel):
    tipo: str = Field(..., description="arcgis_rest | geojson_url | geoserver_wfs")
    url: str
    titulo: str = "Malha de bairros CTM"
    arcgis_where: str = "1=1"
    nome_campo_bairro: str | None = None
    geoserver_type_name: str | None = Field(
        default=None,
        description="Camada WFS (ex.: Limites_Municipais:bairros_2023) quando tipo=geoserver_wfs",
    )


class GeoportalProbeRequest(BaseModel):
    tipo: str
    url: str
    arcgis_where: str = "1=1"
    geoserver_type_name: str | None = None


@router.get("/{codigo_ibge}/status")
def geoportal_status(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return get_geoportal_status(db, muni)


@router.get("/ctm/catalog")
def geoportal_ctm_catalog():
    return {"municipios": catalog_ctm_targets()}


@router.post("/{codigo_ibge}/register-api")
def geoportal_register_api(
    codigo_ibge: str,
    payload: GeoportalApiRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    _gestor: User = Depends(require_role(Role.GESTOR)),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    type_name = payload.geoserver_type_name if payload.tipo == "geoserver_wfs" else payload.arcgis_where
    try:
        return register_geoportal_api(
            db,
            muni,
            tipo=payload.tipo,
            url=payload.url,
            titulo=payload.titulo,
            arcgis_where=type_name or payload.arcgis_where,
            nome_campo_bairro=payload.nome_campo_bairro,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{codigo_ibge}/upload")
async def geoportal_upload(
    codigo_ibge: str,
    request: Request,
    file: UploadFile = File(...),
    titulo: str = Form(default="Malha de bairros CTM"),
    db: Session = Depends(get_db),
    _gestor: User = Depends(require_role(Role.GESTOR)),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    content = await file.read()
    try:
        return register_geoportal_upload(
            db,
            muni,
            content=content,
            filename=file.filename or "malha.geojson",
            titulo=titulo,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{codigo_ibge}/import")
def geoportal_import(
    codigo_ibge: str,
    request: Request,
    publicacao_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _gestor: User = Depends(require_role(Role.GESTOR)),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    result = import_geoportal_publication(db, muni, publicacao_id=publicacao_id)
    if result.get("error") and result.get("skipped"):
        raise HTTPException(status_code=404, detail=result["error"])
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@router.post("/{codigo_ibge}/sync-ctm-registry")
def geoportal_sync_ctm_registry(
    codigo_ibge: str,
    request: Request,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    _gestor: User = Depends(require_role(Role.GESTOR)),
):
    """Importa malha do catálogo CTM nacional (geoportais já cadastrados)."""
    get_accessible_municipio(db, codigo_ibge, request=request)
    return collect_ctm_municipality(db, codigo_ibge, force=force)


@router.post("/probe-url")
def geoportal_probe_url(payload: GeoportalProbeRequest, _gestor: User = Depends(require_role(Role.GESTOR))):
    type_name = payload.geoserver_type_name if payload.tipo == "geoserver_wfs" else payload.arcgis_where
    return probe_geoportal_url(payload.tipo, payload.url, arcgis_where=type_name or payload.arcgis_where)
