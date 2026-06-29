"""Garante modelos ML de alagamento disponíveis no boot ou na primeira inferência."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from ml.baseline import TERRAIN_PRESETS, train_baseline_model
from ml.constants import ML_TARGET_IBGE_CODES
from ml.paths import ensure_dirs, model_path

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"


def _copy_artifact(codigo_ibge: str) -> bool:
    src = ARTIFACTS_DIR / f"flood_model_{codigo_ibge}_v1.pkl"
    dst = model_path(codigo_ibge)
    if not src.exists():
        return False
    ensure_dirs()
    shutil.copy2(src, dst)
    meta_src = ARTIFACTS_DIR / f"flood_model_{codigo_ibge}_meta.json"
    if meta_src.exists():
        shutil.copy2(meta_src, dst.with_name(meta_src.name))
    logger.info("Modelo ML copiado de artifacts → %s", dst)
    return True


def ensure_model_for(codigo_ibge: str, db: Session | None = None) -> bool:
    """Garante modelo para um IBGE. Retorna True se disponível após a operação."""
    code = str(codigo_ibge).strip().zfill(7)[:7]
    if model_path(code).exists():
        return True

    if _copy_artifact(code):
        return True

    if db is not None:
        try:
            from ml.train import train_municipality

            train_municipality(db, code)
            if model_path(code).exists():
                return True
        except Exception as exc:
            logger.warning("Treino completo falhou para %s: %s", code, exc)

    terrain = TERRAIN_PRESETS.get(code)
    if db is not None:
        try:
            from ml.baseline import terrain_from_municipality

            terrain = terrain_from_municipality(db, code)
        except Exception as exc:
            logger.warning("Terreno derivado falhou para %s: %s", code, exc)

    train_baseline_model(code, terrain)
    return model_path(code).exists()


def ensure_flood_models(db: Session | None = None) -> dict[str, bool]:
    """Garante os 5 modelos-alvo. Usado no boot da API."""
    ensure_dirs()
    status: dict[str, bool] = {}
    for codigo in ML_TARGET_IBGE_CODES:
        try:
            status[codigo] = ensure_model_for(codigo, db)
        except Exception as exc:
            logger.error("Falha ao garantir modelo %s: %s", codigo, exc)
            status[codigo] = False
    ready = sum(status.values())
    logger.info("Modelos ML alagamento: %d/%d prontos", ready, len(ML_TARGET_IBGE_CODES))
    return status
