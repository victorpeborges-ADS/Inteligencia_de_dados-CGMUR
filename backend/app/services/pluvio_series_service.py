"""Persistência de séries pluviométricas no PostGIS (Fase 21b.6)."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Municipio, SeriePluviometricaObservada
from app.timeutil import utc_now

logger = logging.getLogger(__name__)


def upsert_pluvio_rows(db: Session, rows: list[dict[str, Any]]) -> int:
    """Upsert em lote; retorna quantas linhas foram enviadas ao banco."""
    if not rows:
        return 0
    table = SeriePluviometricaObservada.__table__
    # PostgreSQL ON CONFLICT — chunks para não estourar parâmetro
    written = 0
    chunk_size = 500
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        stmt = insert(table).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["fonte", "estacao_id", "observed_at", "codigo_ibge"],
            set_={
                "precip_mm": stmt.excluded.precip_mm,
                "data_quality": stmt.excluded.data_quality,
                "estacao_nome": stmt.excluded.estacao_nome,
                "lat": stmt.excluded.lat,
                "lng": stmt.excluded.lng,
                "granularidade": stmt.excluded.granularidade,
                "municipio_id": stmt.excluded.municipio_id,
                "ingestido_em": stmt.excluded.ingestido_em,
                "raw_payload": stmt.excluded.raw_payload,
            },
        )
        db.execute(stmt)
        written += len(chunk)
    db.commit()
    return written


def persist_openmeteo_daily(
    db: Session,
    codigo_ibge: str,
    df: pd.DataFrame,
    *,
    lat: float | None = None,
    lng: float | None = None,
) -> int:
    """Grava série diária Open-Meteo (ERA5) — qualidade=reanalise, não oficial."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    estacao_id = f"openmeteo:{code}"
    now = utc_now()
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        ts = pd.Timestamp(row["date"]).to_pydatetime()
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.replace(tzinfo=None)
        rows.append({
            "codigo_ibge": code,
            "municipio_id": muni.id if muni else None,
            "estacao_id": estacao_id,
            "estacao_nome": f"Open-Meteo ERA5 centróide {code}",
            "lat": lat,
            "lng": lng,
            "observed_at": ts,
            "precip_mm": float(row.get("precipitation_sum") or 0.0),
            "granularidade": "diaria",
            "data_quality": "reanalise",
            "fonte": "open_meteo_era5",
            "ingestido_em": now,
            "raw_payload": None,
        })
    n = upsert_pluvio_rows(db, rows)
    logger.info("Pluvio Open-Meteo persistido %s: %d dias", code, n)
    return n


def daily_series_from_db(
    db: Session,
    codigo_ibge: str,
    *,
    prefer_official: bool = True,
) -> pd.DataFrame | None:
    """Lê série diária do PostGIS. Prefere estação oficial; senão reanálise."""
    code = str(codigo_ibge).zfill(7)[:7]
    q = db.query(SeriePluviometricaObservada).filter(
        SeriePluviometricaObservada.codigo_ibge == code,
        SeriePluviometricaObservada.granularidade == "diaria",
    )
    if prefer_official:
        official = q.filter(SeriePluviometricaObservada.data_quality == "oficial").all()
        rows = official or q.filter(SeriePluviometricaObservada.fonte == "open_meteo_era5").all()
    else:
        rows = q.all()
    if not rows:
        return None

    # Agrega por dia (média entre estações se houver várias)
    by_day: dict[dt.date, list[float]] = {}
    for r in rows:
        d = r.observed_at.date() if hasattr(r.observed_at, "date") else r.observed_at
        by_day.setdefault(d, []).append(float(r.precip_mm or 0))
    records = [
        {"date": pd.Timestamp(day), "precipitation_sum": sum(vals) / len(vals), "precipitation_hours": 0.0}
        for day, vals in sorted(by_day.items())
    ]
    return pd.DataFrame(records)
