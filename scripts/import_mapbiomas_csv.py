#!/usr/bin/env python3
"""Importa CSV oficial MapBiomas para /data/mapbiomas/."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Copia CSV MapBiomas para o volume de dados.")
    parser.add_argument("csv_path", help="Caminho do CSV baixado de brasil.mapbiomas.org/estatisticas")
    parser.add_argument(
        "--dest-dir",
        default="/data/mapbiomas",
        help="Diretório destino no container/host (default: /data/mapbiomas)",
    )
    args = parser.parse_args()

    src = Path(args.csv_path)
    if not src.is_file():
        print(f"Arquivo não encontrado: {src}", file=sys.stderr)
        return 1

    dest_dir = Path(args.dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "municipios_cobertura.csv"
    shutil.copy2(src, dest)
    print(f"CSV copiado para {dest}")
    print("Configure MAPBIOMAS_STATS_CSV=/data/mapbiomas/municipios_cobertura.csv e reinicie o backend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
