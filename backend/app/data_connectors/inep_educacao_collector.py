"""Coletor INEP Censo Escolar — escolas com matrículas por etapa e coordenadas."""

from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import EscolaInep, Municipio

logger = logging.getLogger(__name__)

CENSO_ANO_DEFAULT = 2023
CENSO_FONTE = "inep_censo_escolar"
DEFAULT_SEED = Path(__file__).resolve().parents[2] / "data" / "inep_escolas_seed.csv"
MICRODADOS_CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "inep" / "microdados_ed_basica_2023.csv"

DEPENDENCIA_MAP = {
    "1": "federal",
    "2": "estadual",
    "3": "municipal",
    "4": "privada",
    "federal": "federal",
    "estadual": "estadual",
    "municipal": "municipal",
    "privada": "privada",
}

ETAPAS_VALIDAS = ("todas", "infantil", "fundamental", "medio")


def _parse_int(value: str | None) -> int:
    if value is None:
        return 0
    cleaned = str(value).strip().replace(",", ".")
    if not cleaned:
        return 0
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_dependencia(value: str | None) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    return DEPENDENCIA_MAP.get(key) or DEPENDENCIA_MAP.get(str(value).strip())


def _row_matriculas(row: dict[str, str]) -> dict[str, int]:
    infantil = _parse_int(
        row.get("matriculas_infantil")
        or row.get("qt_mat_inf")
        or row.get("qt_mat_inf_int")
    )
    fundamental = _parse_int(
        row.get("matriculas_fundamental")
        or row.get("qt_mat_fund")
        or row.get("qt_mat_fund_reg")
    )
    medio = _parse_int(row.get("matriculas_medio") or row.get("qt_mat_med"))
    total = _parse_int(row.get("matriculas_total") or row.get("qt_mat_bas"))
    if total <= 0:
        total = infantil + fundamental + medio
    return {
        "matriculas_total": total,
        "matriculas_infantil": infantil,
        "matriculas_fundamental": fundamental,
        "matriculas_medio": medio,
    }


def load_seed_rows(codigo_ibge: str | None = None) -> list[dict[str, Any]]:
    if not DEFAULT_SEED.exists():
        return []
    code = str(codigo_ibge).strip().zfill(7)[:7] if codigo_ibge else None
    rows: list[dict[str, Any]] = []
    with DEFAULT_SEED.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if code and row.get("codigo_ibge", "").strip().zfill(7)[:7] != code:
                continue
            mats = _row_matriculas(row)
            lat = _parse_float(row.get("latitude") or row.get("nu_latitude"))
            lng = _parse_float(row.get("longitude") or row.get("nu_longitude"))
            if lat is None or lng is None:
                continue
            rows.append({
                "codigo_ibge": row["codigo_ibge"].strip().zfill(7)[:7],
                "codigo_inep": row["codigo_inep"].strip(),
                "nome": row["nome"].strip(),
                "dependencia": _normalize_dependencia(row.get("dependencia")),
                "localizacao": (row.get("localizacao") or "urbana").strip().lower(),
                "ano": _parse_int(row.get("ano")) or CENSO_ANO_DEFAULT,
                **mats,
                "latitude": lat,
                "longitude": lng,
                "data_quality": "oficial",
            })
    return rows


