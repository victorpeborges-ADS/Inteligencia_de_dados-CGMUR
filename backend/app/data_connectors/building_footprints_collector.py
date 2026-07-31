"""Ingestão de footprints de edificações (17a.1) + estimativa de altura LOD1 (17a.2).

Fonte primária: OpenStreetMap via Overpass (`building=*`).
Altura: OSM height → building:levels → heurística por uso.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import requests
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, Polygon, box, shape
from sqlalchemy.orm import Session

from app.models import Edificacao, Municipio

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
LEVEL_HEIGHT_M = 3.0
DEFAULT_HEIGHT_M = 6.0
MAX_BUILDINGS = 3500
OVERPASS_TIMEOUT_S = 90
OVERPASS_MAX_RETRIES = 4
OVERPASS_BACKOFF_BASE_S = 8.0


class OverpassRateLimitError(RuntimeError):
    """Overpass recusou / sobrecarregado (429/504/timeout)."""


# Heurística por uso OSM quando não há height/levels
USO_HEIGHT_M = {
    "apartments": 18.0,
    "residential": 9.0,
    "house": 6.0,
    "detached": 6.0,
    "commercial": 12.0,
    "retail": 9.0,
    "office": 24.0,
    "industrial": 10.0,
    "warehouse": 8.0,
    "school": 9.0,
    "hospital": 15.0,
    "church": 12.0,
    "cathedral": 20.0,
    "yes": DEFAULT_HEIGHT_M,
}


def parse_height_meters(raw: str | None) -> float | None:
    if not raw:
        return None
    text = str(raw).strip().lower().replace(",", ".")
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*(m|meter|meters|metro|metros)?$", text)
    if m:
        val = float(m.group(1))
        return val if 1.5 <= val <= 400 else None
    # "12'" feet — raro no BR
    m2 = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*'$", text)
    if m2:
        return float(m2.group(1)) * 0.3048
    return None


def estimate_height(tags: dict[str, Any]) -> tuple[float, str, str, int | None]:
    """Retorna (altura_m, fonte_altura, qualidade, pavimentos)."""
    height = parse_height_meters(tags.get("height") or tags.get("building:height"))
    if height is not None:
        levels = None
        try:
            if tags.get("building:levels"):
                levels = max(1, int(float(str(tags["building:levels"]).replace(",", "."))))
        except (TypeError, ValueError):
            pass
        return round(height, 2), "osm_height", "Observado", levels

    levels_raw = tags.get("building:levels") or tags.get("levels")
    if levels_raw is not None:
        try:
            levels = max(1, int(float(str(levels_raw).replace(",", "."))))
            return round(levels * LEVEL_HEIGHT_M, 2), "osm_levels", "Estimado", levels
        except (TypeError, ValueError):
            pass

    building = str(tags.get("building") or "yes").lower()
    h = USO_HEIGHT_M.get(building, DEFAULT_HEIGHT_M)
    pav = max(1, int(round(h / LEVEL_HEIGHT_M)))
    return float(h), "heuristic", "Derivado", pav


def _muni_bbox(db: Session, muni: Municipio) -> tuple[float, float, float, float]:
    """south, west, north, east (Overpass order)."""
    if muni.geom is None:
        # Recife fallback
        return (-8.16, -35.03, -7.92, -34.85)
    geojson = db.scalar(muni.geom.ST_AsGeoJSON())
    g = shape(json.loads(geojson))
    minx, miny, maxx, maxy = g.bounds
    # Overpass: south,west,north,east
    return (miny, minx, maxy, maxx)


def _element_polygon(el: dict[str, Any]) -> Polygon | MultiPolygon | None:
    geom_pts = el.get("geometry")
    if not geom_pts or len(geom_pts) < 3:
        return None
    coords = [(float(p["lon"]), float(p["lat"])) for p in geom_pts if "lon" in p and "lat" in p]
    if len(coords) < 3:
        return None
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    try:
        poly = Polygon(coords)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            return None
        if isinstance(poly, MultiPolygon):
            return poly
        return poly
    except Exception:
        return None


def _as_multipolygon(g: Polygon | MultiPolygon) -> MultiPolygon:
    if isinstance(g, MultiPolygon):
        return g
    return MultiPolygon([g])


def fetch_osm_buildings(
    south: float,
    west: float,
    north: float,
    east: float,
    *,
    limit: int = MAX_BUILDINGS,
    retries: int = OVERPASS_MAX_RETRIES,
) -> list[dict[str, Any]]:
    """Consulta Overpass — prioriza edifícios com height/levels.

    Em 429/504/timeout aplica backoff exponencial (18c.2).
    """
    import time

    # Clip bbox se enorme (protege Overpass)
    if (north - south) * (east - west) > 0.08:
        cy = (south + north) / 2
        cx = (west + east) / 2
        half = 0.06
        south, north = cy - half / 2, cy + half / 2
        west, east = cx - half / 2, cx + half / 2

    query = f"""
    [out:json][timeout:{OVERPASS_TIMEOUT_S}];
    (
      way["building"]["height"]({south},{west},{north},{east});
      way["building"]["building:levels"]({south},{west},{north},{east});
      way["building"]({south},{west},{north},{east});
    );
    out body geom {limit};
    """
    last_exc: Exception | None = None
    attempts = max(1, retries)
    for attempt in range(attempts):
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=OVERPASS_TIMEOUT_S + 15,
            )
            if resp.status_code in (429, 502, 503, 504):
                raise OverpassRateLimitError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            elements = resp.json().get("elements") or []
            return [e for e in elements if e.get("type") == "way"]
        except (OverpassRateLimitError, requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            wait = OVERPASS_BACKOFF_BASE_S * (2**attempt)
            logger.warning(
                "Overpass tentativa %s/%s falhou (%s); aguardando %.0fs",
                attempt + 1,
                attempts,
                exc,
                wait,
            )
            if attempt + 1 < attempts:
                time.sleep(wait)
        except Exception as exc:
            logger.warning("Overpass buildings falhou: %s", exc)
            return []

    raise OverpassRateLimitError(f"Overpass indisponível após {attempts} tentativas: {last_exc}")


def _seed_recife_centro() -> list[dict[str, Any]]:
    """Footprints sintéticos no centro do Recife — fallback offline."""
    # Grade ~6×6 blocos perto do Marco Zero / Boa Vista
    base_lng, base_lat = -34.8715, -8.0635
    out: list[dict[str, Any]] = []
    idx = 0
    for row in range(6):
        for col in range(6):
            idx += 1
            w = 0.00028
            h = 0.00022
            ox = col * 0.00055
            oy = row * 0.00045
            poly = box(base_lng + ox, base_lat + oy, base_lng + ox + w, base_lat + oy + h)
            levels = 2 + ((row + col) % 8)
            out.append({
                "osm_id": f"seed-recife-{idx}",
                "nome": f"Edifício piloto {idx}",
                "uso": "apartments" if levels >= 5 else "residential",
                "pavimentos": levels,
                "altura_m": levels * LEVEL_HEIGHT_M,
                "fonte_altura": "heuristic",
                "qualidade": "Derivado",
                "fonte_footprint": "seed",
                "geom": poly,
            })
    return out


def elements_to_records(elements: list[dict[str, Any]], codigo_ibge: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for el in elements:
        poly = _element_polygon(el)
        if poly is None:
            continue
        osm_id = f"way/{el.get('id')}"
        if osm_id in seen:
            continue
        seen.add(osm_id)
        tags = el.get("tags") or {}
        altura, fonte_h, qualidade, pav = estimate_height(tags)
        uso = str(tags.get("building") or "yes")
        nome = tags.get("name") or tags.get("addr:housename")
        records.append({
            "osm_id": osm_id,
            "nome": nome,
            "uso": uso[:80],
            "pavimentos": pav,
            "altura_m": altura,
            "fonte_altura": fonte_h,
            "qualidade": qualidade,
            "fonte_footprint": "osm",
            "geom": poly,
            "codigo_ibge": codigo_ibge,
        })
        if len(records) >= MAX_BUILDINGS:
            break
    return records


def upsert_edificacoes(
    db: Session,
    muni: Municipio,
    records: list[dict[str, Any]],
) -> int:
    db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).delete(synchronize_session=False)
    now = datetime.now(timezone.utc)
    for rec in records:
        g = _as_multipolygon(rec["geom"])
        row = Edificacao(
            municipio_id=muni.id,
            codigo_ibge=muni.codigo_ibge,
            osm_id=rec.get("osm_id"),
            nome=rec.get("nome"),
            uso=rec.get("uso"),
            pavimentos=rec.get("pavimentos"),
            altura_m=rec["altura_m"],
            fonte_altura=rec["fonte_altura"],
            qualidade=rec["qualidade"],
            fonte_footprint=rec.get("fonte_footprint") or "osm",
            geom=from_shape(g, srid=4326),
            atualizado_em=now,
        )
        db.add(row)
    db.commit()
    return len(records)


def collect_buildings_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
    limit: int = MAX_BUILDINGS,
) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    existing = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    if existing > 0 and not force:
        return {
            "codigo_ibge": code,
            "status": "cached",
            "count": existing,
            "fonte": "banco_local",
        }

    south, west, north, east = _muni_bbox(db, muni)
    try:
        elements = fetch_osm_buildings(south, west, north, east, limit=limit)
    except OverpassRateLimitError as exc:
        return {
            "codigo_ibge": code,
            "status": "rate_limited",
            "count": existing,
            "fonte": "overpass",
            "error": str(exc),
            "retryable": True,
        }
    records = elements_to_records(elements, code)

    fonte = "osm"
    if not records and code == "2611606":
        seed = _seed_recife_centro()
        records = [{**r, "codigo_ibge": code} for r in seed]
        fonte = "seed"

    count = upsert_edificacoes(db, muni, records)

    # 17a.6 — refinar altura com nDSM quando houver DSM/LiDAR local (piloto Recife)
    ndsm_info = None
    try:
        from app.services.dem_processor import dem_dir, find_local_dem
        from app.services.ndsm_service import refine_building_heights_from_ndsm

        has_dsm = bool(find_local_dem(code)) or (dem_dir(code) / "dem.tif").exists()
        if has_dsm:
            ndsm_info = refine_building_heights_from_ndsm(db, code)
    except Exception as exc:
        logger.warning("nDSM refine falhou para %s: %s", code, exc)
        ndsm_info = {"status": "erro", "erro": str(exc)}

    return {
        "codigo_ibge": code,
        "status": "ok" if count else "vazio",
        "count": count,
        "fonte": fonte,
        "bbox": [west, south, east, north],
        "ndsm": ndsm_info,
    }


def buildings_geojson(
    db: Session,
    codigo_ibge: str,
    *,
    ensure: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    count = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    if count == 0 and ensure:
        collect_buildings_municipality(db, code, force=False)

    q = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id)
    if limit:
        q = q.limit(limit)
    rows = q.all()

    features = []
    for row in rows:
        try:
            geo = json.loads(db.scalar(row.geom.ST_AsGeoJSON()))
        except Exception:
            continue
        altura = float(row.altura_m or DEFAULT_HEIGHT_M)
        from app.services.building_quality_service import enrich_feature_properties

        props = enrich_feature_properties({
            "id": row.id,
            "osm_id": row.osm_id,
            "nome": row.nome,
            "uso": row.uso,
            "pavimentos": row.pavimentos,
            "altura_m": altura,
            "fonte_altura": row.fonte_altura,
            "qualidade": row.qualidade,
            "fonte_footprint": row.fonte_footprint,
            "_extrusionHeightM": altura,
            "fonte_referencia": "OpenStreetMap / Sinidu+Clima LOD1",
            "qualidade_dado": row.qualidade,
        })
        features.append({
            "type": "Feature",
            "geometry": geo,
            "properties": props,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "codigo_ibge": code,
            "count": len(features),
            "model": "LOD1",
            "versao": "17a",
        },
    }
