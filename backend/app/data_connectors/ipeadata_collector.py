"""Coletor Ipeadata — IDHM municipal (Atlas do Desenvolvimento Humano).

Fonte: http://www.ipeadata.gov.br/api/odata4/
Série ADH_IDHM — último valor disponível por município (Censo 2010, referência PNUD/IPEA).
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.data_connectors.base import fetch_json

logger = logging.getLogger(__name__)

IPEADATA_BASE = "http://www.ipeadata.gov.br/api/odata4"
IDHM_SERIES = "ADH_IDHM"
DEFAULT_IDHM_CSV = Path(__file__).resolve().parents[2] / "data" / "idhm_municipios_prioritarios.csv"


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    try:
        return float(cleaned.replace(",", "."))
    except ValueError:
        return None


def load_idhm_csv(csv_path: Path | None = None) -> dict[str, dict[str, Any]]:
    path = csv_path or DEFAULT_IDHM_CSV
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            code = str(row.get("codigo_ibge", "")).zfill(7)[-7:]
            if not code:
                continue
            rows[code] = row
    return rows


def fetch_idhm_live(codigo_ibge: str) -> tuple[float | None, int | None]:
    """Busca IDHM no Ipeadata paginando a série até encontrar o município."""
    codigo = str(codigo_ibge).zfill(7)[-7:]
    cache_key = f"ipeadata:idhm:{codigo}"
    skip = 0
    page = 5000
    best_val: float | None = None
    best_year: int | None = None

    while skip <= 20000:
        url = f"{IPEADATA_BASE}/ValoresSerie(SERCODIGO='{IDHM_SERIES}')"
        params = {"$skip": skip, "$top": page}
        try:
            payload = fetch_json(url, params=params, cache_key=f"{cache_key}:skip:{skip}", cache_ttl=86400 * 7)
        except Exception as exc:
            logger.warning("Ipeadata IDHM falhou (%s): %s", codigo, exc)
            break
        rows = payload if isinstance(payload, list) else payload.get("value", [])
        if not rows:
            break
        for row in rows:
            if str(row.get("TERCODIGO", "")).zfill(7)[-7:] != codigo:
                continue
            year = int(str(row.get("VALDATA", ""))[:4])
            val = float(row["VALVALOR"])
            if best_year is None or year >= best_year:
                best_val = val
                best_year = year
        if best_val is not None:
            return best_val, best_year
        if len(rows) < page:
            break
        skip += page
    return None, None


def collect_idhm_municipality(codigo_ibge: str, *, csv_path: Path | None = None) -> dict[str, Any]:
    codigo = str(codigo_ibge).zfill(7)[-7:]
    csv_rows = load_idhm_csv(csv_path)
    row = csv_rows.get(codigo)

    idh = _parse_float(row.get("idh") if row else None)
    idh_ano = int(row["idh_ano"]) if row and str(row.get("idh_ano", "")).isdigit() else None
    fonte = (row or {}).get("fonte") or "Atlas DH / Ipeadata"

    if idh is None:
        idh, idh_ano = fetch_idhm_live(codigo)
        if idh is not None:
            fonte = "Ipeadata ADH_IDHM (consulta ao vivo)"

    return {
        "idh": idh,
        "idh_ano": idh_ano,
        "idh_fonte": fonte if idh is not None else None,
        "idh_qualidade": "oficial" if idh is not None else "ausente",
        "atualizado_em": datetime.now(timezone.utc),
    }
