"""API de tiles do gêmeo digital (17c.4) — MVT + 3D Tiles com cache Redis."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data_connectors.cache import cache_delete_prefix, cache_get_bytes, cache_get_json, cache_set_bytes, cache_set_json
from app.models import Edificacao, Municipio
from app.services.building_3dtiles_service import build_3dtiles_for_municipality, status_3dtiles, tiles3d_muni_dir

logger = logging.getLogger(__name__)

TILE_CACHE_TTL = 3600  # 1h
GEOJSON_CACHE_TTL = 1800
TILESET_CACHE_TTL = 3600
MVT_LAYER = "edificacoes"


def _code(codigo_ibge: str) -> str:
    return str(codigo_ibge).zfill(7)[:7]


def mvt_cache_key(codigo_ibge: str, z: int, x: int, y: int) -> str:
    return f"gemeo:mvt:{_code(codigo_ibge)}:{z}:{x}:{y}"


def geojson_cache_key(codigo_ibge: str, limit: int | None) -> str:
    return f"gemeo:geojson:{_code(codigo_ibge)}:lim{limit or 0}"


def tileset_cache_key(codigo_ibge: str) -> str:
    return f"gemeo:3dtiles:tileset:{_code(codigo_ibge)}"


def glb_cache_key(codigo_ibge: str) -> str:
    return f"gemeo:3dtiles:glb:{_code(codigo_ibge)}"


def invalidate_gemeo_tile_cache(codigo_ibge: str) -> int:
    code = _code(codigo_ibge)
    return (
        cache_delete_prefix(f"gemeo:mvt:{code}")
        + cache_delete_prefix(f"gemeo:geojson:{code}")
        + cache_delete_prefix(f"gemeo:3dtiles:tileset:{code}")
        + cache_delete_prefix(f"gemeo:3dtiles:glb:{code}")
    )


def build_mvt_tile(
    db: Session,
    codigo_ibge: str,
    z: int,
    x: int,
    y: int,
    *,
    use_cache: bool = True,
) -> bytes:
    """Gera tile MVT (PostGIS ST_AsMVT) das edificações do município."""
    code = _code(codigo_ibge)
    if z < 10 or z > 18:
        return b""
    if x < 0 or y < 0:
        return b""

    key = mvt_cache_key(code, z, x, y)
    if use_cache:
        cached = cache_get_bytes(key)
        if cached is not None:
            return cached

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    # ST_AsMVTGeom + atributos de selo derivados no SQL via CASE
    sql = text(
        """
        WITH bounds AS (
          SELECT ST_TileEnvelope(:z, :x, :y) AS geom
        ),
        mvtgeom AS (
          SELECT
            e.id,
            e.osm_id,
            e.nome,
            e.uso,
            CASE
              WHEN lower(coalesce(e.uso, '')) IN (
                'apartments', 'residential', 'house', 'detached',
                'semidetached_house', 'terrace', 'dormitory', 'yes', 'building'
              ) THEN 'residencial'
              WHEN lower(coalesce(e.uso, '')) IN (
                'commercial', 'retail', 'shop', 'supermarket', 'mall', 'kiosk'
              ) THEN 'comercial'
              WHEN lower(coalesce(e.uso, '')) IN (
                'industrial', 'warehouse', 'manufacture', 'factory'
              ) THEN 'industrial'
              WHEN lower(coalesce(e.uso, '')) IN (
                'office', 'government', 'civic', 'public'
              ) THEN 'escritorio'
              WHEN lower(coalesce(e.uso, '')) IN (
                'school', 'university', 'college', 'kindergarten', 'college'
              ) THEN 'educacao'
              WHEN lower(coalesce(e.uso, '')) IN (
                'hospital', 'clinic', 'doctors', 'dentist'
              ) THEN 'saude'
              WHEN lower(coalesce(e.uso, '')) IN ('hotel', 'hostel', 'guest_house') THEN 'hospedagem'
              WHEN lower(coalesce(e.uso, '')) IN (
                'church', 'cathedral', 'chapel', 'mosque', 'temple', 'synagogue', 'religious'
              ) THEN 'religioso'
              ELSE 'outro'
            END AS uso_grupo,
            e.pavimentos,
            e.altura_m::float AS altura_m,
            e.fonte_altura,
            CASE
              WHEN lower(coalesce(e.fonte_altura, '')) IN ('ndsm_lidar', 'lidar', 'ndsm') THEN 'LiDAR'
              WHEN lower(coalesce(e.fonte_altura, '')) LIKE 'osm%'
                OR lower(coalesce(e.fonte_altura, '')) IN ('height', 'building:levels') THEN 'OSM'
              ELSE 'Estimado'
            END AS selo_3d,
            CASE
              WHEN lower(coalesce(e.fonte_altura, '')) IN ('ndsm_lidar', 'lidar', 'ndsm', 'osm_height') THEN 'Observado'
              WHEN lower(coalesce(e.fonte_altura, '')) LIKE 'osm%' THEN 'Estimado'
              ELSE 'Derivado'
            END AS qualidade,
            ST_AsMVTGeom(
              ST_Transform(e.geom, 3857),
              bounds.geom,
              4096,
              64,
              true
            ) AS geom
          FROM edificacoes e
          CROSS JOIN bounds
          WHERE e.municipio_id = :muni_id
            AND e.geom IS NOT NULL
            AND ST_Intersects(ST_Transform(e.geom, 3857), bounds.geom)
        )
        SELECT ST_AsMVT(mvtgeom.*, :layer, 4096, 'geom') AS tile
        FROM mvtgeom
        """
    )
    try:
        row = db.execute(
            sql,
            {"z": z, "x": x, "y": y, "muni_id": muni.id, "layer": MVT_LAYER},
        ).first()
    except Exception as exc:
        logger.warning("ST_AsMVT falhou para %s/%s/%s/%s: %s", code, z, x, y, exc)
        raise

    tile = bytes(row[0]) if row and row[0] is not None else b""
    if use_cache and tile:
        cache_set_bytes(key, tile, ttl=TILE_CACHE_TTL)
    return tile


def get_cached_buildings_geojson(
    db: Session,
    codigo_ibge: str,
    *,
    limit: int | None = None,
    ensure: bool = True,
    use_cache: bool = True,
) -> dict[str, Any]:
    from app.data_connectors.building_footprints_collector import buildings_geojson

    code = _code(codigo_ibge)
    key = geojson_cache_key(code, limit)
    if use_cache:
        cached = cache_get_json(key)
        if isinstance(cached, dict) and cached.get("type") == "FeatureCollection":
            cached = dict(cached)
            cached["_cache"] = "hit"
            return cached

    data = buildings_geojson(db, code, ensure=ensure, limit=limit)
    if use_cache:
        cache_set_json(key, data, ttl=GEOJSON_CACHE_TTL)
    out = dict(data)
    out["_cache"] = "miss"
    return out


def get_cached_tileset_json(
    db: Session,
    codigo_ibge: str,
    *,
    ensure_build: bool = True,
    use_cache: bool = True,
) -> dict[str, Any]:
    code = _code(codigo_ibge)
    key = tileset_cache_key(code)
    if use_cache:
        cached = cache_get_json(key)
        if isinstance(cached, dict) and "root" in cached:
            out = dict(cached)
            out["_cache"] = "hit"
            return out

    path = tiles3d_muni_dir(code) / "tileset.json"
    if not path.exists() and ensure_build:
        build_3dtiles_for_municipality(db, code, force=False)
    if not path.exists():
        raise FileNotFoundError("tileset.json não encontrado")

    doc = json.loads(path.read_text(encoding="utf-8"))
    # Reescreve content URI relativa para API cacheável
    try:
        root = doc.get("root") or {}
        content = root.get("content") or {}
        if content.get("uri") in {"content.glb", "./content.glb"}:
            content["uri"] = f"content.glb"
            root["content"] = content
            doc["root"] = root
    except Exception:
        pass

    if use_cache:
        cache_set_json(key, doc, ttl=TILESET_CACHE_TTL)
    out = dict(doc)
    out["_cache"] = "miss"
    return out


def get_cached_glb(
    db: Session,
    codigo_ibge: str,
    *,
    ensure_build: bool = True,
    use_cache: bool = True,
) -> tuple[bytes, Path]:
    code = _code(codigo_ibge)
    key = glb_cache_key(code)
    path = tiles3d_muni_dir(code) / "content.glb"

    if use_cache:
        cached = cache_get_bytes(key)
        if cached is not None:
            return cached, path

    if (not path.exists()) and ensure_build:
        build_3dtiles_for_municipality(db, code, force=False)
    if not path.exists():
        raise FileNotFoundError("content.glb não encontrado")

    data = path.read_bytes()
    if use_cache and data:
        cache_set_bytes(key, data, ttl=TILESET_CACHE_TTL)
    return data, path


def tile_api_status(db: Session, codigo_ibge: str) -> dict[str, Any]:
    code = _code(codigo_ibge)
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    count = 0
    if muni:
        count = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    tiles = status_3dtiles(code)
    return {
        "codigo_ibge": code,
        "edificios": count,
        "mvt": {
            "template": f"/api/v1/buildings/{code}/tiles/{{z}}/{{x}}/{{y}}.mvt",
            "minzoom": 10,
            "maxzoom": 18,
            "layer": MVT_LAYER,
            "cache_ttl_s": TILE_CACHE_TTL,
        },
        "geojson": {
            "url": f"/api/v1/buildings/{code}/geojson",
            "cache_ttl_s": GEOJSON_CACHE_TTL,
        },
        "tiles_3d": {
            **tiles,
            "tileset_api_url": f"/api/v1/buildings/{code}/3dtiles/tileset.json",
            "content_api_url": f"/api/v1/buildings/{code}/3dtiles/content.glb",
            "cache_ttl_s": TILESET_CACHE_TTL,
        },
        "selo_atributos": ["selo_3d", "qualidade", "fonte_altura", "altura_m"],
    }
