"""PDF do Diagnóstico Executivo Automático."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.models import DiagnosticoExecutivo, Municipio
from app.services.executive_diagnostic_engine import _fmt_currency, _fmt_num

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "reports" / "templates"


def _html_to_pdf(html: str, path: Path, *, base_url: str | None = None) -> None:
    from weasyprint import HTML

    HTML(string=html, base_url=base_url).write_pdf(str(path))


def diagnostic_pdf_dir() -> Path:
    path = Path(settings.REPORTS_DIR) / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def diagnostic_pdf_filename(codigo_ibge: str, versao: int) -> str:
    return f"diagnostico_{codigo_ibge}_v{versao}.pdf"


def diagnostic_pdf_path(codigo_ibge: str, versao: int) -> Path:
    return diagnostic_pdf_dir() / diagnostic_pdf_filename(codigo_ibge, versao)


def generate_diagnostic_pdf(record: DiagnosticoExecutivo, muni: Municipio) -> Path:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("executive_diagnostic.html")
    conteudo = record.conteudo or {}
    html = template.render(
        muni=muni,
        record=record,
        headline=record.headline,
        sections=conteudo,
        perfil=conteudo.get("perfil_municipal") or {},
        fiscal=conteudo.get("situacao_fiscal") or {},
        climatica=conteudo.get("situacao_climatica") or {},
        historico=conteudo.get("historico_desastres") or {},
        vegetal=conteudo.get("cobertura_vegetal") or {},
        riscos=conteudo.get("principais_riscos") or {},
        lacunas=conteudo.get("lacunas") or {},
        fmt_num=_fmt_num,
        fmt_currency=_fmt_currency,
        gerado_em=(record.gerado_em or datetime.utcnow()).strftime("%d/%m/%Y %H:%M"),
        narrativa_ia=record.narrativa_ia,
        narrativa_ia_meta=record.narrativa_ia_meta or {},
        narrativa_paragrafos=(record.narrativa_ia_meta or {}).get("paragrafos")
        or (record.conteudo or {}).get("narrativa_ia_paragrafos")
        or [],
    )
    path = diagnostic_pdf_path(record.codigo_ibge, record.versao)
    _html_to_pdf(html, path, base_url=str(TEMPLATE_DIR))
    return path


def ensure_diagnostic_pdf(record: DiagnosticoExecutivo, muni: Municipio) -> Path:
    path = diagnostic_pdf_path(record.codigo_ibge, record.versao)
    if not path.exists():
        return generate_diagnostic_pdf(record, muni)
    return path


def diagnostic_download_meta(record: DiagnosticoExecutivo) -> dict[str, str | int | None]:
    path = diagnostic_pdf_path(record.codigo_ibge, record.versao)
    if not path.exists():
        return {"nome_arquivo": None, "tamanho_bytes": None, "download_url": None}
    return {
        "nome_arquivo": path.name,
        "tamanho_bytes": path.stat().st_size,
        "download_url": f"/api/v1/diagnostic/{record.codigo_ibge}/download-pdf?versao={record.versao}",
    }
