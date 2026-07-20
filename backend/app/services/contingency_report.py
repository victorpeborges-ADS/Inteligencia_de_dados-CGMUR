"""PDF do plano de contingência."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.models import ContingencyPlan, Municipio

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "reports" / "templates"


def generate_contingency_pdf(plan: ContingencyPlan, muni: Municipio | None) -> Path:
    from weasyprint import HTML

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("contingency_plan.html")
    html = template.render(
        plan=plan,
        muni=muni,
        gerado_em=datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC"),
    )
    out_dir = Path(settings.REPORTS_DIR) / "contingency"
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"contingencia_{muni.codigo_ibge if muni else plan.id}_v{plan.versao}.pdf"
    path = out_dir / filename
    HTML(string=html).write_pdf(str(path))
    return path
