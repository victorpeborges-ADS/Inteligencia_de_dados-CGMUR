"""Hidrografia OSM (waterway) para reforço de canais no motor pluvial."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import requests
from shapely.geometry import LineString, mapping, shape
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

OVERPASS_TIMEOUT_S = 28
MAX_WAYS = 800
CACHE_NAME = "osm_waterways.geojson"
WATERWAY_FILTER = "river|stream|canal|drain|ditch|tidal_channel"


def _cache_path(codigo_ibge: str) -> Path:
    from app.services.dem_processor import dem_dir

    return dem_dir(str(codigo_ibge).zfill(7)[:7]) / CACHE_NAME


_OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)


def _fetch_overpass(south: float, west: float, north: float, east: float) -> list[dict[str, Any]]:
    bbox = f"{south},{west},{north},{east}"
    query = f"""
    [out:json][timeout:{OVERPASS_TIMEOUT_S}];
    (
      way["waterway"~"{WATERWAY_FILTER}"]({bbox});
      relation["waterway"~"river|canal"]({bbox});
    );
    out body geom;
    """
    headers = {"User-Agent": "SiniduClima/1.0 (osm-hydrography; contact=sinidu)"}
    for url in _OVERPASS_ENDPOINTS:
        try:
            resp = requests.post(
                url,
                data={"data": query},
                headers=headers,
                timeout=OVERPASS_TIMEOUT_S + 8,
            )
            if resp.status_code != 200:
                logger.warning("Overpass hidrografia HTTP %s (%s)", resp.status_code, url)
                continue
            elements = resp.json().get("elements") or []
            if elements:
                return elements
        except Exception as exc:
            logger.warning("Overpass hidrografia falhou (%s): %s", url, exc)
    return []


def _elements_to_shapes(elements: list[dict[str, Any]]) -> list:
    out = []
    for el in elements:
        if el.get("type") != "way":
            continue
        geom = el.get("geometry") or []
        coords = [(p["lon"], p["lat"]) for p in geom if "lon" in p and "lat" in p]
        if len(coords) < 2:
            continue
        try:
            line = LineString(coords)
            if not line.is_empty:
                out.append(line)
        except Exception:
            continue
        if len(out) >= MAX_WAYS:
            break
    return out


def load_osm_waterway_shapes(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
) -> tuple[list, dict[str, Any]]:
    """Lista de geometrias Shapely (LineString) + meta; cache GeoJSON no DEM dir."""
    from app.models import Municipio

    code = str(codigo_ibge).zfill(7)[:7]
    meta: dict[str, Any] = {"ok": False, "fonte": None, "n_ways": 0}
    cache = _cache_path(code)

    if not force and cache.exists():
        try:
            fc = json.loads(cache.read_text(encoding="utf-8"))
            shapes = []
            for feat in fc.get("features") or []:
                g = feat.get("geometry")
                if not g:
                    continue
                try:
                    s = shape(g)
                    if not s.is_empty:
                        shapes.append(s)
                except Exception:
                    continue
            if shapes:
                meta.update({"ok": True, "fonte": "cache", "n_ways": len(shapes)})
                return shapes, meta
        except Exception as exc:
            logger.info("cache hidrografia inválido %s: %s", code, exc)

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni or muni.geom is None:
        return [], meta

    try:
        bounds = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))).bounds
        west, south, east, north = bounds
    except Exception as exc:
        logger.warning("bbox hidrografia %s: %s", code, exc)
        return [], meta

    elements = _fetch_overpass(south, west, north, east)
    shapes = _elements_to_shapes(elements)
    if not shapes:
        meta["reason"] = "sem_waterways_osm"
        return [], meta

    # Clip leve ao município (buffer) para não puxar fora
    try:
        muni_g = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))).buffer(0.002)
        clipped = []
        for s in shapes:
            try:
                inter = s.intersection(muni_g)
                if inter.is_empty:
                    continue
                if inter.geom_type == "LineString":
                    clipped.append(inter)
                elif inter.geom_type == "MultiLineString":
                    clipped.extend(list(inter.geoms))
            except Exception:
                continue
        shapes = clipped or shapes
    except Exception:
        pass

    features = []
    for s in shapes:
        if s.geom_type != "LineString" or len(s.coords) < 2:
            continue
        features.append({
            "type": "Feature",
            "geometry": mapping(s),
            "properties": {
                "layer_type": "osm_waterway",
                "fonte": "osm_overpass",
                "fonte_referencia": "OpenStreetMap waterway",
                "qualidade_dado": "Referencia",
            },
        })
    fc = {"type": "FeatureCollection", "features": features}
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(fc), encoding="utf-8")
    except Exception as exc:
        logger.info("cache hidrografia write %s: %s", code, exc)

    meta.update({"ok": True, "fonte": "osm_overpass", "n_ways": len(shapes)})
    return shapes, meta


def build_osm_hydrography_geojson(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """GeoJSON de hidrografia OSM para o LayerPanel."""
    shapes, meta = load_osm_waterway_shapes(db, codigo_ibge, force=force)
    features = []
    for s in shapes:
        if s.geom_type == "LineString" and len(s.coords) >= 2:
            features.append({
                "type": "Feature",
                "geometry": mapping(s),
                "properties": {
                    "layer_type": "osm_waterway",
                    "fonte_referencia": "OpenStreetMap waterway (rio/córrego/canal)",
                    "qualidade_dado": "Referencia",
                },
            })
        elif s.geom_type == "MultiLineString":
            for part in s.geoms:
                if len(part.coords) < 2:
                    continue
                features.append({
                    "type": "Feature",
                    "geometry": mapping(part),
                    "properties": {
                        "layer_type": "osm_waterway",
                        "fonte_referencia": "OpenStreetMap waterway (rio/córrego/canal)",
                        "qualidade_dado": "Referencia",
                    },
                })
    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {"codigo_ibge": str(codigo_ibge).zfill(7)[:7], **meta},
    }


def merge_river_shapes(existing: list, osm_shapes: list) -> list:
    """Une MapBiomas/água + OSM sem duplicar geometria vazia."""
    out = [g for g in (existing or []) if g is not None and not getattr(g, "is_empty", True)]
    for g in osm_shapes or []:
        if g is None or getattr(g, "is_empty", True):
            continue
        out.append(g)
    return out
