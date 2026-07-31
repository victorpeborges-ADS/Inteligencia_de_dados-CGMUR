"""Persistência de séries fluviométricas (cota/vazão) no PostGIS (Fase 21c.3/21d.9)."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import SerieFluviometricaObservada
from app.timeutil import utc_now

logger = logging.getLogger(__name__)


def upsert_fluvio_rows(db: Session, rows: list[dict[str, Any]]) -> int:
    """Upsert em lote (mirror de ``pluvio_series_service.upsert_pluvio_rows``)."""
    if not rows:
        return 0
    table = SerieFluviometricaObservada.__table__
    written = 0
    chunk_size = 500
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        stmt = insert(table).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["fonte", "estacao_id", "observed_at", "codigo_ibge"],
            set_={
                "cota_m": stmt.excluded.cota_m,
                "vazao_m3s": stmt.excluded.vazao_m3s,
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


def daily_cota_series_from_db(db: Session, codigo_ibge: str) -> pd.DataFrame | None:
    """Série diária de cota (m) — média entre estações do município, se houver.

    Usada pelas features ML (21d.9: ``cota_rio_disponivel`` / ``cota_rio_anomalia``).
    """
    code = str(codigo_ibge).zfill(7)[:7]
    rows = (
        db.query(SerieFluviometricaObservada)
        .filter(
            SerieFluviometricaObservada.codigo_ibge == code,
            SerieFluviometricaObservada.cota_m.isnot(None),
        )
        .all()
    )
    if not rows:
        return None

    by_day: dict[dt.date, list[float]] = {}
    for r in rows:
        d = r.observed_at.date() if hasattr(r.observed_at, "date") else r.observed_at
        by_day.setdefault(d, []).append(float(r.cota_m or 0))
    if not by_day:
        return None

    records = [
        {"date": pd.Timestamp(day), "cota_m": sum(vals) / len(vals)}
        for day, vals in sorted(by_day.items())
    ]
    return pd.DataFrame(records)


def latest_stations_for_municipality(db: Session, codigo_ibge: str) -> list[dict[str, Any]]:
    """Lista estações fluviométricas já ingeridas para o município (debug/UI)."""
    code = str(codigo_ibge).zfill(7)[:7]
    rows = (
        db.query(SerieFluviometricaObservada)
        .filter(SerieFluviometricaObservada.codigo_ibge == code)
        .order_by(SerieFluviometricaObservada.observed_at.desc())
        .limit(500)
        .all()
    )
    seen: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.estacao_id in seen:
            continue
        seen[r.estacao_id] = {
            "estacao_id": r.estacao_id,
            "estacao_nome": r.estacao_nome,
            "lat": float(r.lat) if r.lat is not None else None,
            "lng": float(r.lng) if r.lng is not None else None,
            "ultimo_registro": r.observed_at.isoformat() if r.observed_at else None,
            "fonte": r.fonte,
        }
    return list(seen.values())


def cota_features_for_dates(db: Session, codigo_ibge: str, df: pd.DataFrame) -> pd.DataFrame:
    """Anexa ``cota_rio_disponivel`` (0/1) e ``cota_rio_anomalia`` (z-score) ao dataset.

    Se não houver série fluviométrica, preenche zeros (backward-compatible com
    artefatos antigos via FEATURE_DEFAULTS).
    """
    out = df.copy()
    series = daily_cota_series_from_db(db, codigo_ibge)
    if series is None or series.empty or "date" not in out.columns:
        out["cota_rio_disponivel"] = 0.0
        out["cota_rio_anomalia"] = 0.0
        return out

    mean = float(series["cota_m"].mean())
    std = float(series["cota_m"].std(ddof=0) or 0.0)
    by_day = {
        pd.Timestamp(r["date"]).date(): float(r["cota_m"])
        for _, r in series.iterrows()
    }

    disponivel: list[float] = []
    anomalia: list[float] = []
    for ts in out["date"]:
        d = pd.Timestamp(ts).date()
        if d in by_day:
            disponivel.append(1.0)
            if std > 1e-6:
                anomalia.append((by_day[d] - mean) / std)
            else:
                anomalia.append(0.0)
        else:
            disponivel.append(0.0)
            anomalia.append(0.0)

    out["cota_rio_disponivel"] = disponivel
    out["cota_rio_anomalia"] = anomalia
    return out
