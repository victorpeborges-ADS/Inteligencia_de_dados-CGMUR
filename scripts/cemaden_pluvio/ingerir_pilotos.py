#!/usr/bin/env python3
"""Ingere snapshots CEMADEN dos 6 pilotos no PostGIS.

Requer backend com DATABASE_URL acessível (Docker no ar).

  # de dentro do container:
  python /app/../scripts/...  # ou:
  docker compose exec backend python -c "..."

  # local com PYTHONPATH:
  cd backend && PYTHONPATH=. python ../scripts/cemaden_pluvio/ingerir_pilotos.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def main() -> int:
    from app.db import SessionLocal
    from app.data_connectors.cemaden_pluvio_collector import collect_cemaden_pluvio_pilots

    db = SessionLocal()
    try:
        out = collect_cemaden_pluvio_pilots(db)
        print(out)
        total = int(out.get("total_records") or 0)
        print(f"OK — {total} registros em serie_pluviometrica_observada")
        return 0 if total >= 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
