#!/usr/bin/env python3
"""Sonda todas as fontes CTM cadastradas + alvos pendentes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data_connectors.ctm_collector import catalog_ctm_targets


def main() -> int:
    rows = catalog_ctm_targets()
    for row in sorted(rows, key=lambda r: (r.get("status", ""), r.get("nome", ""))):
        code = row["codigo_ibge"]
        feicoes = row.get("feicoes", 0)
        extra = f" ({feicoes} feições)" if feicoes else ""
        print(f"{code} {row['nome']} [{row['status']}]{extra} — {row.get('nota') or row.get('erro', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
