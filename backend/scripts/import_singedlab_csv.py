"""Importa export CSV do portal IBGE SINGED Lab para backend/data/singedlab_rs_enchentes_2024.csv."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data_connectors.singedlab_rs_collector import DEFAULT_CSV  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services.singedlab_import_service import (  # noqa: E402
    normalize_ibge_export_file,
    run_singedlab_csv_import,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa CSV exportado do IBGE SINGED Lab")
    parser.add_argument("source_csv", type=Path, help="Arquivo exportado do portal IBGE")
    parser.add_argument("--target", type=Path, default=DEFAULT_CSV, help="CSV seed interno")
    parser.add_argument("--sync-db", action="store_true", help="Sincroniza banco após merge")
    args = parser.parse_args()

    rows = normalize_ibge_export_file(args.source_csv)
    if not rows:
        raise SystemExit("Nenhuma linha reconhecida no CSV de origem.")

    db = SessionLocal() if args.sync_db else None
    try:
        result = run_singedlab_csv_import(
            args.source_csv.read_bytes(),
            filename=args.source_csv.name,
            target_csv=args.target,
            db=db,
        )
    finally:
        if db is not None:
            db.close()

    print(f"Merge concluído: {result['imported_municipios']} municípios RS atualizados em {args.target}")
    if result.get("sync"):
        print("Sync DB:", result["sync"])


if __name__ == "__main__":
    main()
