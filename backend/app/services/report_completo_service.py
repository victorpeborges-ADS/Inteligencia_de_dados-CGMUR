"""Relatório municipal completo enriquecido — Step 8 (IA + gráficos + 8 páginas)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import DiagnosticoExecutivo, Municipio, RelatorioMunicipal
from app.reports.chart_generator import gerar_todos_graficos
from app.services.action_plan_engine import build_action_plan_payload
from app.services.executive_diagnostic_engine import generate_executive_diagnostic
from app.services.report_generator import (
    TEMPLATE_DIR,
    MunicipalReportGenerator,
    _ensure_capag_fresh,
    _format_currency,
    _format_number,
    _score_methodology,
    build_bairro_ranking,
)

logger = logging.getLogger(__name__)

LOGO_CANDIDATES = [
    TEMPLATE_DIR.parent / "assets" / "logo-sinidu-clima.png",
    Path(__file__).resolve().parents[3] / "frontend" / "public" / "logo-sinidu-clima.png",
]

STAGES = (
    ("graficos", 30, "Gerando gráficos e mapas…"),
    ("narrativa", 50, "Compilando narrativa IA…"),
    ("html", 75, "Montando documento HTML…"),
    ("pdf", 100, "Renderizando PDF (WeasyPrint)…"),
)


def _logo_uri() -> str | None:
    for path in LOGO_CANDIDATES:
        if path.exists():
            return path.as_uri()
    return None


def _score_circle_color(score: int | None) -> str:
    if score is None:
        return "#64748b"
    if score >= 66:
        return "#ef4444"
    if score >= 33:
        return "#f97316"
    return "#22c55e"


def _severity_label(score: int | None) -> str:
    if score is None:
        return "—"
    if score >= 66:
        return "Crítica"
    if score >= 33:
        return "Alta"
    if score >= 20:
        return "Moderada"
    return "Baixa"


def _disaster_stats(db: Session, muni: Municipio) -> dict[str, Any]:
    from app.models import HistoricoDesastreS2ID

    cutoff = date.today() - timedelta(days=365 * 10)
    rows = (
        db.query(HistoricoDesastreS2ID)
        .filter(
            HistoricoDesastreS2ID.municipio_id == muni.id,
            HistoricoDesastreS2ID.data_ocorrencia >= cutoff,
        )
        .all()
    )
    total = len(rows)
    maior_dano = max((float(r.danos_materiais or 0) for r in rows), default=0)
    return {
        "total_10_anos": total,
        "maior_dano": maior_dano,
        "maior_dano_fmt": _format_currency(maior_dano),
        "periodo": f"{cutoff.year}–{date.today().year}",
    }


def _infra_summary(db: Session, muni: Municipio) -> list[dict[str, Any]]:
    from app.models import InfraestruturaUrbana

    rows = db.query(InfraestruturaUrbana).filter(InfraestruturaUrbana.municipio_id == muni.id).all()
    by_type: dict[str, int] = {}
    for row in rows:
        tipo = (row.tipo or "Outros").strip()
        by_type[tipo] = by_type.get(tipo, 0) + 1
    return [{"tipo": k, "quantidade": v} for k, v in sorted(by_type.items(), key=lambda x: -x[1])[:12]]


def _fontes_consultadas(generated_at: datetime) -> list[dict[str, str]]:
    ts = generated_at.strftime("%d/%m/%Y")
    return [
        {"fonte": "IBGE — Censo e estimativas", "data": ts, "tipo": "OFICIAL"},
        {"fonte": "S2ID / CEMADEN — desastres e alertas", "data": ts, "tipo": "OFICIAL"},
        {"fonte": "CAPAG / Tesouro Transparente", "data": ts, "tipo": "OFICIAL"},
        {"fonte": "MapBiomas / Open-Meteo", "data": ts, "tipo": "OFICIAL"},
        {"fonte": "Sinidu+Clima — Score e ranking", "data": ts, "tipo": "DERIVADO"},
        {"fonte": "Sinidu+Clima IA — narrativa executiva", "data": ts, "tipo": "IA"},
    ]


ProgressFn = Callable[[int, str, str], None]


def build_completo_context(
    db: Session,
    muni: Municipio,
    *,
    charts: dict[str, str] | None = None,
    on_progress: ProgressFn | None = None,
) -> dict[str, Any]:
    def prog(pct: int, stage: str, label: str) -> None:
        if on_progress:
            on_progress(pct, stage, label)

    if charts is None:
        prog(10, "graficos", STAGES[0][2])

        def _chart_step(name: str, step: int) -> None:
            prog(10 + step * 5, "graficos", f"Gráfico: {name}…")

        charts = gerar_todos_graficos(muni.codigo_ibge, on_step=_chart_step)
        prog(30, "graficos", "Gráficos concluídos")

    prog(35, "narrativa", STAGES[1][2])
    diag = (
        db.query(DiagnosticoExecutivo)
        .filter(DiagnosticoExecutivo.codigo_ibge == muni.codigo_ibge)
        .order_by(DiagnosticoExecutivo.gerado_em.desc())
        .first()
    )
    if not diag or not diag.narrativa_ia:
        try:
            diag = generate_executive_diagnostic(db, muni.codigo_ibge, origem="relatorio_completo")
        except Exception as exc:
            logger.warning("Diagnóstico IA não gerado: %s", exc)

    narrativa = diag.narrativa_ia if diag else None
    narrativa_meta = (diag.narrativa_ia_meta or {}) if diag else {}
    paragrafos = narrativa_meta.get("paragrafos") or []
    if not paragrafos and narrativa:
        paragrafos = [p.strip() for p in narrativa.split("\n\n") if p.strip()][:3]
    versao = diag.versao if diag else 1

    prog(50, "narrativa", "Narrativa IA pronta")

    prog(52, "html", "Ranking territorial…")
    ranking, snapshot = build_bairro_ranking(db, muni)
    fiscal, capag_meta = _ensure_capag_fresh(db, muni)
    base_gen = MunicipalReportGenerator(db)
    prog(55, "html", "Plano de ação e casos referência…")
    base_ctx = base_gen._build_context(muni)
    plan_payload = build_action_plan_payload(db, muni, diagnostic_id=diag.id if diag else None)

    score_val = int(snapshot.get("score_sinidu") or 0)
    top_bairros = ranking[:10]
    for row in top_bairros:
        row["risco_principal"] = (
            "Inundação" if row.get("iri", 0) > row.get("ivc", 0) else "Vulnerabilidade climática"
        )
        row["pop_estimada"] = "—"

    generated_at = datetime.now()
    prog(60, "html", STAGES[2][2])

    return {
        **base_ctx,
        "report_mode": "completo",
        "logo_uri": _logo_uri(),
        "generated_at": generated_at.strftime("%d/%m/%Y %H:%M"),
        "footer_date": generated_at.strftime("%d/%m/%Y"),
        "total_pages": 8,
        "diagnostico_versao": versao,
        "score_circle_color": _score_circle_color(score_val),
        "severidade": _severity_label(score_val),
        "n_bairros_prioritarios": len([r for r in ranking if r["score_sinidu"] >= 33]),
        "narrativa_ia": narrativa,
        "narrativa_paragrafos": paragrafos,
        "narrativa_ia_meta": narrativa_meta,
        "charts": charts,
        "ranking_top10": top_bairros,
        "disaster_stats": _disaster_stats(db, muni),
        "infra_summary": _infra_summary(db, muni),
        "plano_completo": plan_payload,
        "acoes_curto": plan_payload.get("acoes_curto_prazo") or [],
        "acoes_medio": plan_payload.get("acoes_medio_prazo") or [],
        "acoes_longo": plan_payload.get("acoes_longo_prazo") or [],
        "fontes_tabela": _fontes_consultadas(generated_at),
        "metodologia": _score_methodology(),
        "capa_titulo": "DIAGNÓSTICO TERRITORIAL INTEGRADO",
        "capa_subtitulo": "Gerado por Sinidu+Clima · MCID/CGMUR/DDUM/SNDUM",
    }


def render_completo_html(context: dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("municipal_report_completo.html")
    return template.render(**context)


def generate_completo_report(
    db: Session,
    codigo_ibge: str,
    *,
    on_progress: ProgressFn | None = None,
) -> RelatorioMunicipal:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise ValueError(f"Município {codigo_ibge} não encontrado.")

    reports_dir = Path(settings.REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{codigo_ibge}_completo_{stamp}.pdf"
    filepath = reports_dir / filename

    record = RelatorioMunicipal(
        municipio_id=muni.id,
        codigo_ibge=codigo_ibge,
        nome_arquivo=filename,
        caminho_arquivo=str(filepath),
        status="gerando",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        context = build_completo_context(db, muni, on_progress=on_progress)
        if on_progress:
            on_progress(75, "html", "HTML montado")
        html = render_completo_html(context)
        if on_progress:
            on_progress(85, "pdf", STAGES[3][2])
        from weasyprint import HTML

        HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(str(filepath))
        record.status = "concluido"
        record.tamanho_bytes = filepath.stat().st_size if filepath.exists() else 0
        if filepath.exists():
            from app.services.sei_export import sha256_file

            record.sha256_hash = sha256_file(filepath)
        if on_progress:
            on_progress(100, "pdf", "PDF concluído")
    except Exception as exc:
        logger.exception("Falha relatório completo %s", codigo_ibge)
        record.status = "falha"
        record.erro_mensagem = str(exc)
        if filepath.exists():
            filepath.unlink(missing_ok=True)
        raise
    finally:
        db.commit()
        db.refresh(record)

    return record


def run_completo_report_job(codigo_ibge: str) -> str:
    from app.services.background_jobs import create_job, run_in_background, _update

    muni_label = codigo_ibge
    job_id = create_job("municipal_report_completo", label=f"Relatório completo ({codigo_ibge})")

    def _progress(pct: int, stage: str, label: str) -> None:
        _update(
            job_id,
            progress=min(pct, 99) if pct < 100 else 100,
            result={"stage": stage, "stage_label": label, "codigo_ibge": codigo_ibge},
        )

    def _task() -> dict[str, Any]:
        db = SessionLocal()
        try:
            _progress(5, "init", "Iniciando relatório completo…")
            record = generate_completo_report(db, codigo_ibge, on_progress=_progress)
            return {
                "report_id": record.id,
                "codigo_ibge": codigo_ibge,
                "nome_arquivo": record.nome_arquivo,
                "tamanho_bytes": record.tamanho_bytes,
                "download_url": f"/api/v1/reports/{record.id}/download",
            }
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def get_report_job_progress(job_id: str) -> dict[str, Any] | None:
    from app.services.background_jobs import get_job

    job = get_job(job_id)
    if not job or job.get("type") != "municipal_report_completo":
        return None
    result = job.get("result") or {}
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "progress": job.get("progress", 0),
        "stage": result.get("stage"),
        "stage_label": result.get("stage_label"),
        "report_id": result.get("report_id"),
        "download_url": result.get("download_url"),
        "error": job.get("error"),
    }
