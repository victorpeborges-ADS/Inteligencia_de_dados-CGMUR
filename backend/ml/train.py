from __future__ import annotations

import json
import logging
import pickle
import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sqlalchemy.orm import Session

from ml.constants import (
    BAIRRO_MODEL_VERSION,
    FEATURE_COLUMNS,
    FEATURE_DEFAULTS,
    HOLDOUT_TRAIN_END_YEAR,
    ML_ALGORITHM,
    ML_TARGET_IBGE_CODES,
    MODEL_VERSION,
)
from ml.features import build_labeled_dataset, build_labeled_dataset_bairro, feature_matrix
from ml.model_factory import attach_permutation_importances, fit_classifier, make_classifier
from ml.paths import (
    bairro_model_meta_path,
    bairro_model_path,
    ensure_dirs,
    model_meta_path,
    model_path,
)
from ml.validation import evaluate_protocol, evaluate_spatial_hit_rate, write_model_card

logger = logging.getLogger(__name__)


def _temporal_cv_auc(x: pd.DataFrame, y: pd.Series, n_splits: int = 3) -> float:
    if y.sum() < 2 or len(y) < 20:
        return float("nan")
    tscv = TimeSeriesSplit(n_splits=min(n_splits, max(2, len(y) // 30)))
    scores: list[float] = []
    for train_idx, test_idx in tscv.split(x):
        if y.iloc[test_idx].nunique() < 2:
            continue
        clf, algo = make_classifier(ML_ALGORITHM)
        try:
            fit_classifier(clf, x.iloc[train_idx], y.iloc[train_idx], algorithm=algo)
        except Exception:
            clf, algo = make_classifier("random_forest")
            fit_classifier(clf, x.iloc[train_idx], y.iloc[train_idx], algorithm=algo)
        proba = clf.predict_proba(x.iloc[test_idx])
        if proba.shape[1] < 2 or y.iloc[test_idx].nunique() < 2:
            continue
        scores.append(roc_auc_score(y.iloc[test_idx], proba[:, 1]))
    return round(float(np.nanmean(scores)), 3) if scores else float("nan")


def _find_threshold_mm(model, terrain_row: dict[str, float], target_prob: float = 0.5) -> float:
    """Precipitação 24h (mm) acima da qual P(alagamento) > 50%."""
    from ml.intensity import intensity_from_precip

    best_mm = 65.0
    n_features = getattr(model, "n_features_in_", len(FEATURE_COLUMNS))
    cols = FEATURE_COLUMNS[: int(n_features)] if int(n_features) <= len(FEATURE_COLUMNS) else FEATURE_COLUMNS

    for mm in range(10, 201, 5):
        intensity = intensity_from_precip(float(mm), duracao_h=6.0)
        row = {
            "precip_24h": float(mm),
            "precip_48h": float(mm) * 1.4,
            "precip_72h": float(mm) * 1.7,
            "precip_7d": float(mm) * 2.5,
            "mes_do_ano": 3.0,
            **FEATURE_DEFAULTS,
            **intensity,
            **terrain_row,
        }
        vec = np.array([[float(row.get(c, FEATURE_DEFAULTS.get(c, 0.0))) for c in cols]])
        if vec.shape[1] != int(n_features):
            # Modelo antigo / calibrado: usa só as cols que cabem
            vec = vec[:, : int(n_features)]
        try:
            proba = model.predict_proba(vec)[0]
            prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
        except Exception:
            return best_mm
        if prob >= target_prob:
            return float(mm)
        best_mm = float(mm)
    return best_mm


def _terrain_from_df(df: pd.DataFrame) -> dict[str, float]:
    terrain = {
        "impermeabilizacao_pct": float(df["impermeabilizacao_pct"].iloc[0]),
        "cobertura_vegetal_pct": float(df["cobertura_vegetal_pct"].iloc[0]),
        "declividade_media": float(df["declividade_media"].iloc[0]),
    }
    for key, default in FEATURE_DEFAULTS.items():
        if key in df.columns:
            terrain[key] = float(df[key].iloc[0])
        else:
            terrain[key] = default
    return terrain


def train_municipality(db: Session, codigo_ibge: str, force: bool = False) -> dict[str, Any]:
    ensure_dirs()
    start = time.time()
    df = build_labeled_dataset(db, codigo_ibge, force=force)
    x, y = feature_matrix(df)

    n_pos = int(y.sum())
    if n_pos == 0:
        logger.warning(
            "Sem eventos positivos OFICIAIS para %s — não gravar como model_kind=full.",
            codigo_ibge,
        )
        return {
            "codigo_ibge": codigo_ibge,
            "model_kind": "insufficient_labels",
            "n_positive": 0,
            "note": (
                "Nenhum rótulo oficial (S2ID curado / evento_alagamento_observado). "
                "Eventos estimados/sintéticos são ignorados (Fase 21c.2)."
            ),
        }

    # 21e — hold-out temporal + baselines + calibração (modelo de produção = só treino)
    validation = evaluate_protocol(df, rain_threshold_mm=50.0, calibrate=True)
    validation_public = {
        k: v for k, v in validation.items()
        if k not in {"model", "train_df", "test_df"}
    }

    if validation.get("ok") and validation.get("model") is not None:
        model = validation["model"]
        train_df = validation["train_df"]
        x_fit, y_fit = feature_matrix(train_df)
        algo_name = validation.get("algorithm") or ML_ALGORITHM
        if not validation.get("calibrated"):
            model, algo_name = make_classifier(algo_name)
            fit_classifier(model, x_fit, y_fit, algorithm=algo_name)
            attach_permutation_importances(model, x_fit, y_fit)
        fit_n_pos = int(y_fit.sum())
        auc = validation.get("auc_roc_holdout")
        # Abaixo do baseline: ainda persiste, mas fora de produção (21e.4)
        if validation.get("discard_model"):
            model_kind = "full_below_baseline"
            note = "Hold-out OK, porém Brier pior que chuva e climatologia — não produção."
        else:
            model_kind = "full"
            note = (
                f"Treino hold-out ≤{HOLDOUT_TRAIN_END_YEAR}; "
                f"teste ≥{validation.get('test_start_year')} nunca usado no fit; "
                f"algoritmo={algo_name}."
            )
    else:
        logger.warning(
            "Hold-out 21e indisponível para %s (%s) — fallback CV + fit completo.",
            codigo_ibge,
            validation.get("reason") or "ok=False",
        )
        auc = _temporal_cv_auc(x, y)
        model, algo_name = make_classifier(ML_ALGORITHM)
        try:
            fit_classifier(model, x, y, algorithm=algo_name)
        except Exception:
            model, algo_name = make_classifier("random_forest")
            fit_classifier(model, x, y, algorithm=algo_name)
        attach_permutation_importances(model, x, y)
        fit_n_pos = n_pos
        model_kind = "full_no_holdout"
        note = f"{validation.get('reason') or 'holdout_fallback'} · algoritmo={algo_name}"

    terrain = _terrain_from_df(df)
    threshold = _find_threshold_mm(model, terrain)

    # 21e.5 — hit-rate espacial (zona de suscetibilidade × eventos oficiais)
    try:
        spatial = evaluate_spatial_hit_rate(db, codigo_ibge)
    except Exception as exc:
        logger.info("Validação espacial 21e.5 %s: %s", codigo_ibge, exc)
        spatial = {"disponivel": False, "reason": str(exc), "protocol": "21e5_spatial_hit_rate"}
    validation_public["spatial"] = spatial

    meta = {
        "codigo_ibge": codigo_ibge,
        "model_version": MODEL_VERSION,
        "model_kind": model_kind,
        "algorithm": validation.get("algorithm") or locals().get("algo_name") or ML_ALGORITHM,
        "auc_roc_cv": auc,
        "n_samples": len(df),
        "n_positive": fit_n_pos,
        "threshold_mm_24h": threshold,
        "terrain": terrain,
        "feature_columns": FEATURE_COLUMNS,
        "label_policy": "official_only",
        "validation": validation_public,
        "spatial_validation": spatial,
        "note": note,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "training_seconds": round(time.time() - start, 2),
    }

    with model_path(codigo_ibge).open("wb") as fh:
        pickle.dump({"model": model, "meta": meta}, fh)
    model_meta_path(codigo_ibge).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    card_path = model_meta_path(codigo_ibge).with_name(f"flood_model_{codigo_ibge}_card.md")
    write_model_card(card_path, codigo_ibge=codigo_ibge, meta=meta, validation=validation_public)

    logger.info(
        "Modelo %s — kind=%s AUC=%s Brier=%s threshold=%s mm (%.1fs)",
        codigo_ibge,
        model_kind,
        auc,
        validation_public.get("brier_model"),
        threshold,
        meta["training_seconds"],
    )
    # 21f.2 — treina também o modelo por bairro (não bloqueia o municipal)
    try:
        meta["bairro_model"] = train_municipality_bairro(db, codigo_ibge, force=force)
    except Exception as exc:
        logger.warning("Treino bairro %s falhou: %s", codigo_ibge, exc)
        meta["bairro_model"] = {"model_kind": "error", "note": str(exc)}
    return meta


def train_municipality_bairro(db: Session, codigo_ibge: str, force: bool = False) -> dict[str, Any]:
    """Treina classificador grain=bairro (Fase 21f.2) com o mesmo protocolo 21e."""
    ensure_dirs()
    start = time.time()
    df = build_labeled_dataset_bairro(db, codigo_ibge, force=force)
    if df.empty or "label" not in df.columns:
        return {
            "codigo_ibge": codigo_ibge,
            "model_kind": "insufficient_labels_bairro",
            "grain": "bairro",
            "n_positive": 0,
            "note": "Dataset bairro vazio.",
        }

    x, y = feature_matrix(df)
    n_pos = int(y.sum())
    if n_pos == 0:
        return {
            "codigo_ibge": codigo_ibge,
            "model_kind": "insufficient_labels_bairro",
            "grain": "bairro",
            "n_positive": 0,
            "note": "Sem rótulos positivos espacializados por bairro.",
        }

    validation = evaluate_protocol(df, rain_threshold_mm=50.0, calibrate=True)
    validation_public = {
        k: v for k, v in validation.items()
        if k not in {"model", "train_df", "test_df"}
    }

    if validation.get("ok") and validation.get("model") is not None:
        model = validation["model"]
        train_df = validation["train_df"]
        x_fit, y_fit = feature_matrix(train_df)
        algo_name = validation.get("algorithm") or ML_ALGORITHM
        if not validation.get("calibrated"):
            model, algo_name = make_classifier(algo_name)
            fit_classifier(model, x_fit, y_fit, algorithm=algo_name)
            attach_permutation_importances(model, x_fit, y_fit)
        fit_n_pos = int(y_fit.sum())
        auc = validation.get("auc_roc_holdout")
        if validation.get("discard_model"):
            model_kind = "full_bairro_below_baseline"
            note = "Hold-out OK, Brier abaixo do baseline — ranking usa fallback blend."
        else:
            model_kind = "full_bairro"
            note = (
                f"Treino bairro hold-out ≤{HOLDOUT_TRAIN_END_YEAR}; "
                f"algoritmo={algo_name}."
            )
    else:
        auc = _temporal_cv_auc(x, y)
        model, algo_name = make_classifier(ML_ALGORITHM)
        try:
            fit_classifier(model, x, y, algorithm=algo_name)
        except Exception:
            model, algo_name = make_classifier("random_forest")
            fit_classifier(model, x, y, algorithm=algo_name)
        attach_permutation_importances(model, x, y)
        fit_n_pos = n_pos
        model_kind = "full_bairro_no_holdout"
        note = f"{validation.get('reason') or 'holdout_fallback'} · algoritmo={algo_name}"

    terrain = _terrain_from_df(df)
    threshold = _find_threshold_mm(model, terrain)

    meta = {
        "codigo_ibge": codigo_ibge,
        "model_version": BAIRRO_MODEL_VERSION,
        "model_kind": model_kind,
        "grain": "bairro",
        "algorithm": validation.get("algorithm") or locals().get("algo_name") or ML_ALGORITHM,
        "auc_roc_cv": auc,
        "n_samples": len(df),
        "n_positive": fit_n_pos,
        "n_bairros": int(df["bairro_id"].nunique()) if "bairro_id" in df.columns else None,
        "threshold_mm_24h": threshold,
        "terrain": terrain,
        "feature_columns": FEATURE_COLUMNS,
        "label_policy": "official_spatial_or_susc_quartile",
        "validation": validation_public,
        "note": note,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "training_seconds": round(time.time() - start, 2),
    }

    with bairro_model_path(codigo_ibge).open("wb") as fh:
        pickle.dump({"model": model, "meta": meta}, fh)
    bairro_model_meta_path(codigo_ibge).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    card_path = bairro_model_meta_path(codigo_ibge).with_name(
        f"flood_model_{codigo_ibge}_bairro_card.md"
    )
    write_model_card(card_path, codigo_ibge=codigo_ibge, meta=meta, validation=validation_public)

    logger.info(
        "Modelo bairro %s — kind=%s AUC=%s n_pos=%s (%.1fs)",
        codigo_ibge,
        model_kind,
        auc,
        fit_n_pos,
        meta["training_seconds"],
    )
    return meta


def train_all(db: Session, force: bool = False) -> list[dict[str, Any]]:
    results = []
    for codigo in ML_TARGET_IBGE_CODES:
        results.append(train_municipality(db, codigo, force=force))
    return results
