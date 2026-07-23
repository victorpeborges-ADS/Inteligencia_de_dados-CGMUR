"""Coletor IBGE SINGED Lab — exposição CNEFE nas áreas afetadas (enchentes RS 2024).

O portal IBGE não expõe API REST pública (fetch automatizado retorna 403).
Estratégia: seed CSV curado em ``backend/data/singedlab_rs_enchentes_2024.csv`` +
import opcional de export manual do portal (filtros → CSV).
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.data_connectors.constants import TARGET_IBGE_CODES, TARGET_MUNICIPALITIES
from app.models import Municipio, MunicipioSingedlabRs
from app.timeutil import utc_now

logger = logging.getLogger(__name__)

SINGEDLAB_PORTAL_URL = "https://www.ibge.gov.br/singedlab/dados-apoio-rs.php"
SINGEDLAB_EVENT = "enchentes_rs_2024"
DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "singedlab_rs_enchentes_2024.csv"

RS_IBGE_CODES = {m["codigo_ibge"] for m in TARGET_MUNICIPALITIES if m["uf"] == "RS"}


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    try:
        return int(float(cleaned.replace(",", ".")))
    except ValueError:
        return None


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def catalog_status_for_row(row: MunicipioSingedlabRs | None) -> str:
    if not row:
        return "Ausente"
    if row.escopo == "nao_aplicavel":
        return "Nao aplicavel"
    quality = (row.data_quality or "ausente").lower()
    if quality == "oficial":
        return "Integrado"
    if quality in ("parcial_lancamento_ibge", "estimado"):
        return "Estimado"
    if quality == "pendente_import":
        return "Em integracao"
    if row.populacao_area_afetada or row.domicilios_area_afetada:
        return "Estimado"
    return "Em integracao"


def row_to_dict(row: MunicipioSingedlabRs) -> dict[str, Any]:
    return {
        "codigo_ibge": row.codigo_ibge,
        "escopo": row.escopo,
        "evento": row.evento,
        "populacao_area_afetada": row.populacao_area_afetada,
        "domicilios_area_afetada": row.domicilios_area_afetada,
        "estabelecimentos_area_afetada": row.estabelecimentos_area_afetada,
        "pct_populacao_municipio": float(row.pct_populacao_municipio) if row.pct_populacao_municipio is not None else None,
        "pct_area_municipio": float(row.pct_area_municipio) if row.pct_area_municipio is not None else None,
        "data_quality": row.data_quality,
        "fonte_url": row.fonte_url,
        "fonte_ref": row.fonte_ref,
        "status_catalogo": catalog_status_for_row(row),
        "sincronizado_em": row.sincronizado_em.isoformat() if row.sincronizado_em else None,
        "indicadores": row.indicadores or {},
    }


def load_csv_rows(csv_path: Path | None = None) -> list[dict[str, str]]:
    path = csv_path or DEFAULT_CSV
    if not path.exists():
        logger.warning("CSV SINGED Lab ausente: %s", path)
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _default_row_for_code(codigo_ibge: str) -> dict[str, str]:
    meta = next((m for m in TARGET_MUNICIPALITIES if m["codigo_ibge"] == codigo_ibge), None)
    uf = meta["uf"] if meta else ""
    if uf != "RS":
        return {
            "codigo_ibge": codigo_ibge,
            "escopo": "nao_aplicavel",
            "data_quality": "nao_aplicavel",
            "fonte_ref": "Produto pontual RS 2024 — fora do escopo geográfico",
        }
    return {
        "codigo_ibge": codigo_ibge,
        "escopo": "aplicavel",
        "data_quality": "pendente_import",
        "fonte_ref": "Importar CSV do portal IBGE SINGED Lab",
    }


def upsert_singedlab_row(
    db: Session,
    codigo_ibge: str,
    payload: dict[str, str],
    *,
    municipio_id: int | None = None,
) -> MunicipioSingedlabRs:
    row = db.query(MunicipioSingedlabRs).filter(MunicipioSingedlabRs.codigo_ibge == codigo_ibge).first()
    if not row:
        row = MunicipioSingedlabRs(codigo_ibge=codigo_ibge)
        db.add(row)

    if municipio_id is not None:
        row.municipio_id = municipio_id

    row.escopo = payload.get("escopo") or ("aplicavel" if codigo_ibge in RS_IBGE_CODES else "nao_aplicavel")
    row.evento = payload.get("evento") or SINGEDLAB_EVENT
    row.populacao_area_afetada = _parse_int(payload.get("populacao_area_afetada"))
    row.domicilios_area_afetada = _parse_int(payload.get("domicilios_area_afetada"))
    row.estabelecimentos_area_afetada = _parse_int(payload.get("estabelecimentos_area_afetada"))
    row.pct_populacao_municipio = _parse_decimal(payload.get("pct_populacao_municipio"))
    row.pct_area_municipio = _parse_decimal(payload.get("pct_area_municipio"))
    row.data_quality = payload.get("data_quality") or "ausente"
    row.fonte_url = payload.get("fonte_url") or SINGEDLAB_PORTAL_URL
    row.fonte_ref = payload.get("fonte_ref")
    row.sincronizado_em = utc_now()
    row.indicadores = {
        "metodo": "csv_curado",
        "evento_label": "Enchentes Rio Grande do Sul — maio/2024",
        "base_cnefe": "Censo 2022",
    }
    return row


def collect_singedlab_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    csv_path: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    existing = db.query(MunicipioSingedlabRs).filter(MunicipioSingedlabRs.codigo_ibge == codigo_ibge).first()
    if existing and not force and existing.sincronizado_em:
        return {"codigo_ibge": codigo_ibge, "skipped": True, "records": 1, **row_to_dict(existing)}

    csv_rows = {r["codigo_ibge"]: r for r in load_csv_rows(csv_path)}
    payload = csv_rows.get(codigo_ibge) or _default_row_for_code(codigo_ibge)

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    row = upsert_singedlab_row(db, codigo_ibge, payload, municipio_id=muni.id if muni else None)
    db.flush()
    return {"codigo_ibge": codigo_ibge, "skipped": False, "records": 1, **row_to_dict(row)}


def sync_singedlab_batch(
    db: Session,
    codigos: list[str] | None = None,
    *,
    csv_path: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    targets = codigos or TARGET_IBGE_CODES
    csv_rows = {r["codigo_ibge"]: r for r in load_csv_rows(csv_path)}
    processed = 0
    errors: list[dict[str, str]] = []

    for codigo in targets:
        try:
            payload = csv_rows.get(codigo) or _default_row_for_code(codigo)
            muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo).first()
            upsert_singedlab_row(db, codigo, payload, municipio_id=muni.id if muni else None)
            processed += 1
        except Exception as exc:
            errors.append({"codigo_ibge": codigo, "error": str(exc)})
            logger.exception("SINGED Lab sync falhou para %s", codigo)

    db.commit()
    return {"requested": len(targets), "processed": processed, "errors": errors}
