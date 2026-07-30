"""Cobertura do solo Recife a partir de geometrias OSM (água, parques, mata).

Substitui a partição Voronoi sintética que gerava manchas de 'água'
parecidas com inundação. Área urbana / habitável = limite municipal
− água − vegetação OSM − Unidades de Conservação oficiais (Pref. Recife).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

logger = logging.getLogger(__name__)

RECIFE_IBGE = "2611606"
GEOJSON_PATH = Path(__file__).resolve().parents[2] / "data" / "cobertura_recife_osm.geojson"
# Dados abertos Pref. Recife — UCN/APA (Lei 18.014/2014 / SMUP)
UCN_GEOJSON_PATH = Path(__file__).resolve().parents[2] / "data" / "recife_ucn.geojson"

VEGETATION_CLASS = "Vegetação / Floresta"
WATER_CLASS = "Corpo d'água"
URBAN_CLASS = "Área Urbana"

_ucn_cache: Any | None = None
_ucn_loaded = False


def _load_osm_class_geoms() -> dict[str, Any]:
    if not GEOJSON_PATH.exists():
        logger.warning("GeoJSON cobertura OSM ausente: %s", GEOJSON_PATH)
        return {}
    try:
        raw = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Falha ao ler cobertura OSM: %s", exc)
        return {}
    out: dict[str, Any] = {}
    for feat in raw.get("features") or []:
        props = feat.get("properties") or {}
        classe = props.get("classe_uso")
        geom = feat.get("geometry")
        if not classe or not geom:
            continue
        try:
            g = shape(geom)
            if not g.is_valid:
                g = make_valid(g)
        except Exception:
            continue
        if g.is_empty:
            continue
        out[classe] = g
    return out


def load_recife_ucn_geom():
    """Polígonos oficiais de UCN/APA do Recife (dados.recife.pe.gov.br)."""
    global _ucn_cache, _ucn_loaded
    if _ucn_loaded:
        return _ucn_cache
    _ucn_loaded = True
    if not UCN_GEOJSON_PATH.exists():
        logger.warning("GeoJSON UCN Recife ausente: %s", UCN_GEOJSON_PATH)
        _ucn_cache = None
        return None
    try:
        raw = json.loads(UCN_GEOJSON_PATH.read_text(encoding="utf-8"))
        parts = []
        for feat in raw.get("features") or []:
            geom = feat.get("geometry")
            if not geom:
                continue
            g = shape(geom)
            if not g.is_valid:
                g = make_valid(g)
            if not g.is_empty:
                parts.append(g)
        if not parts:
            _ucn_cache = None
            return None
        u = make_valid(unary_union(parts))
        # simplifica ~80–100 m para clip rápido no request HTTP
        u = make_valid(u.simplify(0.0009, preserve_topology=True))
        _ucn_cache = u if not u.is_empty else None
        return _ucn_cache
    except Exception as exc:
        logger.warning("Falha ao carregar UCN Recife: %s", exc)
        _ucn_cache = None
        return None


def extract_polygons(geom):
    """Extrai apenas Polygon/MultiPolygon (evita GeometryCollection na serialização)."""
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom if not geom.is_empty else None
    if isinstance(geom, GeometryCollection):
        parts = [
            p for p in geom.geoms
            if isinstance(p, (Polygon, MultiPolygon)) and not p.is_empty
        ]
        if not parts:
            return None
        u = unary_union(parts)
        if u.is_empty:
            return None
        if not u.is_valid:
            u = make_valid(u)
        return extract_polygons(u)
    return None


def get_recife_habitable_mask(muni_poly):
    """Área habitável Recife = município − UCN oficial − vegetação OSM − água.

    Usada na camada socioeconômica para não pintar renda em reservas/mata.
    """
    if muni_poly is None or muni_poly.is_empty:
        return None
    poly = make_valid(muni_poly) if not muni_poly.is_valid else muni_poly

    clips = []
    ucn = load_recife_ucn_geom()
    if ucn is not None and not ucn.is_empty:
        try:
            clips.append(make_valid(ucn.intersection(poly)))
        except Exception:
            clips.append(ucn)

    osm = _load_osm_class_geoms()
    for classe in (VEGETATION_CLASS, WATER_CLASS):
        src = osm.get(classe)
        if src is None or src.is_empty:
            continue
        try:
            clips.append(make_valid(src.intersection(poly)))
        except Exception:
            continue

    clips = [c for c in clips if c is not None and not c.is_empty]
    if not clips:
        return extract_polygons(poly)

    nonhab = make_valid(unary_union(clips))
    try:
        hab = make_valid(poly.difference(nonhab))
    except Exception:
        return extract_polygons(poly)
    return extract_polygons(hab)


def get_urban_mask_wkt(db, municipio_id: int) -> str | None:
    """Retorna WKT da máscara habitável/urbana para clip socioeconômico."""
    from sqlalchemy import text
    from app.models import CoberturaVegetalMapBiomas, Municipio

    muni = db.query(Municipio).filter(Municipio.id == municipio_id).first()
    if muni and muni.codigo_ibge == RECIFE_IBGE and muni.geom is not None:
        try:
            import json as _json

            poly = shape(_json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
            hab = get_recife_habitable_mask(poly)
            if hab is not None and not hab.is_empty:
                return hab.wkt
        except Exception as exc:
            logger.warning("Máscara habitável Recife indisponível: %s", exc)

    row = (
        db.query(CoberturaVegetalMapBiomas.id)
        .filter(
            CoberturaVegetalMapBiomas.municipio_id == municipio_id,
            CoberturaVegetalMapBiomas.classe_uso == URBAN_CLASS,
        )
        .first()
    )
    if not row:
        try:
            import json as _json

            if not muni or muni.geom is None:
                return None
            poly = shape(_json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
            parts = build_recife_osm_landcover(poly)
            urban = (parts or {}).get(URBAN_CLASS)
            if urban is None or urban.is_empty:
                return None
            return urban.wkt
        except Exception as exc:
            logger.warning("Máscara urbana OSM indisponível: %s", exc)
            return None

    wkt = db.execute(
        text(
            """
            SELECT ST_AsText(
              ST_MakeValid(
                ST_SimplifyPreserveTopology(ST_SnapToGrid(geom, 0.0005), 0.001)
              )
            )
            FROM cobertura_vegetal_mapbiomas
            WHERE id = :cid
            """
        ),
        {"cid": row.id},
    ).scalar()
    return wkt if wkt else None


def build_recife_osm_landcover(poly) -> dict[str, Any] | None:
    """Partição espacial realista para Recife a partir de OSM + UCN oficial.

    Retorna dict classe → geometria, ou None se OSM indisponível.
    Área urbana é sempre derivada: município − água − vegetação (− UCN).
    """
    if poly is None or poly.is_empty:
        return None

    osm = _load_osm_class_geoms()
    if not osm:
        return None

    poly = make_valid(poly) if not poly.is_valid else poly
    parts: dict[str, Any] = {}

    for classe in (WATER_CLASS, VEGETATION_CLASS):
        src = osm.get(classe)
        if src is None or src.is_empty:
            continue
        try:
            clipped = poly.intersection(src)
        except Exception:
            continue
        if clipped.is_empty:
            continue
        if not clipped.is_valid:
            clipped = make_valid(clipped)
        if clipped.is_empty or clipped.area <= 0:
            continue
        parts[classe] = clipped

    # Incorpora UCN oficial à vegetação/reserva (ex.: UCN Beberibe / Guabiraba)
    ucn = load_recife_ucn_geom()
    if ucn is not None and not ucn.is_empty:
        try:
            ucn_clip = make_valid(ucn.intersection(poly))
        except Exception:
            ucn_clip = None
        if ucn_clip is not None and not ucn_clip.is_empty:
            if VEGETATION_CLASS in parts:
                parts[VEGETATION_CLASS] = make_valid(
                    unary_union([parts[VEGETATION_CLASS], ucn_clip])
                )
            else:
                parts[VEGETATION_CLASS] = ucn_clip

    clips = [parts[c] for c in (WATER_CLASS, VEGETATION_CLASS) if c in parts]
    if clips:
        urban = make_valid(poly.difference(unary_union(clips)))
        if not urban.is_empty and urban.area > 0:
            parts[URBAN_CLASS] = urban
        else:
            parts[URBAN_CLASS] = poly
    else:
        parts[URBAN_CLASS] = poly

    if len(parts) < 2:
        logger.warning("Cobertura OSM Recife incompleta (%s classes)", list(parts))
        return None

    logger.info(
        "Cobertura OSM Recife: %s",
        {k: round(float(v.area), 6) for k, v in parts.items()},
    )
    return parts
