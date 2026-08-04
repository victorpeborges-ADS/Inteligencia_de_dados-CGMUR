"""Comparativo simples mancha Sinidu × hazard GloFAS RP100."""

from __future__ import annotations

import logging
from typing import Any

from shapely.geometry import shape
from shapely.ops import unary_union
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _union_flood_bands(flood_fc: dict[str, Any] | None):
    if not flood_fc or not flood_fc.get("features"):
        return None
    geoms = []
    for feat in flood_fc["features"]:
        props = feat.get("properties") or {}
        if props.get("layer_type") and props.get("layer_type") not in ("flood_band", "simulation", None):
            if props.get("layer_type") == "landslide":
                continue
        band = props.get("depth_band")
        if band and band not in ("moderada", "critica", "superficial"):
            # ainda assim inclui se for polígono de mancha
            pass
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            g = shape(geom)
            if not g.is_empty and g.geom_type in ("Polygon", "MultiPolygon"):
                geoms.append(g)
        except Exception:
            continue
    if not geoms:
        return None
    try:
        return unary_union(geoms)
    except Exception:
        return geoms[0]


def _area_km2(geom, lat_c: float) -> float:
    """Área aproximada km² a partir de graus."""
    import math

    if geom is None or geom.is_empty:
        return 0.0
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * max(0.2, abs(math.cos(math.radians(lat_c))))
    return float(geom.area) * m_per_deg_lat * m_per_deg_lon / 1e6


def compare_flood_to_glofas(
    db: Session,
    codigo_ibge: str,
    flood_fc: dict[str, Any] | None,
) -> dict[str, Any]:
    """Retorna overlap_pct da mancha Sinidu com GloFAS RP100 (quando disponível)."""
    defaults = {
        "ok": False,
        "overlap_pct": None,
        "sinidu_area_km2": None,
        "glofas_area_km2": None,
        "intersection_km2": None,
        "nota": "GloFAS indisponível ou sem mancha",
    }
    flood_u = _union_flood_bands(flood_fc)
    if flood_u is None:
        return defaults

    try:
        from app.services.glofas_hazard_service import build_glofas_rp100_geojson

        glofas_fc = build_glofas_rp100_geojson(db, codigo_ibge)
    except Exception as exc:
        logger.info("GloFAS compare load: %s", exc)
        return {**defaults, "nota": f"Falha ao carregar GloFAS: {exc}"}

    glofas_geoms = []
    for feat in glofas_fc.get("features") or []:
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            g = shape(geom)
            if not g.is_empty:
                glofas_geoms.append(g)
        except Exception:
            continue
    if not glofas_geoms:
        return {**defaults, "nota": "GloFAS sem polígonos neste município"}

    try:
        glofas_u = unary_union(glofas_geoms)
        inter = flood_u.intersection(glofas_u)
    except Exception as exc:
        return {**defaults, "nota": f"Interseção falhou: {exc}"}

    lat_c = float(flood_u.centroid.y)
    a_sin = _area_km2(flood_u, lat_c)
    a_glo = _area_km2(glofas_u, lat_c)
    a_int = _area_km2(inter, lat_c)
    overlap = round(100.0 * a_int / a_sin, 1) if a_sin > 1e-6 else 0.0

    return {
        "ok": True,
        "overlap_pct": overlap,
        "sinidu_area_km2": round(a_sin, 3),
        "glofas_area_km2": round(a_glo, 3),
        "intersection_km2": round(a_int, 3),
        "fonte": "jrc_glofas_rp100",
        "nota": (
            f"{overlap}% da mancha Sinidu (moderada+total) intersecta o hazard GloFAS RP100. "
            "GloFAS é fluvial/global (sem proteção); Sinidu é pluvial municipal — overlap parcial é esperado."
        ),
    }