def _normalize_microdados_header(name: str) -> str:
    return (
        name.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def load_microdados_rows(codigo_ibge: str, cache_path: Path | None = None) -> list[dict[str, Any]]:
    path = cache_path or MICRODADOS_CACHE
    if not path.exists():
        return []

    code = str(codigo_ibge).strip().zfill(7)[:7]
    rows: list[dict[str, Any]] = []
    with path.open(encoding="latin-1", errors="replace") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        if not reader.fieldnames:
            fh.seek(0)
            reader = csv.DictReader(fh, delimiter="|")
        field_map = {_normalize_microdados_header(k): k for k in (reader.fieldnames or [])}

        def get_val(raw: dict[str, str], *keys: str) -> str | None:
            for key in keys:
                col = field_map.get(key)
                if col and raw.get(col) not in (None, ""):
                    return raw.get(col)
            return None

        for raw in reader:
            muni = get_val(raw, "co_municipio")
            if not muni or str(muni).strip().zfill(7)[:7] != code:
                continue
            lat = _parse_float(get_val(raw, "nu_latitude", "latitude"))
            lng = _parse_float(get_val(raw, "nu_longitude", "longitude"))
            if lat is None or lng is None:
                continue
            row = {
                "codigo_ibge": code,
                "codigo_inep": str(get_val(raw, "co_entidade") or "").strip(),
                "nome": str(get_val(raw, "no_entidade") or "Escola").strip(),
                "dependencia": _normalize_dependencia(get_val(raw, "tp_dependencia")),
                "localizacao": "rural" if get_val(raw, "tp_localizacao") == "2" else "urbana",
                "ano": CENSO_ANO_DEFAULT,
                "latitude": lat,
                "longitude": lng,
                "data_quality": "oficial",
            }
            row.update(_row_matriculas({
                "qt_mat_inf": get_val(raw, "qt_mat_inf", "qt_mat_inf_int", "qt_mat_inf_cre"),
                "qt_mat_fund": get_val(raw, "qt_mat_fund", "qt_mat_fund_reg"),
                "qt_mat_med": get_val(raw, "qt_mat_med"),
                "qt_mat_bas": get_val(raw, "qt_mat_bas"),
            }))
            if row["codigo_inep"] and row["matriculas_total"] > 0:
                rows.append(row)
    return rows


def fetch_school_rows(codigo_ibge: str) -> list[dict[str, Any]]:
    micro = load_microdados_rows(codigo_ibge)
    if micro:
        return micro
    return load_seed_rows(codigo_ibge)


def upsert_escolas(db: Session, muni: Municipio, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    now = datetime.now(timezone.utc)
    updated = 0
    for row in rows:
        codigo_inep = row["codigo_inep"]
        ano = int(row.get("ano") or CENSO_ANO_DEFAULT)
        existing = (
            db.query(EscolaInep)
            .filter(
                EscolaInep.municipio_id == muni.id,
                EscolaInep.codigo_inep == codigo_inep,
                EscolaInep.ano == ano,
            )
            .first()
        )
        lat = row["latitude"]
        lng = row["longitude"]
        payload = {
            "nome": row["nome"],
            "dependencia": row.get("dependencia"),
            "localizacao": row.get("localizacao") or "urbana",
            "matriculas_total": row.get("matriculas_total", 0),
            "matriculas_infantil": row.get("matriculas_infantil", 0),
            "matriculas_fundamental": row.get("matriculas_fundamental", 0),
            "matriculas_medio": row.get("matriculas_medio", 0),
            "fonte": CENSO_FONTE,
            "data_quality": row.get("data_quality") or "oficial",
            "atualizado_em": now,
            "geom": func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326),
        }
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            db.add(EscolaInep(
                municipio_id=muni.id,
                codigo_inep=codigo_inep,
                ano=ano,
                **payload,
            ))
        updated += 1
    db.flush()
    return updated


def sync_educacao_municipio(db: Session, muni: Municipio) -> dict[str, Any]:
    rows = fetch_school_rows(muni.codigo_ibge)
    count = upsert_escolas(db, muni, rows)
    return {
        "codigo_ibge": muni.codigo_ibge,
        "escolas_atualizadas": count,
        "fonte": CENSO_FONTE,
        "ano": CENSO_ANO_DEFAULT,
        "disponivel": count > 0,
    }


def matriculas_por_etapa(escola: EscolaInep, etapa: str) -> int:
    if etapa == "infantil":
        return int(escola.matriculas_infantil or 0)
    if etapa == "fundamental":
        return int(escola.matriculas_fundamental or 0)
    if etapa == "medio":
        return int(escola.matriculas_medio or 0)
    return int(escola.matriculas_total or 0)


def etapa_dominante(escola: EscolaInep) -> str:
    counts = {
        "infantil": int(escola.matriculas_infantil or 0),
        "fundamental": int(escola.matriculas_fundamental or 0),
        "medio": int(escola.matriculas_medio or 0),
    }
    best = max(counts, key=counts.get)
    if counts[best] <= 0:
        return "todas"
    return best
