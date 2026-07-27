from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from app.models import HistoricoDesastreS2ID, Municipio
from ml.constants import FLOOD_EVENT_TYPES
from ml.paths import features_parquet
from ml.precipitation import collect_precipitation
from ml.terrain import extract_bairro_features

logger = logging.getLogger(__name__)

# Só estes níveis entram como rótulo positivo no treino full (Fase 21c.2)
ML_LABEL_QUALITIES = frozenset({"oficial", "oficial_curado"})


def _load_municipal_terrain(codigo_ibge: str) -> dict[str, float]:
    import json
    from ml.constants import FEATURE_DEFAULTS
    from ml.paths import terrain_parquet

    meta_path = terrain_parquet(codigo_ibge).with_suffix(".municipal.json")
    if meta_path.exists():
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        for key, default in FEATURE_DEFAULTS.items():
            data.setdefault(key, default)
        return data
    df = pd.read_parquet(terrain_parquet(codigo_ibge))
    out = {
        "impermeabilizacao_pct": float(df["impermeabilizacao_pct"].mean()),
        "cobertura_vegetal_pct": float(df["cobertura_vegetal_pct"].mean()),
        "declividade_media": float(df["declividade_media"].mean()),
    }
    if "water_proximity" in df.columns:
        out["water_proximity"] = float(df["water_proximity"].mean())
    for key, default in FEATURE_DEFAULTS.items():
        out.setdefault(key, default)
    return out


def _is_flood_type(tipo: str) -> bool:
    t = tipo or ""
    return t in FLOOD_EVENT_TYPES or "Inunda" in t or "Alag" in t or "Enxurr" in t


def _event_dates(db: Session, municipio_id: int, codigo_ibge: str) -> set[date]:
    """Datas-rótulo: preferência evento_alagamento_observado; senão S2ID oficial apenas."""
    try:
        from app.services.evento_alagamento_service import observed_flood_dates

        observed = observed_flood_dates(db, codigo_ibge)
        if observed:
            return observed
    except Exception as exc:
        logger.info("evento_alagamento_observado indisponível %s: %s", codigo_ibge, exc)

    rows = (
        db.query(
            HistoricoDesastreS2ID.data_ocorrencia,
            HistoricoDesastreS2ID.tipo_desastre,
            HistoricoDesastreS2ID.data_quality,
        )
        .filter(HistoricoDesastreS2ID.municipio_id == municipio_id)
        .all()
    )
    dates: set[date] = set()
    skipped_estimado = 0
    for row in rows:
        quality = (row.data_quality or "estimado").lower()
        if quality not in ML_LABEL_QUALITIES:
            skipped_estimado += 1
            continue
        if _is_flood_type(row.tipo_desastre):
            dates.add(row.data_ocorrencia)
    if skipped_estimado:
        logger.info(
            "ML labels %s: ignorados %d eventos S2ID não-oficiais (estimado/sintético)",
            codigo_ibge,
            skipped_estimado,
        )
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
    event_dates = _event_dates(db, muni.id, codigo_ibge)

    precip["date_only"] = precip["date"].dt.date
    # 21d.7 — janela de tolerância D-3..D+1 (evento no dia seguinte deixa de ser FN)
    from datetime import timedelta

    from ml.constants import LABEL_LAG_AFTER_DAYS, LABEL_LAG_BEFORE_DAYS

    expanded_dates = set(event_dates)
    for d in list(event_dates):
        for lag in range(-LABEL_LAG_BEFORE_DAYS, LABEL_LAG_AFTER_DAYS + 1):
            if lag == 0:
                continue
            expanded_dates.add(d + timedelta(days=lag))
    precip["label"] = precip["date_only"].apply(lambda d: 1 if d in expanded_dates else 0)

    # Garantir features de intensidade mesmo em parquet antigo
    if "intensidade_media_mm_h" not in precip.columns:
        from ml.intensity import enrich_intensity_features

        precip = enrich_intensity_features(precip, codigo_ibge=codigo_ibge)

    positives = precip[precip["label"] == 1]
    negatives = precip[precip["label"] == 0]
    max_neg = max(len(positives) * 40, 400)
    if len(negatives) > max_neg:
        negatives = negatives.sample(n=max_neg, random_state=42)
    labeled = pd.concat([positives, negatives], ignore_index=True).sort_values("date")

    for key, value in terrain.items():
        labeled[key] = value

    labeled["codigo_ibge"] = codigo_ibge
    labeled["label_source"] = "official_observed_or_s2id"
    output.parent.mkdir(parents=True, exist_ok=True)
    labeled.to_parquet(output, index=False)
    logger.info(
        "Dataset %s: %d positivos (só rótulo oficial), %d negativos, %d linhas",
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
