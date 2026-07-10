"""Exportação em lote — relatórios PDF e diagnósticos executivos."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.data_connectors.constants import TARGET_IBGE_CODES
from app.models import Municipio

logger = logging.getLogger(__name__)


def run_batch_diagnostics(
    db: Session,
    *,
    limit: int = 61,
    codigos: list[str] | None = None,
    ensure_dem: bool = True,
) -> dict[str, Any]:
    targets = (codigos or TARGET_IBGE_CODES)[: min(limit, 61)]
    processed = 0
    skipped = 0
    dem_prepared = 0
    errors: list[dict[str, str]] = []

    for codigo in targets:
        muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo).first()
        if not muni:
            skipped += 1
            errors.append({"codigo_ibge": codigo, "error": "município não carregado no PostGIS"})
            continue
        try:
            if ensure_dem:
                from app.services.dem_processor import is_processed, process_municipality_dem

                if not is_processed(codigo):
                    process_municipality_dem(db, codigo, force=False)
                    dem_prepared += 1

            from app.services.executive_diagnostic_engine import generate_executive_diagnostic

            generate_executive_diagnostic(db, codigo, origem="batch")
            processed += 1
        except Exception as exc:
            logger.exception("Diagnóstico batch falhou %s", codigo)
            db.rollback()
            errors.append({"codigo_ibge": codigo, "error": str(exc)})

    return {
        "requested": len(targets),
        "processed": processed,
        "skipped": skipped,
        "dem_prepared": dem_prepared,
        "errors": errors,
    }


def run_batch_reports(
    db: Session,
    *,
    limit: int = 61,
    force: bool = False,
    codigos: list[str] | None = None,
) -> dict[str, Any]:
    targets = (codigos or TARGET_IBGE_CODES)[: min(limit, 61)]
    processed = 0
    skipped = 0
    blocked = 0
    errors: list[dict[str, str]] = []
    report_ids: list[int] = []

    from app.services.maturity_engine import PRATA_MIN_SCORE, compute_maturity

    for codigo in targets:
        muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo).first()
        if not muni:
            skipped += 1
            errors.append({"codigo_ibge": codigo, "error": "município não carregado no PostGIS"})
            continue

        if not force:
            try:
                score = float(compute_maturity(db, codigo)["score"])
            except Exception:
                score = 0.0
            if score < PRATA_MIN_SCORE:
                blocked += 1
                errors.append({
                    "codigo_ibge": codigo,
                    "error": f"maturidade {score:.0f}% < Prata ({PRATA_MIN_SCORE}%)",
                })
                continue

        try:
            from app.services.report_generator import MunicipalReportGenerator

            record = MunicipalReportGenerator(db).generate(muni.id)
            if record.status == "concluido":
                processed += 1
                report_ids.append(record.id)
            else:
                errors.append({"codigo_ibge": codigo, "error": record.erro_mensagem or "falha na geração"})
        except Exception as exc:
            logger.exception("PDF batch falhou %s", codigo)
            db.rollback()
            errors.append({"codigo_ibge": codigo, "error": str(exc)})

    return {
        "requested": len(targets),
        "processed": processed,
        "skipped": skipped,
        "blocked_maturidade": blocked,
        "report_ids": report_ids,
        "errors": errors,
    }


def batch_coverage_summary(db: Session) -> dict[str, Any]:
    """Resumo diagnósticos/PDFs para homologação (Passo 2 do roadmap)."""
    from sqlalchemy import func, text

    from app.models import DiagnosticoExecutivo, RelatorioMunicipal

    total = db.query(func.count(Municipio.codigo_ibge)).scalar() or 0
    with_diag = (
        db.query(func.count(func.distinct(DiagnosticoExecutivo.codigo_ibge))).scalar() or 0
    )
    with_report = (
        db.query(func.count(func.distinct(RelatorioMunicipal.codigo_ibge))).scalar() or 0
    )
    sem_report_rows = db.execute(
        text(
            """
            SELECT m.codigo_ibge, m.nome, m.uf
            FROM municipios m
            LEFT JOIN (
              SELECT DISTINCT codigo_ibge FROM relatorios_municipais
            ) r ON r.codigo_ibge = m.codigo_ibge
            WHERE r.codigo_ibge IS NULL
            ORDER BY m.nome
            """
        )
    ).fetchall()
    sem_diag_rows = db.execute(
        text(
            """
            SELECT m.codigo_ibge, m.nome, m.uf
            FROM municipios m
            LEFT JOIN (
              SELECT DISTINCT codigo_ibge FROM diagnosticos_executivos
            ) d ON d.codigo_ibge = m.codigo_ibge
            WHERE d.codigo_ibge IS NULL
            ORDER BY m.nome
            """
        )
    ).fetchall()
    return {
        "municipios_total": int(total),
        "com_diagnostico": int(with_diag),
        "com_relatorio": int(with_report),
        "sem_diagnostico": [
            {"codigo_ibge": r[0], "nome": r[1], "uf": r[2]} for r in sem_diag_rows
        ],
        "sem_relatorio": [
            {"codigo_ibge": r[0], "nome": r[1], "uf": r[2]} for r in sem_report_rows
        ],
        "relatorios_ok": len(sem_report_rows) == 0,
        "diagnosticos_ok": len(sem_diag_rows) == 0,
    }
