#!/usr/bin/env python3
"""Revisão do grau de detalhamento da camada de bairros por município."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, text

from app.data_connectors.official_bairros_collector import is_official_ibge_mesh
from app.data_connectors.territorial_mesh_collector import GENERIC_BAIRRO_NAMES
from app.db import SessionLocal
from app.models import Bairro, Municipio, MunicipioSeed, SetorCensitario


def classify(db, muni: Municipio) -> dict:
    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    bcount = len(bairros)
    scount = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == muni.id).count()
    names = {b.nome for b in bairros}
    fontes = sorted({b.fonte_malha for b in bairros if b.fonte_malha})
    official = is_official_ibge_mesh(db, muni)
    is_voronoi = bool(names) and names <= GENERIC_BAIRRO_NAMES
    is_recife_ctm = muni.codigo_ibge == "2611606" and bcount >= 85

    marea = float(db.scalar(func.ST_Area(muni.geom)) or 0)
    barea = float(
        db.scalar(text("SELECT COALESCE(ST_Area(ST_Union(geom)),0) FROM bairros WHERE municipio_id=:mid"), {"mid": muni.id})
        or 0
    )

    if is_recife_ctm or (official and bcount >= 30):
        nivel = "SALVADOR_RECIFE"  # detalhe alto — plotagem densa de bairros
    elif official and bcount >= 8:
        nivel = "MEDIA"
    elif official and bcount >= 1:
        nivel = "BAIXA"
    elif is_voronoi or bcount <= 6:
        nivel = "VORONOI"
    else:
        nivel = "OUTROS"

    return {
        "codigo": muni.codigo_ibge,
        "nome": muni.nome,
        "uf": muni.uf,
        "bairros": bcount,
        "setores": scount,
        "nivel": nivel,
        "fontes": fontes,
        "cov_b": round(barea / marea, 3) if marea else 0,
    }


def main() -> int:
    db = SessionLocal()
    rows: list[dict] = []
    try:
        codes = [s[0] for s in db.query(MunicipioSeed.codigo_ibge).all()]
        for code in sorted(set(codes + ["2611606"])):
            muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
            if muni:
                rows.append(classify(db, muni))

        counts = Counter(r["nivel"] for r in rows)
        print("RESUMO", dict(counts))
        print("TOTAL", len(rows))
        for nivel in ("SALVADOR_RECIFE", "MEDIA", "BAIXA", "VORONOI", "OUTROS"):
            grp = [r for r in rows if r["nivel"] == nivel]
            if not grp:
                continue
            print(f"\n=== {nivel} ({len(grp)}) ===")
            for r in sorted(grp, key=lambda x: (-x["bairros"], x["nome"])):
                print(
                    f"{r['codigo']} {r['nome']} ({r['uf']}) — "
                    f"{r['bairros']} bairros, {r['setores']} setores, cov={r['cov_b']}"
                )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
