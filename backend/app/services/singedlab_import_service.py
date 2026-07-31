"""Importação curada do export CSV do portal IBGE SINGED Lab."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.data_connectors.constants import TARGET_IBGE_CODES
from app.data_connectors.singedlab_rs_collector import DEFAULT_CSV, sync_singedlab_batch

COLUMN_ALIASES = {
    "codigo_ibge": ("codigo_ibge", "cod_municipio", "cd_mun", "ibge"),
    "populacao_area_afetada": ("populacao_area_afetada", "populacao", "pop_residente", "total_pessoas"),
    "domicilios_area_afetada": ("domicilios_area_afetada", "domicilios", "total_domicilios"),
    "estabelecimentos_area_afetada": ("estabelecimentos_area_afetada", "estabelecimentos", "total_estabelecimentos"),
    "pct_populacao_municipio": ("pct_populacao_municipio", "pct_pop", "percentual_populacao"),
    "pct_area_municipio": ("pct_area_municipio", "pct_area", "percentual_area"),
}

SEED_FIELDNAMES = [
    "codigo_ibge",
    "escopo",
    "populacao_area_afetada",
    "domicilios_area_afetada",
    "estabelecimentos_area_afetada",
    "pct_populacao_municipio",
    "pct_area_municipio",
    "data_quality",
    "fonte_ref",
]


def _pick(row: dict[str, str], aliases: tuple[str, ...]) -> str:
    lowered = {k.lower().strip(): v for k, v in row.items()}
    for alias in aliases:
        if alias in lowered and str(lowered[alias]).strip():
            return str(lowered[alias]).strip()
    return ""


def normalize_ibge_export_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for raw in rows:
        codigo = _pick(raw, COLUMN_ALIASES["codigo_ibge"])
        if not codigo:
            continue
        codigo = codigo.zfill(7)[-7:]
        normalized.append({
            "codigo_ibge": codigo,
            "escopo": "aplicavel",
            "populacao_area_afetada": _pick(raw, COLUMN_ALIASES["populacao_area_afetada"]),
            "domicilios_area_afetada": _pick(raw, COLUMN_ALIASES["domicilios_area_afetada"]),
            "estabelecimentos_area_afetada": _pick(raw, COLUMN_ALIASES["estabelecimentos_area_afetada"]),
            "pct_populacao_municipio": _pick(raw, COLUMN_ALIASES["pct_populacao_municipio"]),
            "pct_area_municipio": _pick(raw, COLUMN_ALIASES["pct_area_municipio"]),
            "data_quality": "oficial",
            "fonte_ref": "",
        })
    return normalized


def normalize_ibge_export_file(source: Path) -> list[dict[str, str]]:
    with source.open(encoding="utf-8-sig", newline="") as handle:
        return normalize_ibge_export_rows(list(csv.DictReader(handle)))


def normalize_ibge_export_bytes(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig")
    return normalize_ibge_export_rows(list(csv.DictReader(io.StringIO(text))))


def merge_into_seed(
    import_rows: list[dict[str, str]],
    target: Path,
    *,
    source_label: str,
) -> int:
    existing: dict[str, dict[str, str]] = {}
    if target.exists():
        with target.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                existing[row["codigo_ibge"]] = row

    for row in import_rows:
        row = {**row, "fonte_ref": row.get("fonte_ref") or f"Importado de {source_label}"}
        existing[row["codigo_ibge"]] = row

    for codigo in TARGET_IBGE_CODES:
        existing.setdefault(codigo, {
            "codigo_ibge": codigo,
            "escopo": "nao_aplicavel",
            "data_quality": "nao_aplicavel",
            "fonte_ref": "Produto pontual RS 2024 — fora do escopo geográfico",
        })

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SEED_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for codigo in TARGET_IBGE_CODES:
            writer.writerow(existing[codigo])
    return len(import_rows)


def run_singedlab_csv_import(
    content: bytes,
    *,
    filename: str,
    target_csv: Path | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    rows = normalize_ibge_export_bytes(content)
    if not rows:
        raise ValueError("Nenhuma linha reconhecida no CSV de origem.")

    target = target_csv or DEFAULT_CSV
    merged = merge_into_seed(rows, target, source_label=filename)
    result: dict[str, Any] = {
        "filename": filename,
        "imported_municipios": merged,
        "codigos_ibge": [row["codigo_ibge"] for row in rows],
        "target_csv": str(target),
    }
    if db is not None:
        result["sync"] = sync_singedlab_batch(db, force=True, csv_path=target)
    return result
