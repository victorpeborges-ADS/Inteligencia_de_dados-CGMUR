#!/usr/bin/env python3
"""Validação dos municípios piloto de boot — Recife e Aracaju."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validacao_recife_ui import validate_municipio

PILOTOS = [
    ("2611606", "Recife/PE"),
    ("2800308", "Aracaju/SE"),
]


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    print(f"=== Validação piloto demo — {base} ===\n")
    total = 0
    for ibge, label in PILOTOS:
        total += validate_municipio(base, ibge, label)
    print(f"Resultado total: {total} falha(s) em {len(PILOTOS)} municípios")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
