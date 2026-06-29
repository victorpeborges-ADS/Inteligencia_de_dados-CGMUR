#!/usr/bin/env python3
"""Processamento SRTM OpenTopography → tiles Terrarium para visualização 3D.

Uso:
  python etl/etl_dem_srtm.py --municipio 2611606
  python etl/etl_dem_srtm.py --all
  python etl/etl_dem_srtm.py --limit 5 --force
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.models import Municipio, MunicipioSeed
from app.services.dem_processor import is_processed, process_municipality_dem

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _targets(db, codigo: str | None, all_flag: bool, limit: int | None) -> list[str]:
    if codigo:
        return [codigo]
    if all_flag:
        rows = db.query(MunicipioSeed.codigo_ibge).order_by(MunicipioSeed.prioridade).all()
        codes = [r[0] for r in rows]
    else:
        rows = db.query(Municipio.codigo_ibge).order_by(Municipio.nome).all()
        codes = [r[0] for r in rows]
    if limit:
        codes = codes[:limit]
    return codes


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL SRTM → DEM Terrarium")
    parser.add_argument("--municipio", help="Código IBGE 7 dígitos")
    parser.add_argument("--all", action="store_true", help="Todos os seeds (requer geom no PostGIS)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        codes = _targets(db, args.municipio, args.all, args.limit)
        if not codes:
            logger.error("Nenhum município alvo.")
            sys.exit(1)
        for ibge in codes:
            if is_processed(ibge) and not args.force:
                logger.info("%s — DEM já processado (use --force)", ibge)
                continue
            try:
                meta = process_municipality_dem(db, ibge, force=args.force)
                logger.info(
                    "%s OK — alt %.0f–%.0fm, encosta crítica %.1f%%",
                    ibge,
                    meta["stats"]["altitude_min_m"],
                    meta["stats"]["altitude_max_m"],
                    meta["stats"]["suscetibilidade_alta_pct"],
                )
            except ValueError as exc:
                logger.warning("%s ignorado: %s", ibge, exc)
    finally:
        db.close()


if __name__ == "__main__":
    main()
