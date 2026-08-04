"""Microsoft Global ML Building Footprints → edificações LOD1.

Usado quando OSM tem poucos footprints (ex.: Camutanga). CDLA Permissive 2.0.
"""
from __future__ import annotations

import gzip
import io
import json
import logging
import math
from typing import Any, Iterator

import requests
from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy.orm import Session

from app.models import Municipio

logger = logging.getLogger(__name__)

DATASET_LINKS_URL = (
    "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"
)
LEVEL_HEIGHT_M = 3.0
DEFAULT_HEIGHT_M = 6.0
MAX_BUILDINGS = 8000
HTTP_TIMEOUT_S = 180
HEADERS = {"User-Agent": "SiniduClima/1.0 (digital-twin; research)"}


def _latlon_to_quadkey(lat: float, lon: float, level: int = 9) -> str:
    siny = math.sin(lat * math.pi / 180.0)
    siny = min(max(siny, -0.9999), 0.9999)
    x = (lon + 180.0) / 360.0
    y = 0.5 - math.log((1.0 + siny) / (1.0 - siny)) / (4.0 * math.pi)
    map_size = 256 << level
    px = min(int(x * map_size), map_size - 1)
    py = min(int(y * map_size), map_size - 1)
    tx, ty = px // 256, py // 256
    digits: list[str] = []
    for i in range(level, 0, -1):
        digit = 0
        mask = 1 << (i - 1)
        if tx & mask:
            digit += 1
        if ty & mask:
            digit += 2
        digits.append(str(digit))
    return "".join(digits)


def _quadkeys_for_bbox(
    west: float, south: float, east: float, north: float, *, level: int = 9
) -> list[str]:
    # amostra cantos + centro (municípios pequenos cabem em 1–4 tiles L9)
    samples = [
        (south, west),
        (south, east),
        (north, west),
        (north, east),
        ((south + north) / 2, (west + east) / 2),
    ]
    out: list[str] = []
    seen: set[str] = set()
    for lat, lon in samples:
        qk = _latlon_to_quadkey(lat, lon, level)
        if qk not in seen:
            seen.add(qk)
            out.append(qk)
    return out


def _resolve_tile_urls(quadkeys: list[str], *, location: str = "Brazil") -> list[str]:
    import pandas as pd

    links = pd.read_csv(DATASET_LINKS_URL)
    subset = links[links.Location == location]
    urls: list[str] = []
    for qk in quadkeys:
        rows = subset[subset.QuadKey.astype(str) == str(qk)]
        for url in rows["Url"].tolist():
            if url and url not in urls:
                urls.append(str(url))
    return urls


def _iter_features(url: str) -> Iterator[dict[str, Any]]:
    resp = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT_S)
    resp.raise_for_status()
    raw = gzip.GzipFile(fileobj=io.BytesIO(resp.content))
    for line in raw:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _height_from_props(props: dict[str, Any]) -> tuple[float, str, str, int]:
    for key in ("height", "Height", "height_m", "HF"):
        if props.get(key) is None:
            continue
        try:
            h = float(props[key])
            # MS usa -1 quando altura não estimada
            if h >= 2.0:
                pav = max(1, int(round(h / LEVEL_HEIGHT_M)))
                return round(h, 2), "msft_height", "Estimado", pav
        except (TypeError, ValueError):
            continue
    return (
        DEFAULT_HEIGHT_M,
        "heuristic",
        "Estimado",
        max(1, int(round(DEFAULT_HEIGHT_M / LEVEL_HEIGHT_M))),
    )


def fetch_microsoft_buildings(
    west: float,
    south: float,
    east: float,
    north: float,
    *,
    clip: BaseGeometry | None = None,
    limit: int = MAX_BUILDINGS,
    location: str = "Brazil",
) -> list[dict[str, Any]]:
    """Baixa footprints MS que intersectam o bbox (e opcionalmente o polígono municipal)."""
    qks = _quadkeys_for_bbox(west, south, east, north)
    urls = _resolve_tile_urls(qks, location=location)
    if not urls:
        logger.warning("Microsoft buildings: nenhum tile para quadkeys %s", qks)
        return []

    bbox_geom = box(west, south, east, north)
    records: list[dict[str, Any]] = []
    for url in urls:
        logger.info("Microsoft buildings: baixando %s", url.split("/")[-1][:80])
        try:
            features = _iter_features(url)
        except Exception as exc:
            logger.warning("Microsoft buildings download falhou (%s): %s", url, exc)
            continue
        for feat in features:
            geom_j = feat.get("geometry")
            if not geom_j:
                continue
            try:
                g = shape(geom_j)
            except Exception:
                continue
            if g.is_empty or not g.intersects(bbox_geom):
                continue
            if clip is not None and not g.intersects(clip):
                continue
            if clip is not None:
                try:
                    g = g.intersection(clip)
                except Exception:
                    pass
            if g.is_empty or g.geom_type not in {"Polygon", "MultiPolygon"}:
                continue
            props = feat.get("properties") or {}
            if not isinstance(props, dict):
                props = {}
            altura, fonte_h, qualidade, pav = _height_from_props(props)
            c = g.centroid
            stable_id = f"msft/{round(c.x, 6)}_{round(c.y, 6)}"
            records.append(
                {
                    "osm_id": stable_id[:40],
                    "nome": None,
                    "uso": "yes",
                    "pavimentos": pav,
                    "altura_m": altura,
                    "fonte_altura": fonte_h,
                    "qualidade": qualidade,
                    "fonte_footprint": "microsoft",
                    "geom": g,
                }
            )
            if len(records) >= limit:
                return records
    return records


def collect_microsoft_buildings_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
    limit: int = MAX_BUILDINGS,
) -> dict[str, Any]:
    """Ingere footprints Microsoft e grava em edificacoes (substitui existentes)."""
    from app.data_connectors.building_footprints_collector import (
        _muni_bbox,
        upsert_edificacoes,
    )
    from app.models import Edificacao
    from geoalchemy2.shape import to_shape

    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    existing = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    if existing > 50 and not force:
        return {
            "codigo_ibge": code,
            "status": "cached",
            "count": existing,
            "fonte": "banco_local",
        }

    south, west, north, east = _muni_bbox(db, muni)
    clip = None
    if muni.geom is not None:
        try:
            clip = to_shape(muni.geom)
        except Exception:
            clip = None

    records = fetch_microsoft_buildings(
        west, south, east, north, clip=clip, limit=limit
    )
    for rec in records:
        rec["codigo_ibge"] = code
    count = upsert_edificacoes(db, muni, records) if records else 0
    return {
        "codigo_ibge": code,
        "status": "ok" if count else "vazio",
        "count": count,
        "fonte": "microsoft",
        "bbox": [west, south, east, north],
    }
