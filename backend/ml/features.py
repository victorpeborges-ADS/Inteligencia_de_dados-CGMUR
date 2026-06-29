from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models import HistoricoDesastreS2ID, Municipio
from ml.constants import FLOOD_EVENT_TYPES
from ml.paths import features_parquet
from ml.precipitation import collect_precipitation
from ml.terrain import extract_bairro_features

logger = logging.getLogger(__name__)


def _load_municipal_terrain(codigo_ibge: str) -> dict[str, float]:
    import json
    from ml.paths import terrain_parquet

    meta_path = terrain_parquet(codigo_ibge).with_suffix(".municipal.json")
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    df = pd.read_parquet(terrain_parquet(codigo_ibge))
    return {
        "impermeabilizacao_pct": float(df["impermeabilizacao_pct"].mean()),
        "cobertura_vegetal_pct": float(df["cobertura_vegetal_pct"].mean()),
        "declividade_media": float(df["declividade_media"].mean()),
    }


def _event_dates(db: Session, municipio_id: int) -> set[date]:
    rows = (
        db.query(HistoricoDesastreS2ID.data_ocorrencia, HistoricoDesastreS2ID.tipo_desastre)
        .filter(HistoricoDesastreS2ID.municipio_id == municipio_id)
        .all()
    )
    dates: set[date] = set()
    for row in rows:
        if row.tipo_desastre in FLOOD_EVENT_TYPES or "Inunda" in row.tipo_desastre or "Alag" in row.tipo_desastre:
            dates.add(row.data_ocorrencia)
    return dates


def build_labeled_dataset(db: Session, codigo_ibge: str, force: bool = False) -> pd.DataFrame:
    output = features_parquet(codigo_ibge)
    if output.exists() and not force:
        return pd.read_parquet(output)

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise ValueError(f"Município {codigo_ibge} não encontrado.")

    precip = collect_precipitation(db, codigo_ibge, force=force)
    extract_bairro_features(db, codigo_ibge, force=force)
    terrain = _load_municipal_terrain(codigo_ibge)
    event_dates = _event_dates(db, muni.id)

    precip["date_only"] = precip["date"].dt.date
    precip["label"] = precip["date_only"].apply(lambda d: 1 if d in event_dates else 0)

    # Amostragem negativa: limitar para manter RAM < 2 GB
    positives = precip[precip["label"] == 1]
    negatives = precip[precip["label"] == 0]
    max_neg = max(len(positives) * 40, 400)
    if len(negatives) > max_neg:
        negatives = negatives.sample(n=max_neg, random_state=42)
    labeled = pd.concat([positives, negatives], ignore_index=True).sort_values("date")

    for key, value in terrain.items():
        labeled[key] = value

    labeled["codigo_ibge"] = codigo_ibge
    output.parent.mkdir(parents=True, exist_ok=True)
    labeled.to_parquet(output, index=False)
    logger.info(
        "Dataset %s: %d positivos, %d negativos, %d linhas",
        codigo_ibge,
        int(labeled["label"].sum()),
        int((labeled["label"] == 0).sum()),
        len(labeled),
    )
    return labeled


def feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    from ml.constants import FEATURE_COLUMNS

    x = df[FEATURE_COLUMNS].astype(float)
    y = df["label"].astype(int)
    return x, y
