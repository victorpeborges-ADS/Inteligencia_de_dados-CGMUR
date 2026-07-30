"""Ground truth de alagamento observado (Fase 21c.5)."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.models import EventoAlagamentoObservado, HistoricoDesastreS2ID, Municipio
from ml.constants import FLOOD_EVENT_TYPES

logger = logging.getLogger(__name__)

OFFICIAL_S2ID_QUALITIES = frozenset({"oficial", "oficial_curado"})


def _is_flood_type(tipo: str) -> bool:
    t = tipo or ""
    return t in FLOOD_EVENT_TYPES or "Inunda" in t or "Alag" in t or "Enxurr" in t


def _fenomeno_from_tipo(tipo: str) -> str:
    """21d.9 — heurística pluvial × fluvial × misto a partir do tipo S2ID.

    Inundação (transbordamento de rio/corpo d'água) → fluvial;
    Alagamento Urbano / Enxurrada (drenagem/escoamento superficial local) → pluvial;
    demais tipos (ou combinados) → misto.
    """
    t = (tipo or "").lower()
    if "inunda" in t and "alag" not in t:
        return "fluvial"
    if "alag" in t or "enxurr" in t:
        return "pluvial"
    return "misto"


def _actor_label(actor: Any) -> str | None:
    if actor is None:
        return None
    if isinstance(actor, str):
        return actor[:120]
    username = getattr(actor, "username", None) or getattr(actor, "email", None)
    if username:
        return str(username)[:120]
    return str(actor)[:120]


def sync_official_s2id_to_observed_events(db: Session, codigo_ibge: str) -> dict[str, Any]:
    """Copia eventos S2ID oficiais para evento_alagamento_observado (sem sintéticos)."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {"codigo_ibge": code, "synced": 0, "reason": "municipio_nao_encontrado"}

    rows = (
        db.query(HistoricoDesastreS2ID)
        .filter(
            HistoricoDesastreS2ID.municipio_id == muni.id,
            HistoricoDesastreS2ID.data_quality.in_(tuple(OFFICIAL_S2ID_QUALITIES)),
        )
        .all()
    )

    created = 0
    for row in rows:
        if not _is_flood_type(row.tipo_desastre):
            continue
        inicio = dt.datetime.combine(row.data_ocorrencia, dt.time.min)
        exists = (
            db.query(EventoAlagamentoObservado)
            .filter(
                EventoAlagamentoObservado.codigo_ibge == code,
                EventoAlagamentoObservado.inicio_em == inicio,
                EventoAlagamentoObservado.tipo == row.tipo_desastre,
                EventoAlagamentoObservado.fonte == (row.fonte or "s2id_curado"),
            )
            .first()
        )
        if exists:
            if getattr(exists, "fenomeno", None) is None:
                exists.fenomeno = _fenomeno_from_tipo(row.tipo_desastre)
            continue

        geom = None
        if row.geom is not None:
            try:
                geom = from_shape(to_shape(row.geom), srid=4326)
            except Exception:
                geom = None

        db.add(
            EventoAlagamentoObservado(
                codigo_ibge=code,
                municipio_id=muni.id,
                tipo=row.tipo_desastre,
                inicio_em=inicio,
                severidade=None,
                populacao_afetada=int(row.populacao_afetada or 0) or None,
                fonte=row.fonte or "s2id_curado",
                data_quality=row.data_quality,
                referencia=row.referencia,
                fenomeno=_fenomeno_from_tipo(row.tipo_desastre),
                geom=geom,
                payload={"origem": "historico_desastres_s2id", "s2id_id": row.id},
            )
        )
        created += 1

    if created:
        db.commit()
    else:
        db.commit()  # possível backfill de fenomeno
    logger.info("evento_alagamento_observado %s: +%d", code, created)
    return {"codigo_ibge": code, "synced": created, "official_s2id": len(rows)}


def create_field_event(
    db: Session,
    *,
    codigo_ibge: str,
    tipo: str,
    inicio_em: dt.datetime,
    fim_em: dt.datetime | None = None,
    severidade: str | None = "media",
    fenomeno: str | None = "pluvial",
    populacao_afetada: int | None = None,
    precip_acumulada_mm: float | None = None,
    referencia: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    geojson: dict[str, Any] | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    """Cria evento observado pela Defesa Civil / campo (21c.4)."""
    from shapely.geometry import mapping, shape as shp_shape

    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    fen = (fenomeno or _fenomeno_from_tipo(tipo) or "pluvial").lower()
    if fen not in {"pluvial", "fluvial", "misto"}:
        fen = "pluvial"

    geom = None
    if geojson:
        try:
            g = geojson.get("geometry") if geojson.get("type") == "Feature" else geojson
            if g and g.get("type"):
                geom = from_shape(shp_shape(g), srid=4326)
        except Exception as exc:
            raise ValueError(f"GeoJSON inválido: {exc}") from exc
    elif lat is not None and lng is not None:
        geom = from_shape(Point(float(lng), float(lat)), srid=4326)
    else:
        raise ValueError("Informe lat/lng ou geojson do ponto/polígono")

    ts = inicio_em.replace(tzinfo=None) if getattr(inicio_em, "tzinfo", None) else inicio_em
    fim = None
    if fim_em is not None:
        fim = fim_em.replace(tzinfo=None) if getattr(fim_em, "tzinfo", None) else fim_em

    row = EventoAlagamentoObservado(
        codigo_ibge=code,
        municipio_id=muni.id,
        tipo=(tipo or "Alagamento Urbano")[:50],
        inicio_em=ts,
        fim_em=fim,
        severidade=(severidade or "media")[:20] if severidade else None,
        populacao_afetada=populacao_afetada,
        precip_acumulada_mm=precip_acumulada_mm,
        fonte="defesa_civil",
        data_quality="oficial",
        referencia=(referencia or "Registro em campo Defesa Civil")[:255],
        fenomeno=fen,
        geom=geom,
        payload={"origem": "campo_ui", "actor": _actor_label(actor)},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    geom_out = None
    try:
        if row.geom is not None:
            geom_out = mapping(to_shape(row.geom))
    except Exception:
        geom_out = None

    return {
        "id": row.id,
        "codigo_ibge": code,
        "tipo": row.tipo,
        "inicio_em": row.inicio_em.isoformat() if row.inicio_em else None,
        "fim_em": row.fim_em.isoformat() if row.fim_em else None,
        "severidade": row.severidade,
        "fenomeno": row.fenomeno,
        "fonte": row.fonte,
        "data_quality": row.data_quality,
        "geometry": geom_out,
    }


def list_observed_events(db: Session, codigo_ibge: str, *, limit: int = 50) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    rows = (
        db.query(EventoAlagamentoObservado)
        .filter(EventoAlagamentoObservado.codigo_ibge == code)
        .order_by(EventoAlagamentoObservado.inicio_em.desc())
        .limit(limit)
        .all()
    )
    items = []
    for r in rows:
        items.append({
            "id": r.id,
            "tipo": r.tipo,
            "inicio_em": r.inicio_em.isoformat() if r.inicio_em else None,
            "fim_em": r.fim_em.isoformat() if r.fim_em else None,
            "severidade": r.severidade,
            "fenomeno": getattr(r, "fenomeno", None),
            "fonte": r.fonte,
            "data_quality": r.data_quality,
            "referencia": r.referencia,
        })
    return {"codigo_ibge": code, "total": len(items), "eventos": items}


def observed_flood_dates(db: Session, codigo_ibge: str) -> set[dt.date]:
    """Datas com evento observado oficial (rótulo ML preferencial)."""
    code = str(codigo_ibge).zfill(7)[:7]
    rows = (
        db.query(EventoAlagamentoObservado.inicio_em)
        .filter(
            EventoAlagamentoObservado.codigo_ibge == code,
            EventoAlagamentoObservado.data_quality.in_(tuple(OFFICIAL_S2ID_QUALITIES)),
        )
        .all()
    )
    out: set[dt.date] = set()
    for (inicio,) in rows:
        if inicio is None:
            continue
        out.add(inicio.date() if hasattr(inicio, "date") else inicio)
    return out
