#!/usr/bin/env python3
"""Importa malha CTM dos municípios com fonte cadastrada no registry."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data_connectors.ctm_collector import collect_ctm_batch, collect_ctm_municipality
from app.data_connectors.ctm_registry import CTM_BY_CODE, CTM_TARGET_CODES
from app.db import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser(description="Importação batch de malha CTM municipal")
    parser.add_argument("--codigo", action="append", help="Código IBGE (repita para vários)")
    parser.add_argument("--all", action="store_true", help="Todos com fonte CTM cadastrada")
    parser.add_argument("--targets", action="store_true", help="Todos os 24 alvos com fonte no registry")
    parser.add_argument("--force", action="store_true", help="Sobrescrever malha densa existente")
    args = parser.parse_args()

    if args.codigo:
        codes = args.codigo
    elif args.all or args.targets:
        codes = [c for c in CTM_TARGET_CODES if c in CTM_BY_CODE]
    else:
        codes = list(CTM_BY_CODE.keys())

    db = SessionLocal()
    try:
        if len(codes) == 1:
            res = collect_ctm_municipality(db, codes[0], force=args.force)
            print(res)
            return 0 if not res.get("error") else 1

        summary = collect_ctm_batch(db, codigos=codes, force=args.force)
        print(f"Concluído: {summary['ok']} ok, {summary['erro']} erro, {summary['pulados']} pulados")
        for item in summary["detalhes"]:
            code = item.get("codigo_ibge")
            if item.get("error"):
                print(f"  ERRO {code}: {item['error']}")
            elif item.get("skipped"):
                print(f"  SKIP {code}: {item.get('motivo', 'skipped')}")
            else:
                print(f"  OK   {code}: {item.get('bairros')} bairros CTM")
        return 0 if summary["erro"] == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
