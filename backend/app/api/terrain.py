"""API de terreno 3D — config DEM, análise de encostas e processamento."""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Municipio
from app.services.dem_processor import (
    TERRARIUM_DECODER,
    import_local_dem_bytes,
    is_processed,
    load_meta,
    process_municipality_dem,
    slope_analysis,
)
from app.security.municipio_access import get_accessible_municipio

router = APIRouter()


class TerrainProfileBody(BaseModel):
    coordinates: list[list[float]] = Field(..., description="LineString [[lon,lat], ...]")
    samples: int = Field(80, ge=10, le=200)
    water_level_m: float | None = None
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
        "dem_resolution_m": meta.get("dem_resolution_m"),
        "vertical_accuracy_m": meta.get("vertical_accuracy_m"),
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


@router.post("/{codigo_ibge}/profile")
def terrain_profile(
    codigo_ibge: str,
    body: TerrainProfileBody,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Seção transversal de elevação ao longo de uma linha (17f.5)."""
    get_accessible_municipio(db, codigo_ibge, request=request)
    from app.services.terrain_profile_service import build_terrain_profile

    result = build_terrain_profile(
        db,
        codigo_ibge,
        body.coordinates,
        samples=body.samples,
        water_level_m=body.water_level_m,
    )
    if result.get("erro") == "municipio_nao_encontrado":
        raise HTTPException(status_code=404, detail="Município não encontrado")
    if result.get("erro") == "dem_indisponivel":
        raise HTTPException(status_code=404, detail=result.get("mensagem") or "DEM indisponível")
    if result.get("erro") in {"linha_invalida", "linha_degenerada"}:
        raise HTTPException(status_code=400, detail=result.get("mensagem") or result["erro"])
    return result


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


@router.post("/{codigo_ibge}/import-local-dem")
async def import_local_dem(
    codigo_ibge: str,
    request: Request,
    file: UploadFile = File(...),
    reprocess: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Importa GeoTIFF LiDAR/DSM municipal (<5 m) e opcionalmente reprocessa tiles 3D."""
    get_accessible_municipio(db, codigo_ibge, request=request)
    if not file.filename or not file.filename.lower().endswith((".tif", ".tiff", ".geotiff")):
        raise HTTPException(status_code=400, detail="Envie um GeoTIFF (.tif/.tiff)")
    content = await file.read()
    if len(content) < 2048:
        raise HTTPException(status_code=400, detail="Arquivo GeoTIFF inválido ou vazio")
    dest = import_local_dem_bytes(codigo_ibge, content)
    if not reprocess:
        return {"status": "imported", "path": str(dest)}
    try:
        meta = process_municipality_dem(db, codigo_ibge, force=True)
        return {"status": "processed", "path": str(dest), "config": _terrain_config(codigo_ibge, meta)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
