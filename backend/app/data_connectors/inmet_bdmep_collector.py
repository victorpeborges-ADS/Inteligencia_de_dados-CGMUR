"""Coletor INMET / BDMEP de precipitação (Fase 21b.3).

A API BDMEP exige cadastro (gratuito). Enquanto o token não estiver no ambiente,
aceita CSVs exportados do portal BDMEP depositados em INMET_BDMEP_DIR e grava
em serie_pluviometrica_observada (fonte=inmet, qualidade=oficial).

Formato esperado (separador ; ou ,): colunas tipicas
  DC_NOME / Estacao, CD_ESTACAO, DT_MEDICAO / Data, CHUVA / PRECIPITACAO, VL_LATITUDE, VL_LONGITUDE
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import Municipio
from app.services.pluvio_series_service import upsert_pluvio_rows
from app.timeutil import utc_now

logger = logging.getLogger(__name__)

DEFAULT_DIR = Path(os.getenv("INMET_BDMEP_DIR", "/data/inmet_bdmep"))

PILOT_IBGE = (
    "2611606",
    "2800308",
    "2927408",
    "3304557",
    "3550308",
    "5300108",
)


def _norm(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (h or "").strip().lower())


def _pick(row: dict[str, str], *candidates: str) -> str | None:
    norms = {_norm(k): v for k, v in row.items()}
    for c in candidates:
        if c in norms and norms[c] not in (None, ""):
            return norms[c]
    return None


def _parse_ts(raw: str) -> dt.datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ):
        try:
            return dt.datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    try:
        return dt.datetime.fromisoformat(text.replace("Z", ""))
    except ValueError:
        return None


def _to_float(val: Any) -> float | None:
    if val is None or val == "" or val in {"-", "null", "None"}:
        return None
    try:
        return float(str(val).replace(",", "."))
    except ValueError:
        return None


def parse_inmet_bdmep_csv(path: Path, codigo_ibge: str) -> list[dict[str, Any]]:
    """Parseia CSV BDMEP/INMET depositado → linhas de serie_pluviometrica_observada."""
    code = str(codigo_ibge).zfill(7)[:7]
    rows_out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        now = utc_now()
        for raw in reader:
            if not raw:
                continue
            estacao = _pick(
                raw,
                "cdestacao",
                "codigoestacao",
                "estacao",
                "cod",
                "station",
                "id",
            )
            ts_raw = _pick(
                raw,
                "dtmedicao",
                "data",
                "datamedicao",
                "datetime",
                "datahora",
                "hora",
                "timestamp",
            )
            val_raw = _pick(
                raw,
                "chuva",
                "precipitacao",
                "precipitacaototal",
                "precip",
                "mm",
                "precipitation",
                "valor",
            )
            if not estacao or val_raw is None:
                continue
            ts = _parse_ts(ts_raw or "")
            if ts is None:
                continue
            precip = _to_float(val_raw)
            if precip is None:
                continue
            lat_s = _pick(raw, "vllatitude", "latitude", "lat")
            lng_s = _pick(raw, "vllongitude", "longitude", "lng", "lon", "long")
            nome = _pick(raw, "dcnome", "nome", "estacaonome", "name")
            # Heurística: se só tem data (sem hora) → diária; senão horária
            gran = "diaria" if len((ts_raw or "").strip()) <= 10 else "horaria"
            rows_out.append({
                "codigo_ibge": code,
                "municipio_id": None,
                "estacao_id": str(estacao).strip()[:64],
                "estacao_nome": (nome or f"INMET {estacao}")[:120],
                "lat": float(lat_s.replace(",", ".")) if lat_s else None,
                "lng": float(lng_s.replace(",", ".")) if lng_s else None,
                "observed_at": ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts,
                "precip_mm": precip,
                "granularidade": gran,
                "data_quality": "oficial",
                "fonte": "inmet",
                "ingestido_em": now,
                "raw_payload": {"arquivo": path.name, "origem": "bdmep_csv"},
            })
    return rows_out


def list_inmet_files(codigo_ibge: str | None = None, directory: Path | None = None) -> list[Path]:
    root = Path(directory or DEFAULT_DIR)
    if not root.exists():
        return []
    files = sorted(root.glob("*.csv")) + sorted(root.glob("*.CSV"))
    if codigo_ibge:
        code = str(codigo_ibge).zfill(7)[:7]
        files = [f for f in files if code in f.name or f.name.lower().startswith(code)]
    return files


def collect_inmet_bdmep_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    directory: Path | None = None,
) -> dict[str, Any]:
    """Ingere CSVs BDMEP depositados para um município."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    files = list_inmet_files(code, directory)
    if not files:
        files = list_inmet_files(None, directory)

    total = 0
    used: list[str] = []
    for path in files:
        parsed = parse_inmet_bdmep_csv(path, code)
        if muni:
            for r in parsed:
                r["municipio_id"] = muni.id
        if parsed:
            total += upsert_pluvio_rows(db, parsed)
            used.append(path.name)

    return {
        "codigo_ibge": code,
        "skipped": total == 0,
        "records": total,
        "arquivos": used,
        "data_quality": "oficial" if total else None,
        "fonte": "inmet",
        "hint": (
            None
            if total
            else (
                "Sem CSV em "
                f"{directory or DEFAULT_DIR}. Exporte séries BDMEP "
                "(portal INMET, cadastro gratuito) e deposite o arquivo."
            )
        ),
    }


def collect_inmet_bdmep_pilots(db: Session) -> dict[str, Any]:
    results = [collect_inmet_bdmep_municipality(db, code) for code in PILOT_IBGE]
    return {
        "pilotos": results,
        "records": sum(int(r.get("records") or 0) for r in results),
    }
