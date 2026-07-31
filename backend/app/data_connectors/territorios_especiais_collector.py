"""Coletor de territórios tradicionais e periferias — quilombos, TIs e comunidades urbanas."""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.data_connectors.base import fetch_json
from app.models import Municipio, TerritorioEspecial

logger = logging.getLogger(__name__)

DEFAULT_SEED = Path(__file__).resolve().parents[2] / "data" / "territorios_especiais_seed.csv"
TIPOS_VALIDOS = ("todas", "quilombo", "terra_indigena", "comunidade_urbana")
TIPO_ALIASES = {
    "quilombo": "quilombo",
    "quilombos": "quilombo",
    "terra_indigena": "terra_indigena",
    "ti": "terra_indigena",
    "terra indigena": "terra_indigena",
    "comunidade_urbana": "comunidade_urbana",
    "comunidade": "comunidade_urbana",
    "favela": "comunidade_urbana",
    "periferia": "comunidade_urbana",
}

INCRA_WFS = (
    "https://geoserver.incra.gov.br/geoserver/ows"
    "?service=WFS&version=1.0.0&request=GetFeature"
    "&typeName=incra:quilombos&outputFormat=application/json"
    "&maxFeatures=80"
)


def normalize_tipo(value: str | None) -> str:
    if not value:
        return "comunidade_urbana"
    key = value.strip().lower().replace("-", "_")
    return TIPO_ALIASES.get(key, key if key in TIPOS_VALIDOS else "comunidade_urbana")


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def load_seed_rows(codigo_ibge: str) -> list[dict[str, Any]]:
    if not DEFAULT_SEED.exists():
        return []
    code = str(codigo_ibge).zfill(7)[:7]
    rows: list[dict[str, Any]] = []
    with DEFAULT_SEED.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            if str(raw.get("codigo_ibge", "")).zfill(7)[:7] != code:
                continue
            lat = _parse_float(raw.get("latitude"))
            lon = _parse_float(raw.get("longitude"))
            if lat is None or lon is None:
                continue
            rows.append({
                "tipo": normalize_tipo(raw.get("tipo")),
                "nome": (raw.get("nome") or "").strip(),
                "codigo_oficial": (raw.get("codigo_oficial") or "").strip() or None,
                "latitude": lat,
                "longitude": lon,
                "raio_m": _parse_int(raw.get("raio_m")) or 400,
                "populacao_estimada": _parse_int(raw.get("populacao_estimada")),
                "fonte": (raw.get("fonte") or "bases_oficiais").strip(),
                "ano": _parse_int(raw.get("ano")) or 2022,
                "data_quality": "oficial",
            })
    return rows


def fetch_territory_rows(codigo_ibge: str) -> list[dict[str, Any]]:
    return load_seed_rows(codigo_ibge)


def _insert_geom_from_point(
    db: Session,
    territorio_id: int,
    lon: float,
    lat: float,
    raio_m: int,
) -> None:
    db.execute(
        text(
            """
            UPDATE territorios_especiais
            SET geom = ST_Multi(
                ST_Buffer(
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :raio
                )::geometry
            )
            WHERE id = :tid
            """
        ),
        {"lon": lon, "lat": lat, "raio": raio_m, "tid": territorio_id},
    )


def upsert_territorios(db: Session, muni: Municipio, rows: list[dict[str, Any]]) -> int:
    updated = 0
    now = datetime.now(timezone.utc)
    for row in rows:
        nome = row.get("nome")
        if not nome:
            continue
        tipo = normalize_tipo(row.get("tipo"))
        existing = (
            db.query(TerritorioEspecial)
            .filter(
                TerritorioEspecial.municipio_id == muni.id,
                TerritorioEspecial.tipo == tipo,
                TerritorioEspecial.nome == nome,
            )
            .first()
        )
        if existing:
            existing.codigo_oficial = row.get("codigo_oficial")
            existing.populacao_estimada = row.get("populacao_estimada")
            existing.ano = row.get("ano") or 2022
            existing.fonte = row.get("fonte") or "bases_oficiais"
            existing.data_quality = row.get("data_quality") or "oficial"
            existing.atualizado_em = now
            record = existing
        else:
            record = TerritorioEspecial(
                municipio_id=muni.id,
                tipo=tipo,
                nome=nome,
                codigo_oficial=row.get("codigo_oficial"),
                populacao_estimada=row.get("populacao_estimada"),
                ano=row.get("ano") or 2022,
                fonte=row.get("fonte") or "bases_oficiais",
                data_quality=row.get("data_quality") or "oficial",
                atualizado_em=now,
            )
            db.add(record)
            db.flush()
        lat = row.get("latitude")
        lon = row.get("longitude")
        raio_m = int(row.get("raio_m") or 400)
        if lat is not None and lon is not None and record.id:
            _insert_geom_from_point(db, record.id, float(lon), float(lat), raio_m)
        updated += 1
    return updated


