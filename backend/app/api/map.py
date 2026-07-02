"""Endpoints de mapa estático para apresentação."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Municipio
from app.security.municipio_access import assert_codigo_ibge_access, get_accessible_municipio
from app.services.map_screenshot_service import VALID_LAYERS, render_map_screenshot

router = APIRouter()


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
