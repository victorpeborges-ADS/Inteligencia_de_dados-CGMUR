"""Vias intransitáveis: cruzamento OSM × mancha de alagamento (overlay pós-simulação)."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests
from shapely.geometry import LineString, mapping, shape
from shapely.ops import unary_union
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import InfraestruturaUrbana, Municipio

logger = logging.getLogger(__name__)

# Alinha com DEPTH_BANDS: moderada começa em 35 cm
DEFAULT_DEPTH_THRESHOLD_M = 0.35
MAX_ROADS = 2500
OVERPASS_TIMEOUT_S = 25
HIGHWAY_FILTER = (
    "primary|secondary|tertiary|residential|unclassified|trunk|living_street|service"
)


def _flood_union_from_features(
    flood_fc: dict[str, Any] | None,
    *,
    min_depth_m: float = DEFAULT_DEPTH_THRESHOLD_M,
):
    if not flood_fc or not flood_fc.get("features"):
        return None
    geoms = []
    for feat in flood_fc["features"]:
        props = feat.get("properties") or {}
        if props.get("layer_type") and props.get("layer_type") != "flood_band":
            continue
        band = props.get("depth_band")
        dmin = props.get("depth_min_m")
        dmax = props.get("depth_max_m")
        ok = False
        if band in ("moderada", "critica"):
            ok = True
        elif dmin is not None and float(dmin) >= min_depth_m:
            ok = True
        elif dmax is not None and float(dmax) >= min_depth_m:
            ok = True
        if not ok:
            continue
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            g = shape(geom)
            if not g.is_empty:
                geoms.append(g)
        except Exception:
            continue
    if not geoms:
        return None
    try:
        return unary_union(geoms)
    except Exception:
        return geoms[0]


def _lines_from_db(db: Session, muni: Municipio) -> list[tuple[Any, str, str]]:
    rows = (
        db.query(
            InfraestruturaUrbana.nome,
            InfraestruturaUrbana.tipo,
            InfraestruturaUrbana.subgrupo,
            func.ST_AsGeoJSON(InfraestruturaUrbana.geom).label("geojson"),
        )
        .filter(
            InfraestruturaUrbana.municipio_id == muni.id,
            InfraestruturaUrbana.tipo.in_(("via", "rodovia", "highway")),
        )
        .limit(MAX_ROADS)
        .all()
    )
    out: list[tuple[Any, str, str]] = []
    for r in rows:
        try:
            g = shape(json.loads(r.geojson))
        except Exception:
            continue
        if g.is_empty:
            continue
        if g.geom_type not in ("LineString", "MultiLineString"):
            continue
        nome = r.nome or "Via"
        sub = r.subgrupo or r.tipo or "via"
        out.append((g, nome, sub))
    return out


def _fetch_osm_roads_bbox(south: float, west: float, north: float, east: float) -> list[tuple[Any, str, str]]:
    """Overpass — malha viária aberta quando o DB não tem vias suficientes."""
    bbox = f"{south},{west},{north},{east}"
    query = f"""
    [out:json][timeout:{OVERPASS_TIMEOUT_S}];
    (
      way["highway"~"{HIGHWAY_FILTER}"]({bbox});
    );
    out body geom;
    """
    headers = {"User-Agent": "SiniduClima/1.0 (impassable-roads; contact=sinidu)"}
    try:
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            headers=headers,
            timeout=OVERPASS_TIMEOUT_S + 5,
        )
        if resp.status_code != 200:
            logger.warning("Overpass vias HTTP %s", resp.status_code)
            return []
        elements = resp.json().get("elements") or []
    except Exception as exc:
        logger.warning("Overpass vias falhou: %s", exc)
        return []

    out: list[tuple[Any, str, str]] = []
    for el in elements:
        if el.get("type") != "way":
            continue
        geom = el.get("geometry") or []
        coords = [(p["lon"], p["lat"]) for p in geom if "lon" in p and "lat" in p]
        if len(coords) < 2:
            continue
        tags = el.get("tags") or {}
        nome = tags.get("name") or tags.get("ref") or "Via OSM"
        sub = tags.get("highway") or "via"
        try:
            out.append((LineString(coords), nome, sub))
        except Exception:
            continue
        if len(out) >= MAX_ROADS:
            break
    return out


def _length_km(geom) -> float:
    """Comprimento aproximado em km (grau→m em lat média)."""
    import math

    try:
        if geom.is_empty:
            return 0.0
        if geom.geom_type == "MultiLineString":
            return sum(_length_km(g) for g in geom.geoms)
        coords = list(geom.coords)
        if len(coords) < 2:
            return 0.0
        lat = sum(c[1] for c in coords) / len(coords)
        m_per_deg_lon = 111_320.0 * max(0.2, abs(math.cos(math.radians(lat))))
        m_per_deg_lat = 111_320.0
        total = 0.0
        for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
            dx = (x1 - x0) * m_per_deg_lon
            dy = (y1 - y0) * m_per_deg_lat
            total += (dx * dx + dy * dy) ** 0.5
        return total / 1000.0
    except Exception:
        return 0.0


def build_impassable_roads_geojson(
    db: Session,
    muni: Municipio,
    flood_fc: dict[str, Any] | None,
    *,
    min_depth_m: float = DEFAULT_DEPTH_THRESHOLD_M,
    allow_overpass: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Retorna (FeatureCollection, meta) com trechos de via sob alagamento ≥ limiar."""
    empty = {"type": "FeatureCollection", "features": []}
    flood = _flood_union_from_features(flood_fc, min_depth_m=min_depth_m)
    if flood is None or flood.is_empty:
        return empty, {
            "ok": False,
            "reason": "sem_mancha_moderada_critica",
            "vias_comprometidas_km": 0.0,
            "trechos": 0,
            "fonte_vias": None,
        }

    roads = _lines_from_db(db, muni)
    fonte = "infraestrutura_db"
    if len(roads) < 8 and allow_overpass:
        try:
            minx, miny, maxx, maxy = shape(
                json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))
            ).bounds
            osm = _fetch_osm_roads_bbox(miny, minx, maxy, maxx)
            if osm:
                roads = osm
                fonte = "osm_overpass"
        except Exception as exc:
            logger.warning("bbox/overpass vias %s: %s", muni.codigo_ibge, exc)

    if not roads:
        return empty, {
            "ok": False,
            "reason": "sem_rede_viaria",
            "vias_comprometidas_km": 0.0,
            "trechos": 0,
            "fonte_vias": None,
        }

    features: list[dict[str, Any]] = []
    total_km = 0.0
    for geom, nome, sub in roads:
        try:
            inter = geom.intersection(flood)
        except Exception:
            continue
        if inter.is_empty:
            continue
        parts = []
        if inter.geom_type == "LineString":
            parts = [inter]
        elif inter.geom_type == "MultiLineString":
            parts = list(inter.geoms)
        elif inter.geom_type == "GeometryCollection":
            parts = [g for g in inter.geoms if g.geom_type in ("LineString", "MultiLineString")]
            flat: list = []
            for g in parts:
                if g.geom_type == "MultiLineString":
                    flat.extend(list(g.geoms))
                else:
                    flat.append(g)
            parts = flat
        else:
            continue
        for part in parts:
            if part.is_empty or part.geom_type != "LineString" or len(part.coords) < 2:
                continue
            km = _length_km(part)
            if km < 0.005:
                continue
            total_km += km
            features.append({
                "type": "Feature",
                "geometry": mapping(part),
                "properties": {
                    "layer_type": "via_intransitavel",
                    "nome": nome,
                    "highway": sub,
                    "length_km": round(km, 3),
                    "depth_threshold_m": min_depth_m,
                    "fonte_vias": fonte,
                    "qualidade_dado": "Derivado Sinidu+Clima",
                    "fonte_referencia": "OSM × mancha pluvial (≥35 cm)",
                },
            })
            if len(features) >= MAX_ROADS:
                break
        if len(features) >= MAX_ROADS:
            break

    meta = {
        "ok": True,
        "vias_comprometidas_km": round(total_km, 2),
        "trechos": len(features),
        "fonte_vias": fonte,
        "depth_threshold_m": min_depth_m,
    }
    return {"type": "FeatureCollection", "features": features}, meta
