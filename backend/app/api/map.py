"""Endpoints de mapa estático para apresentação."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Municipio
from app.security.municipio_access import assert_codigo_ibge_access, get_accessible_municipio
from app.services.external_raster_service import (
    get_external_raster_config,
    get_external_raster_source,
    list_external_rasters,
    probe_external_raster_server,
)
from app.services.georedus_lst_service import fetch_lst_point, get_lst_observada_config
from app.services.map_screenshot_service import VALID_LAYERS, render_map_screenshot

router = APIRouter()


@router.get("/external-rasters")
def external_rasters_catalog(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Catálogo de camadas raster externas (mosaicjson) — sem ingestão PostGIS."""
    if codigo_ibge:
        assert_codigo_ibge_access(db, codigo_ibge, request=request)
    return {
        "provider": "georedus_mosaicjson",
        "tile_server_pattern": "mosaicjson/tiles/WebMercatorQuad/{z}/{x}/{y}.png",
        "layers": list_external_rasters(),
    }


@router.get("/external-rasters/{layer_id}/config")
def external_raster_config(
    layer_id: str,
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    rescale_min: float | None = Query(default=None),
    rescale_max: float | None = Query(default=None),
    ano: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Configuração de tiles para uma camada raster externa registrada."""
    if codigo_ibge:
        assert_codigo_ibge_access(db, codigo_ibge, request=request)
    cfg = get_external_raster_config(layer_id, rescale_min=rescale_min, rescale_max=rescale_max, ano=ano)
    if cfg.get("error"):
        raise HTTPException(status_code=404, detail=cfg["error"])
    return cfg


@router.get("/external-rasters/{layer_id}/health")
def external_raster_health(layer_id: str):
    """Probe do raster-server (mosaicjson/info) — diagnóstico sem baixar tiles."""
    result = probe_external_raster_server(layer_id)
    if not result.get("ok") and result.get("error") == "Camada desconhecida":
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/lst-observada/config")
def lst_observada_config(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    rescale_min: float | None = Query(default=None),
    rescale_max: float | None = Query(default=None),
    ano: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Configuração de tiles raster LST (GeoReDUS / TiTiler)."""
    if codigo_ibge:
        assert_codigo_ibge_access(db, codigo_ibge, request=request)
    return get_lst_observada_config(rescale_min, rescale_max, ano)


@router.get("/external-rasters/{layer_id}/point")
def external_raster_point(
    layer_id: str,
    request: Request,
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Amostra valor do raster externo no ponto (LST GeoReDUS via TiTiler mosaicjson/point)."""
    if codigo_ibge:
        assert_codigo_ibge_access(db, codigo_ibge, request=request)

    source = get_external_raster_source(layer_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Camada raster desconhecida: {layer_id}")
    if not source.supports_point_query:
        raise HTTPException(status_code=400, detail=f"Camada {layer_id} não suporta consulta por ponto")

    temperatura_c: float | None = None
    if layer_id == "lst_observada":
        temperatura_c = fetch_lst_point(lon, lat)

    return {
        "layer_id": layer_id,
        "label": source.label,
        "lon": round(lon, 6),
        "lat": round(lat, 6),
        "temperatura_c": temperatura_c,
        "value": temperatura_c,
        "unit": source.unit or "°C",
        "qualidade": source.quality,
        "fonte": source.source,
        "periodo": source.periodo_label,
        "attribution": source.attribution,
        "georedus_url": source.georedus_url,
        "disponivel": temperatura_c is not None,
        "nota": (
            "Temperatura de superfície terrestre (LST) observada no mosaico GeoReDUS "
            f"({source.periodo_label}) — valor amostrado no pixel sob o clique."
            if temperatura_c is not None
            else "Sem valor LST neste ponto (fora da cobertura do mosaico ou falha na consulta GeoReDUS)."
        ),
    }


@router.get("/screenshot/{codigo_ibge}")
def map_screenshot(
    codigo_ibge: str,
    request: Request,
    layer: str = Query(default="vulnerabilidade"),
    format: str = Query(default="png", pattern="^(png|base64)$"),
    db: Session = Depends(get_db),
):
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    layer_key = (layer or "vulnerabilidade").lower()
    if layer_key not in VALID_LAYERS:
        raise HTTPException(status_code=400, detail=f"Camada inválida. Use: {', '.join(sorted(VALID_LAYERS))}")

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise HTTPException(status_code=404, detail="Município não encontrado.")

    try:
        png = render_map_screenshot(db, muni, layer_key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao gerar mapa: {exc}") from exc

    if format == "base64":
        return {"layer": layer_key, "png_base64": base64.b64encode(png).decode("ascii"), "width": 1200, "height": 700}

    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
