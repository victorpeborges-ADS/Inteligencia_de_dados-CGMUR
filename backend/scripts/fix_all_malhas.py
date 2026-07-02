#!/usr/bin/env python3
"""Reimporta malha IBGE oficial para todos os municípios seed (corrige geometrias)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data_connectors.official_bairros_collector import import_official_ibge_mesh
from app.db import SessionLocal
from app.models import Bairro, Municipio, MunicipioSeed, SetorCensitario
from app.services.malha_ibge_service import enriquecer_socioeconomico_censo
from sqlalchemy import func, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _coverage(db, muni) -> tuple[int, int, float, float]:
    b = db.query(Bairro).filter(Bairro.municipio_id == muni.id).count()
    s = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == muni.id).count()
    marea = float(db.scalar(func.ST_Area(muni.geom)) or 0)
    barea = float(
        db.scalar(text("SELECT COALESCE(ST_Area(ST_Union(geom)),0) FROM bairros WHERE municipio_id=:mid"), {"mid": muni.id})
        or 0
    )
    sarea = float(
        db.scalar(text("SELECT COALESCE(ST_Area(ST_Union(geom)),0) FROM setores_censitarios WHERE municipio_id=:mid"), {"mid": muni.id})
        or 0
    )
    return b, s, (barea / marea if marea else 0), (sarea / marea if marea else 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codigo", action="append", help="Código IBGE (repetível)")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--socio", action="store_true", help="Enriquecer socio após malha")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.codigo:
            codes = [c.zfill(7)[:7] for c in args.codigo]
        else:
            codes = [s[0] for s in db.query(MunicipioSeed.codigo_ibge).all()]

        ok = err = 0
        for code in codes:
            muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
            if not muni:
                logger.warning("Município %s ausente", code)
                err += 1
                continue
            result = import_official_ibge_mesh(db, muni, force=True)
            if result.get("error"):
                logger.error("%s — %s", muni.nome, result["error"])
                err += 1
                continue
            if args.socio:
                import asyncio

                asyncio.run(enriquecer_socioeconomico_censo(code, db))
            b, s, rb, rs = _coverage(db, muni)
            logger.info("%s — bairros=%d setores=%d cov_b=%.2f cov_s=%.2f", muni.nome, b, s, rb, rs)
            ok += 1
        logger.info("Concluído: %d ok, %d erro", ok, err)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
