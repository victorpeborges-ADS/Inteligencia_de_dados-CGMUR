#!/usr/bin/env python3
"""Pipeline de carga dos 50 municípios prioritários.

Uso:
  python etl/etl_municipios_seed.py --seed-only
  python etl/etl_municipios_seed.py --all
  python etl/etl_municipios_seed.py --limit 5
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.services.municipio_loader import load_all_pending, upsert_seed_rows

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga municípios prioritários Sinidu+Clima")
    parser.add_argument("--seed-only", action="store_true", help="Apenas popula municipios_seed")
    parser.add_argument("--all", action="store_true", help="Carrega todos pendentes")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        inserted = upsert_seed_rows(db)
        print(f"Seed manifest sincronizado ({inserted} novos registros).")
        if args.seed_only:
            return 0
        limit = None if args.all else (args.limit or 3)
        stats = load_all_pending(db, limit=limit if not args.all else None)
        print(f"Processados: {stats['processados']}, carregados: {stats['carregados']}, parciais: {stats['parciais']}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
