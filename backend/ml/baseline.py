"""Modelos baseline sintéticos — inferência imediata sem ETL OpenMeteo completo."""
from __future__ import annotations

import json
import logging
import pickle
import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ml.constants import FEATURE_COLUMNS, ML_TARGET_IBGE_CODES, MODEL_VERSION, RF_PARAMS
from ml.paths import ensure_dirs, model_meta_path, model_path

logger = logging.getLogger(__name__)

# Terreno típico por município (proxy MapBiomas + DEM)
TERRAIN_PRESETS: dict[str, dict[str, float]] = {
    "2611606": {"impermeabilizacao_pct": 62.0, "cobertura_vegetal_pct": 8.0, "declividade_media": 2.8},   # Recife
    "2927408": {"impermeabilizacao_pct": 55.0, "cobertura_vegetal_pct": 12.0, "declividade_media": 4.5},  # Salvador
    "4314902": {"impermeabilizacao_pct": 48.0, "cobertura_vegetal_pct": 18.0, "declividade_media": 3.2}, # Porto Alegre
    "2507507": {"impermeabilizacao_pct": 58.0, "cobertura_vegetal_pct": 10.0, "declividade_media": 2.5},  # João Pessoa
    "4113700": {"impermeabilizacao_pct": 52.0, "cobertura_vegetal_pct": 14.0, "declividade_media": 3.8},  # Londrina
}


def _temporal_cv_auc(x: pd.DataFrame, y: pd.Series, n_splits: int = 3) -> float:
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import TimeSeriesSplit

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
        if proba.shape[1] < 2:
            continue
        scores.append(roc_auc_score(y.iloc[test_idx], proba[:, 1]))
    return round(float(np.nanmean(scores)), 3) if scores else float("nan")


def _find_threshold_mm(model: RandomForestClassifier, terrain_row: dict[str, float], target_prob: float = 0.5) -> float:
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


def _synthetic_labeled_frame(terrain: dict[str, float], codigo_ibge: str, n: int = 900) -> pd.DataFrame:
    """Gera dataset sintético calibrado: mais chuva + impermeabilização → mais alagamentos."""
    seed = int(codigo_ibge[-6:]) % (2**31 - 1)
    rng = np.random.default_rng(seed)

    precip_24h = rng.uniform(0, 200, n)
    precip_48h = precip_24h * rng.uniform(1.15, 1.85, n)
    precip_72h = precip_24h * rng.uniform(1.35, 2.25, n)
    precip_7d = precip_24h * rng.uniform(1.8, 3.8, n)
    mes = rng.integers(1, 13, n).astype(float)

    imperm = terrain["impermeabilizacao_pct"]
    veg = terrain["cobertura_vegetal_pct"]
    slope = terrain["declividade_media"]

    # Score logístico simplificado (calibrado para threshold ~60–80 mm em cidades costeiras)
    logit = (
        -2.1
        + 0.028 * precip_24h
        + 0.012 * precip_48h
        + 0.006 * precip_72h
        + 0.018 * imperm
        - 0.022 * veg
        + 0.035 * slope
        + 0.08 * np.sin((mes - 3) * np.pi / 6)  # sazonalidade chuvosa
        + rng.normal(0, 0.35, n)
    )
    prob = 1.0 / (1.0 + np.exp(-logit))
    label = (prob >= 0.5).astype(int)

    return pd.DataFrame({
        "precip_24h": precip_24h,
        "precip_48h": precip_48h,
        "precip_72h": precip_72h,
        "precip_7d": precip_7d,
        "mes_do_ano": mes,
        "impermeabilizacao_pct": imperm,
        "cobertura_vegetal_pct": veg,
        "declividade_media": slope,
        "label": label,
        "codigo_ibge": codigo_ibge,
    })


def terrain_from_municipality(db, codigo_ibge: str) -> dict[str, float]:
    """Deriva proxy de terreno a partir de cobertura MapBiomas no banco."""
    from sqlalchemy import func

    from app.models import CoberturaVegetalMapBiomas, Municipio

    preset = dict(TERRAIN_PRESETS.get(codigo_ibge, TERRAIN_PRESETS["2611606"]))
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni or muni.geom is None:
        return preset

    total_area = db.scalar(func.ST_Area(muni.geom))
    forest_area = db.query(func.sum(func.ST_Area(CoberturaVegetalMapBiomas.geom))).filter(
        CoberturaVegetalMapBiomas.municipio_id == muni.id,
        CoberturaVegetalMapBiomas.classe_uso == "Vegetação / Floresta",
    ).scalar()

    if total_area and forest_area:
        veg_pct = min(100.0, (float(forest_area) / float(total_area)) * 100.0)
        preset["cobertura_vegetal_pct"] = round(veg_pct, 1)
        preset["impermeabilizacao_pct"] = round(max(25.0, min(85.0, 100.0 - veg_pct * 0.55)), 1)

    return preset


def train_baseline_model(codigo_ibge: str, terrain: dict[str, float] | None = None) -> dict[str, Any]:
    """Treina e persiste Random Forest baseline para um município."""
    ensure_dirs()
    terrain = terrain or TERRAIN_PRESETS.get(codigo_ibge, TERRAIN_PRESETS["2611606"])
    start = time.time()

    df = _synthetic_labeled_frame(terrain, codigo_ibge)
    x = df[FEATURE_COLUMNS].astype(float)
    y = df["label"].astype(int)

    auc = _temporal_cv_auc(x, y)
    model = RandomForestClassifier(**RF_PARAMS)
    model.fit(x, y)
    threshold = _find_threshold_mm(model, terrain)

    meta = {
        "codigo_ibge": codigo_ibge,
        "model_version": MODEL_VERSION,
        "model_kind": "baseline_synthetic",
        "auc_roc_cv": auc,
        "n_samples": len(df),
        "n_positive": int(y.sum()),
        "threshold_mm_24h": threshold,
        "terrain": terrain,
        "feature_columns": FEATURE_COLUMNS,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "training_seconds": round(time.time() - start, 2),
        "note": (
            "Modelo baseline sintético. Execute etl/etl_flood_ml.py --municipio "
            f"{codigo_ibge} para retreinar com OpenMeteo + S2ID."
        ),
    }

    with model_path(codigo_ibge).open("wb") as fh:
        pickle.dump({"model": model, "meta": meta}, fh)
    model_meta_path(codigo_ibge).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "Baseline ML %s — AUC=%s, threshold=%.0f mm, %.1fs",
        codigo_ibge, auc, threshold, meta["training_seconds"],
    )
    return meta


def train_all_baselines() -> list[dict[str, Any]]:
    return [train_baseline_model(codigo) for codigo in ML_TARGET_IBGE_CODES]
