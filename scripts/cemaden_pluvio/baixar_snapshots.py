#!/usr/bin/env python3
"""Baixa snapshots CEMADEN (getJson2) dos 6 municípios-piloto → CSV local.

Uso:
  python3 scripts/cemaden_pluvio/baixar_snapshots.py

Não exige captcha. Série histórica mensal do Mapa Interativo continua manual.
"""

from __future__ import annotations

import csv
import json
import sys
import urllib.request
from pathlib import Path

PILOTS = {
    "2611606": "PE",
    "2800308": "SE",
    "2927408": "BA",
    "3304557": "RJ",
    "3550308": "SP",
    "5300108": "DF",
}

URL = "https://resources.cemaden.gov.br/graficos/interativo/getJson2.php"
FIELDS = [
    "idestacao", "uf", "codibge", "cidade", "nomeestacao", "ultimovalor",
    "datahoraUltimovalor", "acc1hr", "acc3hr", "acc6hr", "acc12hr",
    "acc24hr", "acc48hr", "acc72hr", "acc96hr", "tipoestacao", "status",
]


def fetch_uf(uf: str) -> list[dict]:
    req = urllib.request.Request(
        f"{URL}?uf={uf}",
        headers={"User-Agent": "Mozilla/5.0 (compatible; Sinidu/1.0)", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def main() -> int:
    out = Path(__file__).resolve().parent / "downloads"
    out.mkdir(parents=True, exist_ok=True)
    for ibge, uf in PILOTS.items():
        print(f"Baixando {uf} ({ibge})…", flush=True)
        data = fetch_uf(uf)
        muni = [r for r in data if str(r.get("codibge", "")).zfill(7) == ibge]
        write_csv(out / f"{ibge}_snapshot.csv", muni)
        write_csv(out / f"cemaden_{uf}_all.csv", data)
        (out / f"cemaden_{uf}_raw.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  {len(muni)} estações municipais / {len(data)} na UF")
    print(f"OK → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
