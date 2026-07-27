"""Extrai CSV dos 6 municípios piloto a partir do XLSX oficial MapBiomas Coleção 10.1.

Fonte: https://doi.org/10.58053/MapBiomas/SJZOLT
Arquivo: MAPBIOMAS_BRAZIL-COVERAGE_STATISTICS-COL.10.1-MUNICIPALITIES_STATES_BIOMES.xlsx
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_XLSX = ROOT / "mapbiomas" / (
    "MAPBIOMAS_BRAZIL-COVERAGE_STATISTICS-COL.10.1-MUNICIPALITIES_STATES_BIOMES.xlsx"
)
DEFAULT_OUT = Path(__file__).resolve().parent / "municipios_cobertura_pilotos.csv"

PILOTS = {
    ("pe", "recife"): "2611606",
    ("se", "aracaju"): "2800308",
    ("ba", "salvador"): "2927408",
    ("sp", "sao paulo"): "3550308",
    ("rj", "rio de janeiro"): "3304557",
    ("df", "brasilia"): "5300108",
}
YEARS = [1985, 1995, 2005, 2015, 2020, 2024]


def _norm(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip().replace("'", "")


def _classify(class_level_1: object, class_level_2: object) -> str | None:
    l1 = str(class_level_1 or "").lower()
    l2 = str(class_level_2 or "").lower()
    if "4.2. urban" in l2 or "urban area" in l2:
        return "Área Urbana"
    if l1.startswith("1. forest") or "forest formation" in l2 or "mangrove" in l2:
        return "Vegetação / Floresta"
    if "river, lake and ocean" in l2 or "wetland" in l2:
        return "Corpo d'água"
    return None


def extract(xlsx: Path, out: Path) -> int:
    import pandas as pd

    df = pd.read_excel(xlsx, sheet_name="COVERAGE_10.1", engine="openpyxl")
    year_cols = [y for y in YEARS if y in df.columns]
    rows: list[dict[str, object]] = []

    for (uf, muni_name), group in df.groupby(["state_acronym", "municipality"], dropna=False):
        key = (_norm(uf)[:2], _norm(muni_name))
        code = PILOTS.get(key)
        if not code:
            continue
        for year in year_cols:
            totals: dict[str, float] = {}
            for _, row in group.iterrows():
                classe = _classify(row.get("class_level_1"), row.get("class_level_2"))
                if not classe:
                    continue
                try:
                    val = float(row.get(year))
                except (TypeError, ValueError):
                    continue
                if val <= 0:
                    continue
                totals[classe] = totals.get(classe, 0.0) + val
            for classe, area in totals.items():
                rows.append({
                    "codigo_ibge": code,
                    "ano": year,
                    "classe_uso": classe,
                    "area_ha": round(area, 3),
                })

    if not rows:
        print("Nenhuma linha extraída — verifique o XLSX.", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["codigo_ibge", "ano", "classe_uso", "area_ha"])
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (str(r["codigo_ibge"]), int(r["ano"]), str(r["classe_uso"]))))

    # Espelha no volume local montado pelo docker-compose (sem apagar CSV ampliado)
    volume_dir = ROOT / "mapbiomas"
    if volume_dir.is_dir():
        pilot_copy = volume_dir / "municipios_cobertura_pilotos.csv"
        with pilot_copy.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["codigo_ibge", "ano", "classe_uso", "area_ha"])
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda r: (str(r["codigo_ibge"]), int(r["ano"]), str(r["classe_uso"]))))
        print(f"Também escreveu {pilot_copy}")
        main_csv = volume_dir / "municipios_cobertura.csv"
        if not main_csv.exists():
            with main_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["codigo_ibge", "ano", "classe_uso", "area_ha"])
                writer.writeheader()
                writer.writerows(sorted(rows, key=lambda r: (str(r["codigo_ibge"]), int(r["ano"]), str(r["classe_uso"]))))
            print(f"Semeou {main_csv}")

    print(f"OK: {len(rows)} linhas → {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if not args.xlsx.is_file():
        print(
            f"XLSX não encontrado: {args.xlsx}\n"
            "Baixe em https://doi.org/10.58053/MapBiomas/SJZOLT "
            "(arquivo MUNICIPALITIES_STATES_BIOMES.xlsx) para mapbiomas/",
            file=sys.stderr,
        )
        return 1
    return extract(args.xlsx, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
