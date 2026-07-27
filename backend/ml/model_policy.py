"""Política de uso de modelos ML em produção (Fase 21a).

Artefatos `baseline_synthetic` aprendem uma fórmula do próprio código —
não podem alimentar o Monitor como “probabilidade”.
"""

from __future__ import annotations

import json
from typing import Any

from ml.paths import model_meta_path, model_path

# full = hold-out 21e OK; full_no_holdout = rótulos insuficientes para split temporal
PRODUCTION_MODEL_KINDS = frozenset({"full", "full_no_holdout"})
SYNTHETIC_MODEL_KIND = "baseline_synthetic"


def load_model_meta(codigo_ibge: str) -> dict[str, Any]:
    path = model_meta_path(str(codigo_ibge).zfill(7)[:7])
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def model_kind_of(meta: dict[str, Any] | None) -> str | None:
    if not meta:
        return None
    kind = meta.get("model_kind")
    return str(kind) if kind else None


def is_production_model(meta: dict[str, Any] | None) -> bool:
    return model_kind_of(meta) in PRODUCTION_MODEL_KINDS


def production_model_ready(codigo_ibge: str) -> bool:
    """True apenas se existe artefato local com model_kind=full."""
    code = str(codigo_ibge).zfill(7)[:7]
    if not model_path(code).exists():
        return False
    return is_production_model(load_model_meta(code))


def public_auc(meta: dict[str, Any] | None) -> float | None:
    """AUC só é exposto para modelos de produção (nunca sintético)."""
    if not is_production_model(meta):
        return None
    auc = (meta or {}).get("auc_roc_cv")
    if auc is None:
        return None
    try:
        value = float(auc)
    except (TypeError, ValueError):
        return None
    if value != value:  # NaN
        return None
    return value
