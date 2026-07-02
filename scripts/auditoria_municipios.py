#!/usr/bin/env python3
"""Auditoria completa dos 60 municípios (exceto Recife piloto).

Uso:
  python3 scripts/auditoria_municipios.py
  python3 scripts/auditoria_municipios.py --persist
  python3 scripts/auditoria_municipios.py --output relatorios/auditoria.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import SessionLocal  # noqa: E402
from app.services.municipio_audit_service import audit_all_municipios  # noqa: E402

CSV_FIELDS = [
    "codigo_ibge",
    "nome",
    "uf",
    "flag_malha",
    "malha_fonte",
    "bairros_total",
    "bairros_validos",
    "flag_socio",
    "setores_total",
    "setores_reais",
    "flag_seg",
    "seg_registros",
    "seg_fonte",
    "flag_score",
    "campos_reais_pct",
    "score_sinidu",
    "score_confiabilidade",
    "confiabilidade_geral",
    "auditado_em",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoria de dados municipais Sinidu+Clima")
    parser.add_argument("--persist", action="store_true", help="Grava flags em municipios_seed")
    parser.add_argument(
        "--output",
        default=str(ROOT / f"auditoria_municipios_{date.today().isoformat()}.csv"),
        help="Caminho do CSV de saída",
    )
    parser.add_argument("--include-recife", action="store_true", help="Incluir Recife na auditoria")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = audit_all_municipios(
            db,
            exclude_recife=not args.include_recife,
            persist=args.persist,
        )
    finally:
        db.close()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    by_conf = {}
    for r in rows:
        by_conf[r["confiabilidade_geral"]] = by_conf.get(r["confiabilidade_geral"], 0) + 1

    alta_media = by_conf.get("ALTA", 0) + by_conf.get("MEDIA", 0)
    print(f"Auditoria concluída — {len(rows)} municípios")
    print(f"CSV: {out_path}")
    print(f"ALTA+MEDIA: {alta_media}/{len(rows)}")
    for level in ("ALTA", "MEDIA", "BAIXA", "CRITICA"):
        print(f"  {level}: {by_conf.get(level, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
