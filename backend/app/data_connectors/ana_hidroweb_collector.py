"""Coletor ANA / HidroWeb (SNIRH) — stub com instrução de credencial (Fase 21b.2).

A API oficial exige cadastro e token Bearer.
Documentação: https://www.ana.gov.br/hidrowebservice
Cadastro / suporte: hidro@ana.gov.br

Variáveis de ambiente esperadas (quando credencial existir):
  ANA_HIDROWEB_TOKEN   — Bearer JWT
  ANA_HIDROWEB_BASE    — default https://www.ana.gov.br/hidrowebservice

Sem token, a série fluviométrica (Fase 21c.3) também aceita CSVs depositados
manualmente (mesmo padrão do coletor INMET/BDMEP) — ver
``collect_fluvio_series_for_municipality`` e ``scripts/ana_hidroweb/README.md``.
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

from app.services.fluvio_series_service import upsert_fluvio_rows
from app.timeutil import utc_now

logger = logging.getLogger(__name__)

DEFAULT_BASE = "https://www.ana.gov.br/hidrowebservice"
CREDENTIAL_HELP = (
    "API ANA HidroWeb exige cadastro. Solicite acesso em hidro@ana.gov.br, "
    "obtenha o Bearer token e defina ANA_HIDROWEB_TOKEN no ambiente. "
    "Sem credencial, a ingestão fluviométrica/pluviométrica ANA fica desligada."
)

DEFAULT_FLUVIO_DIR = Path(os.getenv("ANA_FLUVIO_DIR", "/data/ana_hidroweb"))
FALLBACK_FLUVIO_DIR = Path(__file__).resolve().parents[3] / "scripts" / "ana_hidroweb" / "downloads"


def ana_credentials_configured() -> bool:
    token = (os.getenv("ANA_HIDROWEB_TOKEN") or "").strip()
    return bool(token)


def credential_status() -> dict[str, Any]:
    configured = ana_credentials_configured()
    return {
        "configured": configured,
        "base_url": (os.getenv("ANA_HIDROWEB_BASE") or DEFAULT_BASE).rstrip("/"),
        "env_var": "ANA_HIDROWEB_TOKEN",
        "help": None if configured else CREDENTIAL_HELP,
        "fase": "21b.2",
    }


def _auth_headers() -> dict[str, str]:
    token = (os.getenv("ANA_HIDROWEB_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(CREDENTIAL_HELP)
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "SiniduMVP/21b.2",
    }


def probe_api(timeout: float = 20.0) -> dict[str, Any]:
    """Testa autenticação com um endpoint leve (quando token existir)."""
    status = credential_status()
    if not status["configured"]:
        return {**status, "ok": False, "reason": "credencial_ausente"}

    base = status["base_url"]
    # Endpoint típico de inventário — pode variar; falha documentada não é crash.
    url = f"{base}/EstacoesTelemetricas/HidroInventarioEstacoesTelemetricas/v1"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=_auth_headers(), params={"codigoEstacao": "1"})
        return {
            **status,
            "ok": resp.status_code in (200, 204, 404),
            "http_status": resp.status_code,
            "probe_url": url,
            "detail": (resp.text or "")[:300],
        }
    except Exception as exc:
        logger.warning("ANA probe falhou: %s", exc)
        return {**status, "ok": False, "reason": str(exc), "probe_url": url}


def collect_pluvio_series_for_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Placeholder de ingestão pluviométrica ANA → serie_pluviometrica_observada.

    dry_run=True (default) só reporta status até o contrato da API ser validado
    com token real.
    """
    code = str(codigo_ibge).zfill(7)[:7]
    status = credential_status()
    if not status["configured"]:
        return {
            "codigo_ibge": code,
            "ok": False,
            "ingested": 0,
            "reason": "credencial_ausente",
            **status,
        }

    if dry_run:
        probe = probe_api()
        return {
            "codigo_ibge": code,
            "ok": bool(probe.get("ok")),
            "ingested": 0,
            "dry_run": True,
            "nota": (
                "Credencial presente. Próximo passo: mapear estações no município, "
                "baixar série e upsert em serie_pluviometrica_observada (fonte=ana)."
            ),
            "probe": probe,
            **status,
        }

    # Implementação completa depende do contrato autenticado (inventário + telemetria).
    return {
        "codigo_ibge": code,
        "ok": False,
        "ingested": 0,
        "reason": "nao_implementado_sem_contrato_validado",
        "nota": "Use dry_run=True até validar endpoints com o token real.",
        **status,
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


def parse_ana_fluvio_csv(path: Path, codigo_ibge: str) -> list[dict[str, Any]]:
    """Parseia CSV depositado manualmente (colunas: estacao, data, cota_m[, vazao_m3s]).

    Mesmo padrão do coletor INMET/BDMEP (Fase 21b.3) — funciona sem token ANA.
    """
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
            estacao = _pick(raw, "estacao", "codigoestacao", "cdestacao", "station", "id")
            ts_raw = _pick(raw, "data", "dtmedicao", "datamedicao", "datetime", "datahora", "timestamp")
            cota_raw = _pick(raw, "cotam", "cota", "nivel", "nivelm", "stage")
            vazao_raw = _pick(raw, "vazaom3s", "vazao", "flow", "discharge")
            if not estacao or (cota_raw is None and vazao_raw is None):
                continue
            ts = _parse_ts(ts_raw or "")
            if ts is None:
                continue
            cota = _to_float(cota_raw)
            vazao = _to_float(vazao_raw)
            if cota is None and vazao is None:
                continue
            lat_s = _pick(raw, "latitude", "lat")
            lng_s = _pick(raw, "longitude", "lng", "lon", "long")
            nome = _pick(raw, "nome", "estacaonome", "name")
            gran = "diaria" if len((ts_raw or "").strip()) <= 10 else "horaria"
            rows_out.append({
                "codigo_ibge": code,
                "municipio_id": None,
                "estacao_id": str(estacao).strip()[:64],
                "estacao_nome": (nome or f"ANA {estacao}")[:120],
                "lat": float(lat_s.replace(",", ".")) if lat_s else None,
                "lng": float(lng_s.replace(",", ".")) if lng_s else None,
                "observed_at": ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts,
                "cota_m": cota,
                "vazao_m3s": vazao,
                "granularidade": gran,
                "data_quality": "oficial",
                "fonte": "ana",
                "ingestido_em": now,
                "raw_payload": {"arquivo": path.name, "origem": "csv_deposit"},
            })
    return rows_out


def list_ana_fluvio_files(codigo_ibge: str | None = None, directory: Path | None = None) -> list[Path]:
    roots = [Path(directory)] if directory else [DEFAULT_FLUVIO_DIR, FALLBACK_FLUVIO_DIR]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(sorted(root.glob("*.csv")))
        files.extend(sorted(root.glob("*.CSV")))
    if codigo_ibge:
        code = str(codigo_ibge).zfill(7)[:7]
        files = [f for f in files if code in f.name or f.name.lower().startswith(code)]
    return files


def collect_fluvio_series_for_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    dry_run: bool = True,
    directory: Path | None = None,
) -> dict[str, Any]:
    """Ingestão fluviométrica ANA (Fase 21c.3/21d.9).

    Ordem de preferência (funciona **sem** token):
    1. CSV depositado em ``ANA_FLUVIO_DIR`` ou ``scripts/ana_hidroweb/downloads/``
       (colunas: estacao, data, cota_m[, vazao_m3s]) — mesmo padrão do INMET/BDMEP.
    2. Se não houver CSV e não houver token: retorna dica de credencial.
    3. Se houver token: dry_run=True apenas sonda a API; dry_run=False ainda
       depende do contrato autenticado (não implementado nesta fase).
    """
    code = str(codigo_ibge).zfill(7)[:7]

    files = list_ana_fluvio_files(code, directory)
    if not files:
        files = list_ana_fluvio_files(None, directory)
    if files:
        from app.models import Municipio

        muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
        total = 0
        used: list[str] = []
        for path in files:
            parsed = parse_ana_fluvio_csv(path, code)
            if muni:
                for r in parsed:
                    r["municipio_id"] = muni.id
            if parsed:
                total += upsert_fluvio_rows(db, parsed)
                used.append(path.name)
        return {
            "codigo_ibge": code,
            "ok": total > 0,
            "ingested": total,
            "fonte": "ana",
            "data_quality": "oficial" if total else None,
            "arquivos": used,
            "metodo": "csv_deposit",
        }

    status = credential_status()
    if not status["configured"]:
        return {
            "codigo_ibge": code,
            "ok": False,
            "ingested": 0,
            "reason": "sem_csv_e_sem_credencial",
            "hint": (
                f"Sem CSV em {directory or DEFAULT_FLUVIO_DIR} / {FALLBACK_FLUVIO_DIR}. "
                "Deposite export do HidroWeb (estacao, data, cota_m) ou configure ANA_HIDROWEB_TOKEN."
            ),
            **status,
        }

    if dry_run:
        probe = probe_api()
        return {
            "codigo_ibge": code,
            "ok": bool(probe.get("ok")),
            "ingested": 0,
            "dry_run": True,
            "nota": (
                "Credencial presente. Próximo passo: mapear estações fluviométricas no "
                "município, baixar série e upsert em serie_fluviometrica_observada (fonte=ana)."
            ),
            "probe": probe,
            **status,
        }

    return {
        "codigo_ibge": code,
        "ok": False,
        "ingested": 0,
        "reason": "nao_implementado_sem_contrato_validado",
        "nota": "Use dry_run=True até validar endpoints com o token real, ou deposite CSV.",
        **status,
    }
