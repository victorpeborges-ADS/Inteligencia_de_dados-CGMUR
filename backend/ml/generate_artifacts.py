#!/usr/bin/env python3
"""Gera artefatos baseline em ml/artifacts/ para versionamento no repositório."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
LOCAL_MODELS = ROOT / "ml" / "artifacts" / "_build"

os.environ.setdefault("MODELS_DIR", str(LOCAL_MODELS))
os.environ.setdefault("ML_DATA_DIR", str(ROOT / "ml" / "artifacts" / "_ml_data"))

sys.path.insert(0, str(ROOT))

from ml.baseline import train_all_baselines
from ml.constants import ML_TARGET_IBGE_CODES
from ml.paths import model_meta_path, model_path


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    LOCAL_MODELS.mkdir(parents=True, exist_ok=True)
    metas = train_all_baselines()
    for codigo in ML_TARGET_IBGE_CODES:
        src = model_path(codigo)
        dst = ARTIFACTS / src.name
        shutil.copy2(src, dst)
        meta = model_meta_path(codigo)
        if meta.exists():
            shutil.copy2(meta, ARTIFACTS / meta.name)
        auc = next(m["auc_roc_cv"] for m in metas if m["codigo_ibge"] == codigo)
        print(f"  {codigo} → {dst.name} (AUC={auc})")
    print(f"\n{len(ML_TARGET_IBGE_CODES)} modelos em {ARTIFACTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
