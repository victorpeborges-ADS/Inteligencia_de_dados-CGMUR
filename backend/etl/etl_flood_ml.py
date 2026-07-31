#!/usr/bin/env python3
"""ETL + treino do modelo estatístico de alagamento.

Uso:
  python etl/etl_flood_ml.py --all
  python etl/etl_flood_ml.py --municipio 2611606
  python etl/etl_flood_ml.py --train-only
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from ml.constants import ML_TARGET_IBGE_CODES
from ml.paths import ensure_dirs
from ml.precipitation import collect_precipitation
from ml.terrain import extract_bairro_features
from ml.features import build_labeled_dataset, build_labeled_dataset_bairro
from ml.train import train_all, train_municipality

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("etl_flood_ml")


def run_etl(db, codigo_ibge: str, force: bool = False) -> None:
    logger.info("=== ETL %s ===", codigo_ibge)
    collect_precipitation(db, codigo_ibge, force=force)
    extract_bairro_features(db, codigo_ibge, force=force)
    build_labeled_dataset(db, codigo_ibge, force=force)
    build_labeled_dataset_bairro(db, codigo_ibge, force=force)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline ML alagamento Sinidu+Clima")
    parser.add_argument("--all", action="store_true", help="Processar os 5 municípios-alvo")
    parser.add_argument("--municipio", type=str, help="Código IBGE")
    parser.add_argument("--train-only", action="store_true", help="Pular coleta, só treinar")
    parser.add_argument("--force", action="store_true", help="Reprocessar Parquets")
    args = parser.parse_args()

    ensure_dirs()
    targets = ML_TARGET_IBGE_CODES if args.all or not args.municipio else [args.municipio]

    db = SessionLocal()
    try:
        if not args.train_only:
            for codigo in targets:
                run_etl(db, codigo, force=args.force)

        if args.all or args.municipio:
            if args.municipio and not args.all:
                meta = train_municipality(db, args.municipio, force=args.force)
                logger.info("Treino concluído: AUC=%s", meta.get("auc_roc_cv"))
            else:
                metas = train_all(db, force=args.force)
                for meta in metas:
                    logger.info("%s — AUC=%s, threshold=%s mm", meta["codigo_ibge"], meta.get("auc_roc_cv"), meta.get("threshold_mm_24h"))
        elif args.train_only:
            metas = train_all(db, force=args.force)
            for meta in metas:
                logger.info("%s — AUC=%s", meta["codigo_ibge"], meta.get("auc_roc_cv"))
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
