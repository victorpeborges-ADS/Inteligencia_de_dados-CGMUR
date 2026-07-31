#!/usr/bin/env python3
"""Gera LOD2-lite do centro do Recife (bbox Recife Antigo / Marco Zero).

Uso (no container backend ou com DATABASE_URL local):
  python scripts/build_lod2_recife_centro.py
  python scripts/build_lod2_recife_centro.py --force
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal  # noqa: E402
from app.services.building_lod2_mesh_service import (  # noqa: E402
    DEFAULT_BBOX_RECIFE,
    build_lod2_for_bbox,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LOD2-lite Recife centro")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--ibge", default="2611606")
    args = parser.parse_args()
    west, south, east, north = DEFAULT_BBOX_RECIFE
    db = SessionLocal()
    try:
        out = build_lod2_for_bbox(
            db,
            args.ibge,
            west=west,
            south=south,
            east=east,
            north=north,
            limit=args.limit,
            force=args.force,
            ensure_buildings=True,
        )
    finally:
        db.close()
    print(out.get("status"), out.get("edificios"), out.get("tileset_url") or out.get("aviso"))
    return 0 if out.get("status") in {"ok", "cached", "vazio"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
