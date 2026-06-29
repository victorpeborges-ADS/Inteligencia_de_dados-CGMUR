from __future__ import annotations

import json
import logging
import pickle
import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sqlalchemy.orm import Session

from ml.constants import FEATURE_COLUMNS, ML_TARGET_IBGE_CODES, MODEL_VERSION, RF_PARAMS
from ml.features import build_labeled_dataset, feature_matrix
from ml.paths import ensure_dirs, model_meta_path, model_path

logger = logging.getLogger(__name__)


def _temporal_cv_auc(x: pd.DataFrame, y: pd.Series, n_splits: int = 3) -> float:
    if y.sum() < 2 or len(y) < 20:
        return float("nan")
    tscv = TimeSeriesSplit(n_splits=min(n_splits, max(2, len(y) // 30)))
    scores: list[float] = []
    for train_idx, test_idx in tscv.split(x):
        if y.iloc[test_idx].nunique() < 2:
            continue
        clf = RandomForestClassifier(**RF_PARAMS)
        clf.fit(x.iloc[train_idx], y.iloc[train_idx])
        proba = clf.predict_proba(x.iloc[test_idx])
        if proba.shape[1] < 2 or y.iloc[test_idx].nunique() < 2:
            continue
        scores.append(roc_auc_score(y.iloc[test_idx], proba[:, 1]))
    return round(float(np.nanmean(scores)), 3) if scores else float("nan")


def _find_threshold_mm(model: RandomForestClassifier, terrain_row: dict[str, float], target_prob: float = 0.5) -> float:
    """Precipitação 24h (mm) acima da qual P(alagamento) > 50%."""
    best_mm = 65.0
    for mm in range(10, 201, 5):
        row = {
            "precip_24h": float(mm),
            "precip_48h": float(mm) * 1.4,
            "precip_72h": float(mm) * 1.7,
            "precip_7d": float(mm) * 2.5,
            "mes_do_ano": 3.0,
            **terrain_row,
        }
        vec = np.array([[row[c] for c in FEATURE_COLUMNS]])
        prob = model.predict_proba(vec)[0][1]
        if prob >= target_prob:
            return float(mm)
        best_mm = float(mm)
    return best_mm


def train_municipality(db: Session, codigo_ibge: str, force: bool = False) -> dict[str, Any]:
    ensure_dirs()
    start = time.time()
    df = build_labeled_dataset(db, codigo_ibge, force=force)
    x, y = feature_matrix(df)

    if y.sum() == 0:
        logger.warning("Sem eventos positivos para %s — modelo baseline.", codigo_ibge)

    auc = _temporal_cv_auc(x, y)
    model = RandomForestClassifier(**RF_PARAMS)
    model.fit(x, y)

    terrain = {
        "impermeabilizacao_pct": float(df["impermeabilizacao_pct"].iloc[0]),
        "cobertura_vegetal_pct": float(df["cobertura_vegetal_pct"].iloc[0]),
        "declividade_media": float(df["declividade_media"].iloc[0]),
    }
    threshold = _find_threshold_mm(model, terrain)

    meta = {
        "codigo_ibge": codigo_ibge,
        "model_version": MODEL_VERSION,
        "auc_roc_cv": auc,
        "n_samples": len(df),
        "n_positive": int(y.sum()),
        "threshold_mm_24h": threshold,
        "terrain": terrain,
        "feature_columns": FEATURE_COLUMNS,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "training_seconds": round(time.time() - start, 2),
    }

    with model_path(codigo_ibge).open("wb") as fh:
        pickle.dump({"model": model, "meta": meta}, fh)
    model_meta_path(codigo_ibge).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Modelo %s treinado — AUC=%s, threshold=%s mm, %.1fs", codigo_ibge, auc, threshold, meta["training_seconds"])
    return meta


def train_all(db: Session, force: bool = False) -> list[dict[str, Any]]:
    results = []
    for codigo in ML_TARGET_IBGE_CODES:
        results.append(train_municipality(db, codigo, force=force))
    return results
