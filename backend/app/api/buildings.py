"""API de edificações: LOD1, nDSM, 3D Tiles, CityJSON, qualidade (17c.5) e tiles API (17c.4)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.data_connectors.building_footprints_collector import collect_buildings_municipality
from app.data_connectors.cache import cache_get_bytes
from app.db import get_db
from app.models import Edificacao
from app.security.auth import Role, User, require_role
from app.security.municipio_access import get_accessible_municipio
from app.services.building_3dtiles_service import (
    build_3dtiles_for_municipality,
    status_3dtiles,
)
from app.services.building_lod2_mesh_service import (
    build_lod2_for_bbox,
    lod2_dir,
    status_lod2,
)
from app.services.building_cityjson_service import (
    build_citymodel_for_municipality,
    citymodel_muni_dir,
    status_citymodel,
)
from app.services.building_quality_service import (
    normalize_municipality_quality,
    quality_summary,
)
from app.services.building_tiles_api_service import (
    GEOJSON_CACHE_TTL,
    TILE_CACHE_TTL,
    TILESET_CACHE_TTL,
    build_mvt_tile,
    get_cached_buildings_geojson,
    get_cached_glb,
    get_cached_tileset_json,
    invalidate_gemeo_tile_cache,
    mvt_cache_key,
    tile_api_status,
)
from pydantic import BaseModel, Field

router = APIRouter()


class BuildingsQueueItem(BaseModel):
    codigo_ibge: str = Field(..., min_length=7, max_length=7)
    force: bool = False


class BuildingsQueueBatch(BaseModel):
    codigos: list[str] = Field(default_factory=list)
    uf: str | None = None
    limit: int = Field(default=15, ge=1, le=40)
    force: bool = False
    start_job: bool = True


def _cache_headers(ttl: int, *, hit: bool | None = None) -> dict[str, str]:
    headers = {
        "Cache-Control": f"public, max-age={ttl}",
        "X-Sinidu-Cache-TTL": str(ttl),
    }
    if hit is not None:
        headers["X-Sinidu-Cache"] = "HIT" if hit else "MISS"
    return headers


@router.get("/queue/status")
def buildings_queue_status(_admin: User = Depends(require_role(Role.ADMIN))):
    """Status da fila Overpass de footprints (18c.2)."""
    from app.services.building_osm_queue_service import queue_status

    return queue_status()


@router.post("/queue")
def buildings_queue_enqueue(
    body: BuildingsQueueItem,
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    """Enfileira ingestão OSM de um município."""
    from app.services.audit_service import log_audit, resolve_actor
    from app.services.building_osm_queue_service import enqueue_buildings

    muni = get_accessible_municipio(db, body.codigo_ibge, request=request)
    try:
        out = enqueue_buildings(muni.codigo_ibge, force=body.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_audit(
        db,
        user=resolve_actor(request),
        action="buildings.queue_enqueue",
        resource_type="municipio",
        codigo_ibge=muni.codigo_ibge,
        metadata={"force": body.force, "enqueued": out.get("enqueued")},
        request=request,
    )
    return out


@router.post("/queue/batch")
def buildings_queue_batch(
    body: BuildingsQueueBatch,
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    """Enfileira lote (lista de códigos ou UF) e opcionalmente inicia job."""
    from app.services.audit_service import log_audit, resolve_actor
    from app.services.background_jobs import get_job, run_buildings_osm_queue_job
    from app.services.building_osm_queue_service import enqueue_many, enqueue_uf

    if body.uf:
        out = enqueue_uf(body.uf, limit=body.limit, force=body.force)
    elif body.codigos:
        codes = [str(c).zfill(7)[:7] for c in body.codigos if str(c).strip()]
        out = enqueue_many(codes[: body.limit], force=body.force)
    else:
        raise HTTPException(status_code=400, detail="Informe uf ou codigos.")

    job_id = None
    if body.start_job and out.get("added", 0) > 0:
        job_id = run_buildings_osm_queue_job(max_items=min(body.limit, 40))
        out["job_id"] = job_id
        out["job"] = get_job(job_id)

    log_audit(
        db,
        user=resolve_actor(request),
        action="buildings.queue_batch",
        resource_type="buildings_queue",
        resource_id=body.uf or "codigos",
        metadata={"added": out.get("added"), "job_id": job_id},
        request=request,
    )
    return out


@router.post("/queue/drain")
def buildings_queue_drain(
    max_items: int = Query(default=10, ge=1, le=40),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    """Processa itens pendentes da fila (síncrono — preferir job)."""
    from app.services.building_osm_queue_service import drain_queue

    return drain_queue(max_items=max_items)


@router.get("/{codigo_ibge}")
def get_buildings(
    codigo_ibge: str,
    request: Request,
    limit: int | None = Query(default=None, ge=1, le=20000),
    ensure: bool = Query(default=True, description="Ingere OSM se a tabela estiver vazia"),
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        data = get_cached_buildings_geojson(
            db, muni.codigo_ibge, limit=limit, ensure=ensure, use_cache=True
        )
        hit = data.pop("_cache", None) == "hit"
        return JSONResponse(content=data, headers=_cache_headers(GEOJSON_CACHE_TTL, hit=hit))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{codigo_ibge}/geojson")
def get_buildings_geojson(
    codigo_ibge: str,
    request: Request,
    limit: int | None = Query(default=None, ge=1, le=20000),
    ensure: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """17c.4 — alias GeoJSON com cache Redis."""
    return get_buildings(codigo_ibge, request, limit=limit, ensure=ensure, db=db)


@router.get("/{codigo_ibge}/status")
def buildings_status(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    count = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    by_q: dict[str, int] = {}
    by_fonte: dict[str, int] = {}
    if count:
        rows = (
            db.query(Edificacao.qualidade, Edificacao.fonte_altura)
            .filter(Edificacao.municipio_id == muni.id)
            .all()
        )
        for q, fonte in rows:
            by_q[q or "Derivado"] = by_q.get(q or "Derivado", 0) + 1
            by_fonte[fonte or "heuristic"] = by_fonte.get(fonte or "heuristic", 0) + 1
    tiles = status_3dtiles(muni.codigo_ibge)
    city = status_citymodel(muni.codigo_ibge)
    try:
        quality = quality_summary(db, muni.codigo_ibge)
    except ValueError:
        quality = None
    return {
        "codigo_ibge": muni.codigo_ibge,
        "count": count,
        "por_qualidade": by_q,
        "por_fonte_altura": by_fonte,
        "por_selo_3d": (quality or {}).get("por_selo_3d", {}),
        "disponivel": count > 0,
        "tiles_3d": tiles,
        "citymodel": city,
        "qualidade_3d": quality,
        "tiles_api": tile_api_status(db, muni.codigo_ibge),
    }


@router.post("/{codigo_ibge}/sync")
def sync_buildings(
    codigo_ibge: str,
    request: Request,
    force: bool = Query(default=False),
    async_job: bool = Query(
        default=False,
        description="Se true, enfileira na fila Overpass com backoff (18c.2)",
    ),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    if async_job:
        from app.services.background_jobs import get_job, run_buildings_osm_queue_job
        from app.services.building_osm_queue_service import enqueue_buildings

        queued = enqueue_buildings(muni.codigo_ibge, force=force, priority=10)
        job_id = run_buildings_osm_queue_job(max_items=5)
        return {"async": True, "queue": queued, "job_id": job_id, "job": get_job(job_id)}
    try:
        out = collect_buildings_municipality(db, muni.codigo_ibge, force=force)
        invalidate_gemeo_tile_cache(muni.codigo_ibge)
        return out
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{codigo_ibge}/sync-microsoft")
def sync_buildings_microsoft(
    codigo_ibge: str,
    request: Request,
    force: bool = Query(default=True),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    """Ingere Microsoft Global Building Footprints (fallback quando OSM é escasso)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        from app.data_connectors.microsoft_buildings_collector import (
            collect_microsoft_buildings_municipality,
        )

        out = collect_microsoft_buildings_municipality(
            db, muni.codigo_ibge, force=force
        )
        invalidate_gemeo_tile_cache(muni.codigo_ibge)
        return out
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{codigo_ibge}/refine-ndsm")
def refine_ndsm_heights(
    codigo_ibge: str,
    request: Request,
    force_rebuild: bool = Query(default=False, description="Regenera nDSM mesmo se cached"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    """17a.6 — atualiza altura LOD1 a partir de nDSM (DSM − DTM proxy)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        from app.services.ndsm_service import refine_building_heights_from_ndsm

        out = refine_building_heights_from_ndsm(
            db, muni.codigo_ibge, force_rebuild_ndsm=force_rebuild
        )
        invalidate_gemeo_tile_cache(muni.codigo_ibge)
        return out
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{codigo_ibge}/quality")
def buildings_quality(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """17c.5 — selos LiDAR / OSM / Estimado e qualidade canônica."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        return quality_summary(db, muni.codigo_ibge)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{codigo_ibge}/normalize-quality")
def buildings_normalize_quality(
    codigo_ibge: str,
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    """17c.5 — backfill de qualidade a partir de fonte_altura."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        out = normalize_municipality_quality(db, muni.codigo_ibge)
        invalidate_gemeo_tile_cache(muni.codigo_ibge)
        return out
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{codigo_ibge}/tiles/status")
def buildings_tiles_api_status(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """17c.4 — endpoints e TTLs da API de tiles do gêmeo."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return tile_api_status(db, muni.codigo_ibge)


@router.get("/{codigo_ibge}/tiles/{z}/{x}/{y}.mvt")
def buildings_mvt_tile(
    codigo_ibge: str,
    z: int,
    x: int,
    y: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """17c.4 — tile vetorial MVT (PostGIS) com cache Redis."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        key = mvt_cache_key(muni.codigo_ibge, z, x, y)
        had = cache_get_bytes(key) is not None
        tile = build_mvt_tile(db, muni.codigo_ibge, z, x, y, use_cache=True)
        return Response(
            content=tile,
            media_type="application/vnd.mapbox-vector-tile",
            headers=_cache_headers(TILE_CACHE_TTL, hit=had),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MVT indisponível: {exc}") from exc


@router.post("/{codigo_ibge}/tiles/invalidate-cache")
def buildings_invalidate_tile_cache(
    codigo_ibge: str,
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    deleted = invalidate_gemeo_tile_cache(muni.codigo_ibge)
    return {"codigo_ibge": muni.codigo_ibge, "deleted_keys": deleted}


@router.get("/{codigo_ibge}/3dtiles/status")
def tiles_3d_status(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """17c.1 — status do tileset 3D Tiles do município."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return status_3dtiles(muni.codigo_ibge)


@router.post("/{codigo_ibge}/3dtiles/build")
def tiles_3d_build(
    codigo_ibge: str,
    request: Request,
    force: bool = Query(default=False),
    limit: int = Query(default=3500, ge=1, le=5000),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    """17c.1 — gera tileset.json + content.glb (LOD1)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        out = build_3dtiles_for_municipality(
            db, muni.codigo_ibge, force=force, limit=limit, ensure_buildings=True
        )
        invalidate_gemeo_tile_cache(muni.codigo_ibge)
        return out
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{codigo_ibge}/3dtiles/tileset.json")
def tiles_3d_tileset(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """17c.4 — tileset.json via API com cache Redis (gera sob demanda se ausente)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        doc = get_cached_tileset_json(db, muni.codigo_ibge, ensure_build=True, use_cache=True)
        hit = doc.pop("_cache", None) == "hit"
        return JSONResponse(content=doc, headers=_cache_headers(TILESET_CACHE_TTL, hit=hit))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Tileset indisponível: {exc}") from exc


@router.get("/{codigo_ibge}/3dtiles/content.glb")
def tiles_3d_content(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """17c.4 — content.glb via API com cache Redis."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        from app.services.building_tiles_api_service import glb_cache_key

        key = glb_cache_key(muni.codigo_ibge)
        had = cache_get_bytes(key) is not None
        data, _path = get_cached_glb(db, muni.codigo_ibge, ensure_build=True, use_cache=True)
        return Response(
            content=data,
            media_type="model/gltf-binary",
            headers={
                **_cache_headers(TILESET_CACHE_TTL, hit=had),
                "Content-Disposition": 'inline; filename="content.glb"',
            },
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"GLB indisponível: {exc}") from exc


@router.get("/{codigo_ibge}/3dtiles/lod2/status")
def tiles_lod2_status(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """18b.1 — status do tileset LOD2-lite (amostra bbox)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return status_lod2(muni.codigo_ibge)


@router.post("/{codigo_ibge}/3dtiles/build-lod2")
def tiles_lod2_build(
    codigo_ibge: str,
    request: Request,
    west: float | None = Query(default=None),
    south: float | None = Query(default=None),
    east: float | None = Query(default=None),
    north: float | None = Query(default=None),
    force: bool = Query(default=False),
    limit: int = Query(default=400, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    """18b.1 — gera GLB/tileset LOD2-lite a partir do nDSM no bbox."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        out = build_lod2_for_bbox(
            db,
            muni.codigo_ibge,
            west=west,
            south=south,
            east=east,
            north=north,
            force=force,
            limit=limit,
            ensure_buildings=True,
        )
        return out
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{codigo_ibge}/3dtiles/lod2/tileset.json")
def tiles_lod2_tileset(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """18b.1 — tileset.json LOD2."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    path = lod2_dir(muni.codigo_ibge) / "tileset.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="LOD2 indisponível — gere com POST .../build-lod2")
    return JSONResponse(content=json.loads(path.read_text(encoding="utf-8")))


@router.get("/{codigo_ibge}/3dtiles/lod2/content.glb")
def tiles_lod2_content(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """18b.1 — content.glb LOD2."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    path = lod2_dir(muni.codigo_ibge) / "content.glb"
    if not path.exists():
        raise HTTPException(status_code=404, detail="LOD2 GLB indisponível — gere com POST .../build-lod2")
    return FileResponse(
        path,
        media_type="model/gltf-binary",
        filename="content.glb",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/{codigo_ibge}/3dtiles/lod2/footprints.geojson")
def tiles_lod2_footprints(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """18b.2 — footprints GeoJSON da amostra LOD2 (para fill-extrusion no MapLibre)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    path = lod2_dir(muni.codigo_ibge) / "footprints.geojson"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Footprints LOD2 indisponíveis — gere com POST .../build-lod2?force=true",
        )
    return JSONResponse(
        content=json.loads(path.read_text(encoding="utf-8")),
        headers={"Cache-Control": "public, max-age=120"},
    )


@router.get("/{codigo_ibge}/cityjson/status")
def cityjson_status(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """17c.2 — status do modelo CityJSON/CityGML."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return status_citymodel(muni.codigo_ibge)


@router.post("/{codigo_ibge}/cityjson/build")
def cityjson_build(
    codigo_ibge: str,
    request: Request,
    force: bool = Query(default=False),
    limit: int = Query(default=3500, ge=1, le=5000),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    """17c.2 — gera CityJSON 2.0 + CityGML 2.0 (Building LOD1)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    try:
        return build_citymodel_for_municipality(
            db, muni.codigo_ibge, force=force, limit=limit, ensure_buildings=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{codigo_ibge}/cityjson/model.city.json")
def cityjson_download(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """Serve model.city.json (gera sob demanda se ausente)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    path = citymodel_muni_dir(muni.codigo_ibge) / "model.city.json"
    if not path.exists():
        try:
            build_citymodel_for_municipality(db, muni.codigo_ibge, force=False)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"CityJSON indisponível: {exc}") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="model.city.json não encontrado")
    return FileResponse(path, media_type="application/json", filename="model.city.json")


@router.get("/{codigo_ibge}/citygml/model.gml")
def citygml_download(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """Serve model.gml (gera sob demanda se ausente)."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    path = citymodel_muni_dir(muni.codigo_ibge) / "model.gml"
    if not path.exists():
        try:
            build_citymodel_for_municipality(db, muni.codigo_ibge, force=False)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=f"CityGML indisponível: {exc}") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="model.gml não encontrado")
    return FileResponse(path, media_type="application/gml+xml", filename="model.gml")
