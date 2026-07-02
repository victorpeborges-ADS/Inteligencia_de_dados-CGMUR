#!/usr/bin/env python3
"""Inventário de fontes CTM para os 24 municípios abaixo do patamar Salvador/Recife."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data_connectors.ctm_collector import catalog_ctm_targets, probe_ctm_source
from app.data_connectors.ctm_registry import CTM_BY_CODE, CTM_RESEARCH_NOTES, CTM_TARGET_CODES


def main() -> int:
    rows = catalog_ctm_targets()
    by_status: dict[str, list] = {}
    for row in rows:
        by_status.setdefault(row["status"], []).append(row)

    print("RESUMO", {k: len(v) for k, v in sorted(by_status.items())})
    print("TOTAL", len(rows))
    for status in ("disponivel", "insuficiente", "sem_ctm_cadastrada", "intermitente", "erro"):
        grp = by_status.get(status, [])
        if not grp:
            continue
        print(f"\n=== {status.upper()} ({len(grp)}) ===")
        for r in sorted(grp, key=lambda x: (-x.get("feicoes", 0), x.get("nome", ""))):
            extra = f" — {r['feicoes']} feições" if r.get("feicoes") else ""
            nota = r.get("nota") or r.get("erro") or ""
            print(f"{r['codigo_ibge']} {r['nome']} ({r['uf']}){extra} | {nota}")

    out = Path("/tmp/catalogo_ctm_municipios.json")
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