def _clip_rows_to_municipio(db: Session, muni: Municipio, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mantém apenas pontos que intersectam o limite municipal (quando geom disponível)."""
    has_geom = db.query(Municipio.geom).filter(Municipio.id == muni.id, Municipio.geom.isnot(None)).first()
    if not has_geom:
        return rows

    kept: list[dict[str, Any]] = []
    for row in rows:
        lon = row.get("longitude")
        lat = row.get("latitude")
        if lon is None or lat is None:
            continue
        inside = db.execute(
            text(
                """
                SELECT ST_Intersects(
                    geom,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                )
                FROM municipios WHERE id = :mid
                """
            ),
            {"lon": lon, "lat": lat, "mid": muni.id},
        ).scalar()
        if inside:
            kept.append(row)
    return kept


def _fetch_incra_quilombos_near_muni(db: Session, muni: Municipio) -> list[dict[str, Any]]:
    """Best-effort: quilombos INCRA via WFS; filtra por interseção municipal."""
    try:
        payload = fetch_json(INCRA_WFS, cache_key=f"incra:quilombos:{muni.codigo_ibge}", cache_ttl=86400 * 14)
    except Exception as exc:
        logger.info("WFS INCRA indisponível para %s: %s", muni.codigo_ibge, exc)
        return []

    features = payload.get("features") or []
    if not features:
        return []

    rows: list[dict[str, Any]] = []
    for feature in features[:80]:
        props = feature.get("properties") or {}
        geom = feature.get("geometry")
        nome = props.get("nm_comunid") or props.get("nome") or props.get("name")
        if not nome or not geom:
            continue
        centroid = db.execute(
            text(
                "SELECT ST_X(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))),"
                "       ST_Y(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326)))"
            ),
            {"geojson": __import__("json").dumps(geom)},
        ).first()
        if not centroid:
            continue
        lon, lat = float(centroid[0]), float(centroid[1])
        rows.append({
            "tipo": "quilombo",
            "nome": str(nome).strip(),
            "codigo_oficial": str(props.get("cd_quilomb") or props.get("id") or "") or None,
            "latitude": lat,
            "longitude": lon,
            "raio_m": 500,
            "populacao_estimada": _parse_int(str(props.get("nu_famili") or "")),
            "fonte": "INCRA / GeoServer",
            "ano": 2022,
            "data_quality": "oficial",
        })
    return _clip_rows_to_municipio(db, muni, rows)


def sync_territorios_municipio(db: Session, muni: Municipio, *, force: bool = False) -> dict[str, Any]:
    existing = db.query(TerritorioEspecial).filter(TerritorioEspecial.municipio_id == muni.id).count()
    if existing > 0 and not force:
        return {"skipped": True, "count": existing}

    seed_rows = fetch_territory_rows(muni.codigo_ibge)
    seed_rows = _clip_rows_to_municipio(db, muni, seed_rows)
    wfs_rows = _fetch_incra_quilombos_near_muni(db, muni)

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in seed_rows + wfs_rows:
        key = (row["tipo"], row["nome"])
        merged[key] = row

    count = upsert_territorios(db, muni, list(merged.values()))
    return {
        "skipped": False,
        "count": count,
        "seed": len(seed_rows),
        "wfs_quilombos": len(wfs_rows),
        "codigo_ibge": muni.codigo_ibge,
    }


def territorio_matches_tipo(record: TerritorioEspecial, tipo_filtro: str) -> bool:
    if tipo_filtro == "todas":
        return True
    return record.tipo == tipo_filtro


def tipo_label(tipo: str) -> str:
    labels = {
        "quilombo": "Quilombo",
        "terra_indigena": "Terra indígena",
        "comunidade_urbana": "Comunidade urbana",
    }
    return labels.get(tipo, tipo)
