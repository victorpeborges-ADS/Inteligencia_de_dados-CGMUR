"""API de terreno 3D — config DEM, análise de encostas e processamento."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Municipio
from app.services.dem_processor import (
    TERRARIUM_DECODER,
    is_processed,
    load_meta,
    process_municipality_dem,
    slope_analysis,
)
from app.security.municipio_access import get_accessible_municipio

router = APIRouter()
DEM_STATIC_PREFIX = "/static/dem"


def _terrain_config(codigo_ibge: str, meta: dict) -> dict:
    base = os.getenv("PUBLIC_API_URL", "http://localhost:8000")
    return {
        "codigo_ibge": codigo_ibge,
        "nome": meta.get("nome"),
        "uf": meta.get("uf"),
        "bounds": meta.get("bounds"),
        "elevation_url": f"{base}{DEM_STATIC_PREFIX}/{codigo_ibge}/elevation.png",
        "texture_url": f"{base}{DEM_STATIC_PREFIX}/{codigo_ibge}/texture.png",
        "mesh_url": f"{base}{DEM_STATIC_PREFIX}/{codigo_ibge}/mesh.json",
        "flow_paths_url": f"{base}{DEM_STATIC_PREFIX}/{codigo_ibge}/flow_paths.geojson",
        "elevation_decoder": meta.get("elevation_decoder", TERRARIUM_DECODER),
        "image_size": meta.get("image_size"),
        "stats": meta.get("stats", {}),
        "dem_source": meta.get("dem_source"),
        "data_reference": meta.get("data_reference"),
        "default_exaggeration": meta.get("default_exaggeration", 2.5),
        "terrain_available": True,
    }


@router.get("/{codigo_ibge}/config")
def get_terrain_config(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    get_accessible_municipio(db, codigo_ibge, request=request)
    meta = load_meta(codigo_ibge)
    if not meta:
        raise HTTPException(
            status_code=404,
            detail="DEM não processado. Execute: python etl/etl_dem_srtm.py --municipio " + codigo_ibge,
        )
    return _terrain_config(codigo_ibge, meta)


@router.get("/slope-analysis/{codigo_ibge}")
def get_slope_analysis(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        return slope_analysis(db, codigo_ibge)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{codigo_ibge}/process")
def trigger_dem_process(
    codigo_ibge: str,
    request: Request,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    get_accessible_municipio(db, codigo_ibge, request=request)
    if is_processed(codigo_ibge) and not force:
        meta = load_meta(codigo_ibge)
        return {"status": "already_processed", "config": _terrain_config(codigo_ibge, meta or {})}
    try:
        meta = process_municipality_dem(db, codigo_ibge, force=force)
        return {"status": "processed", "config": _terrain_config(codigo_ibge, meta)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
