"""Coletor CEMADEN de pluviômetros (Fase 21b.1).

Fonte programática (sem captcha):
  https://resources.cemaden.gov.br/graficos/interativo/getJson2.php?uf=XX

Retorna acumulados ao vivo por estação (acc1hr…acc96hr + ultimovalor).
O download histórico mensal do Mapa Interativo ainda exige captcha/e-mail —
CSVs depositados em CEMADEN_PLUVIO_DIR continuam sendo aceitos.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import Municipio
from app.services.pluvio_series_service import (
    materialize_cemaden_daily_from_snapshots,
    upsert_pluvio_rows,
)
from app.timeutil import utc_now

logger = logging.getLogger(__name__)

DEFAULT_DIR = Path(os.getenv("CEMADEN_PLUVIO_DIR", "/data/cemaden_pluvio"))
CEMADEN_JSON_URL = "https://resources.cemaden.gov.br/graficos/interativo/getJson2.php"

# IBGE piloto → UF
PILOT_UF_BY_IBGE: dict[str, str] = {
    "2611606": "PE",  # Recife
    "2800308": "SE",  # Aracaju
    "2927408": "BA",  # Salvador
    "3304557": "RJ",  # Rio de Janeiro
    "3550308": "SP",  # São Paulo
    "5300108": "DF",  # Brasília
}


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
        "%d/%m/%y %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
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
    if val is None or val == "" or val == "-":
        return None
    try:
        return float(str(val).replace(",", "."))
    except ValueError:
        return None


def fetch_cemaden_uf_json(uf: str) -> list[dict[str, Any]]:
    """Baixa snapshot JSON oficial do CEMADEN para uma UF."""
    uf = uf.strip().upper()[:2]
    with httpx.Client(timeout=90.0, verify=True) as client:
        resp = client.get(
            CEMADEN_JSON_URL,
            params={"uf": uf},
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; Sinidu/1.0)",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, list):
        raise ValueError(f"Resposta CEMADEN inesperada para UF {uf}")
    return data


def json_stations_to_rows(
    stations: list[dict[str, Any]],
    codigo_ibge: str,
    *,
    municipio_id: int | None = None,
) -> list[dict[str, Any]]:
    """Converte snapshot getJson2 em linhas de serie_pluviometrica_observada."""
    code = str(codigo_ibge).zfill(7)[:7]
    now = utc_now()
    rows: list[dict[str, Any]] = []
    for st in stations:
        if str(st.get("codibge", "")).zfill(7) != code:
            continue
        estacao = str(st.get("idestacao") or "").strip()
        if not estacao:
            continue
        ts = _parse_ts(str(st.get("datahoraUltimovalor") or "")) or now.replace(tzinfo=None)
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.replace(tzinfo=None)

        # Preferência: acc24h → acc48h → acc72h → último valor 10 min
        precip = None
        gran = "snapshot_24h"
        for key, g in (
            ("acc24hr", "snapshot_24h"),
            ("acc48hr", "snapshot_48h"),
            ("acc72hr", "snapshot_72h"),
            ("ultimovalor", "10min"),
        ):
            precip = _to_float(st.get(key))
            if precip is not None:
                gran = g
                break
        if precip is None:
            continue

        rows.append({
            "codigo_ibge": code,
            "municipio_id": municipio_id,
            "estacao_id": estacao[:64],
            "estacao_nome": str(st.get("nomeestacao") or f"CEMADEN {estacao}")[:120],
            "lat": None,
            "lng": None,
            "observed_at": ts,
            "precip_mm": precip,
            "granularidade": gran,
            "data_quality": "oficial",
            "fonte": "cemaden",
            "ingestido_em": now,
            "raw_payload": {
                "acc1hr": st.get("acc1hr"),
                "acc3hr": st.get("acc3hr"),
                "acc6hr": st.get("acc6hr"),
                "acc12hr": st.get("acc12hr"),
                "acc24hr": st.get("acc24hr"),
                "acc48hr": st.get("acc48hr"),
                "acc72hr": st.get("acc72hr"),
                "acc96hr": st.get("acc96hr"),
                "ultimovalor": st.get("ultimovalor"),
                "cidade": st.get("cidade"),
                "uf": st.get("uf"),
                "endpoint": "getJson2.php",
            },
        })
    return rows


def parse_cemaden_csv(path: Path, codigo_ibge: str) -> list[dict[str, Any]]:
    """Parseia CSV depositado (histórico) ou snapshot gerado pelo download."""
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
        fieldnames = [ _norm(h) for h in (reader.fieldnames or []) ]

        # Snapshot getJson2 exportado
        if "idestacao" in fieldnames and "acc24hr" in fieldnames:
            stations = list(reader)
            return json_stations_to_rows(
                [{k: (v if v != "" else None) for k, v in row.items()} for row in stations],
                code,
            )

        for raw in reader:
            if not raw:
                continue
            estacao = _pick(raw, "estacao", "codestacao", "codigo", "id", "cod", "station", "idestacao")
            ts_raw = _pick(raw, "datahora", "data", "datetime", "valordata", "timestamp", "hora", "datahoraultimovalor")
            val_raw = _pick(raw, "valor", "chuva", "precipitacao", "precip", "mm", "precipitation", "acc24hr", "ultimovalor")
            if not estacao or val_raw is None:
                continue
            ts = _parse_ts(ts_raw or "") or now.replace(tzinfo=None)
            precip = _to_float(val_raw)
            if precip is None:
                continue
            lat_s = _pick(raw, "latitude", "lat")
            lng_s = _pick(raw, "longitude", "lng", "lon", "long")
            nome = _pick(raw, "nome", "estacaonome", "name", "nomeestacao")
            rows_out.append({
                "codigo_ibge": code,
                "municipio_id": None,
                "estacao_id": str(estacao).strip()[:64],
                "estacao_nome": (nome or f"CEMADEN {estacao}")[:120],
                "lat": float(lat_s.replace(",", ".")) if lat_s else None,
                "lng": float(lng_s.replace(",", ".")) if lng_s else None,
                "observed_at": ts,
                "precip_mm": precip,
                "granularidade": "10min",
                "data_quality": "oficial",
                "fonte": "cemaden",
                "ingestido_em": now,
                "raw_payload": {"arquivo": path.name},
            })
    return rows_out


def list_cemaden_files(codigo_ibge: str | None = None, directory: Path | None = None) -> list[Path]:
    root = Path(directory or DEFAULT_DIR)
    if not root.exists():
        return []
    files = sorted(root.glob("*.csv")) + sorted(root.glob("*.CSV"))
    if codigo_ibge:
        code = str(codigo_ibge).zfill(7)[:7]
        files = [f for f in files if code in f.name or f.name.lower().startswith(code)]
    return files


def collect_cemaden_pluvio_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    directory: Path | None = None,
    use_api: bool = True,
) -> dict[str, Any]:
    """Ingere CEMADEN via API getJson2 (preferencial) e/ou CSVs depositados."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    total = 0
    sources: list[str] = []

    if use_api:
        uf = PILOT_UF_BY_IBGE.get(code)
        if not uf and muni and getattr(muni, "uf", None):
            uf = str(muni.uf).upper()[:2]
        if uf:
            try:
                stations = fetch_cemaden_uf_json(uf)
                rows = json_stations_to_rows(
                    stations, code, municipio_id=muni.id if muni else None
                )
                if rows:
                    total += upsert_pluvio_rows(db, rows)
                    sources.append(f"api_getJson2:{uf}:{len(rows)}")
            except Exception as exc:
                logger.warning("CEMADEN API %s/%s: %s", code, uf, exc)

    files = list_cemaden_files(code, directory)
    if not files:
        files = list_cemaden_files(None, directory)

    used: list[str] = []
    for path in files:
        parsed = parse_cemaden_csv(path, code)
        if muni:
            for r in parsed:
                r["municipio_id"] = muni.id
        if parsed:
            total += upsert_pluvio_rows(db, parsed)
            used.append(path.name)

    if used:
        sources.append(f"csv:{len(used)}")

    daily_n = 0
    try:
        daily_n = materialize_cemaden_daily_from_snapshots(db, code)
        if daily_n:
            sources.append(f"diario_materializado:{daily_n}")
    except Exception as exc:
        logger.warning("Materialização diária CEMADEN %s: %s", code, exc)

    return {
        "codigo_ibge": code,
        "skipped": total == 0 and daily_n == 0,
        "records": total,
        "daily_materialized": daily_n,
        "arquivos": used,
        "sources": sources,
        "data_quality": "oficial" if (total or daily_n) else None,
        "fonte": "cemaden",
        "hint": (
            None
            if (total or daily_n)
            else (
                "Sem dados. API getJson2 falhou e não há CSV em "
                f"{directory or DEFAULT_DIR}."
            )
        ),
    }


def collect_cemaden_pluvio_pilots(db: Session) -> dict[str, Any]:
    """Baixa e persiste snapshot CEMADEN para os 6 municípios-piloto."""
    results = []
    for code in PILOT_UF_BY_IBGE:
        results.append(collect_cemaden_pluvio_municipality(db, code, use_api=True))
    return {
        "municipios": results,
        "total_records": sum(int(r.get("records") or 0) for r in results),
    }
