"""Ficha de campo imprimível a partir do painel de risco (17h.4c)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Municipio
from app.services.risk_traffic_light_service import build_risk_panel

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "reports" / "templates"


def field_report_dir() -> Path:
    path = Path(settings.REPORTS_DIR) / "field"
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_field_report_context(db: Session, codigo_ibge: str) -> dict[str, Any]:
    panel = build_risk_panel(db, codigo_ibge, top_bairros=5)
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == str(codigo_ibge).zfill(7)[:7]).first()
    return {
        "panel": panel,
        "muni": muni,
        "gerado_em": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        "hotspots": (panel.get("hotspots_recorrentes") or {}).get("hotspots") or [],
        "medidas": (panel.get("medidas_recomendadas") or [])[:5],
        "bairros": panel.get("bairros") or [],
    }


def generate_field_report_pdf(db: Session, codigo_ibge: str) -> Path:
    from weasyprint import HTML

    ctx = build_field_report_context(db, codigo_ibge)
    muni = ctx["muni"]
    if not muni:
        raise ValueError(f"Município {codigo_ibge} não encontrado")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("field_report.html").render(**ctx)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    path = field_report_dir() / f"ficha_campo_{muni.codigo_ibge}_{stamp}.pdf"
    HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(str(path))
    return path
