from __future__ import annotations

import os
from pathlib import Path

MODELS_DIR = Path(os.getenv("MODELS_DIR", "/data/models"))
DATA_DIR = Path(os.getenv("ML_DATA_DIR", "/data/ml"))

PRECIP_DIR = DATA_DIR / "precipitation"
FEATURES_DIR = DATA_DIR / "features"
TERRAIN_DIR = DATA_DIR / "terrain"


def ensure_dirs() -> None:
    for path in (MODELS_DIR, PRECIP_DIR, FEATURES_DIR, TERRAIN_DIR):
        path.mkdir(parents=True, exist_ok=True)


def model_path(codigo_ibge: str) -> Path:
    return MODELS_DIR / f"flood_model_{codigo_ibge}_v1.pkl"


def model_meta_path(codigo_ibge: str) -> Path:
    return MODELS_DIR / f"flood_model_{codigo_ibge}_meta.json"


def bairro_model_path(codigo_ibge: str) -> Path:
    """Modelo por bairro (Fase 21f.2) — grain=bairro."""
    return MODELS_DIR / f"flood_model_{codigo_ibge}_bairro_v1.pkl"


def bairro_model_meta_path(codigo_ibge: str) -> Path:
    return MODELS_DIR / f"flood_model_{codigo_ibge}_bairro_meta.json"


def precip_parquet(codigo_ibge: str) -> Path:
    return PRECIP_DIR / f"{codigo_ibge}_daily.parquet"


def features_parquet(codigo_ibge: str) -> Path:
    return FEATURES_DIR / f"{codigo_ibge}_labeled.parquet"


def bairro_features_parquet(codigo_ibge: str) -> Path:
    return FEATURES_DIR / f"{codigo_ibge}_labeled_bairro.parquet"


def terrain_parquet(codigo_ibge: str) -> Path:
    return TERRAIN_DIR / f"{codigo_ibge}_bairros.parquet"
