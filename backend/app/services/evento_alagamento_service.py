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
                geom=geom,
                payload={"origem": "historico_desastres_s2id", "s2id_id": row.id},
            )
        )
        created += 1

    if created:
        db.commit()
    logger.info("evento_alagamento_observado %s: +%d", code, created)
    return {"codigo_ibge": code, "synced": created, "official_s2id": len(rows)}


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
    return {r.inicio_em.date() if hasattr(r.inicio_em, "date") else r.inicio_em for r in rows}
