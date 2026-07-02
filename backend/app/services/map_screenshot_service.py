"""Mapas estáticos PNG para apresentação e relatórios — Sinidu+Clima Step 4."""

from __future__ import annotations

import base64
import io
import json
import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from shapely.geometry import shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Bairro, Municipio
from app.services.analytical_engine import AnalyticalEngine
from app.services.report_generator import build_bairro_ranking

logger = logging.getLogger(__name__)

VALID_LAYERS = {"vulnerabilidade", "socioeconomico", "inundacao", "bairros"}
LAYER_TITLES = {
    "vulnerabilidade": "Vulnerabilidade climática (IVC)",
    "socioeconomico": "Capacidade socioeconômica",
    "inundacao": "Risco de inundação (IRI)",
    "bairros": "Malha de bairros",
}


def _score_color(value: float) -> str:
    if value >= 66:
        return "#ef4444"
    if value >= 33:
        return "#f97316"
    return "#6366f1"


def _layer_values(db: Session, muni: Municipio, layer: str) -> dict[str, float]:
    vulnerabilities = AnalyticalEngine.calculate_climate_vulnerability(db, muni.id)
    floods = AnalyticalEngine.calculate_flood_risk(db, muni.id)
    flood_by_id = {item["id"]: item for item in floods}

    values: dict[str, float] = {}
    for item in vulnerabilities:
        name = item["bairro_nome"]
        ivc = float(item.get("indice_vulnerabilidade", 0.0))
        adaptation = float(item.get("capacidade_adaptacao", 0.0))
        flood = flood_by_id.get(item["id"], {})
        iri = float(flood.get("indice_risco_inundacao", 0.0))

        if layer == "vulnerabilidade":
            values[name] = round(ivc * 100)
        elif layer == "inundacao":
            values[name] = round(iri * 100)
        elif layer == "socioeconomico":
            values[name] = round((1.0 - adaptation) * 100)
        else:
            values[name] = 50.0
    return values


def _render_matplotlib_map(
    muni_geojson: dict,
    bairro_payloads: list[dict],
    *,
    title: str,
    width: int = 1200,
    height: int = 700,
) -> bytes:
    dpi = 100
    fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), facecolor="#0f172a", dpi=dpi)
    ax.set_facecolor("#0f172a")

    def plot_geom(geom_dict, **kwargs):
        geom = shape(geom_dict)
        if geom.geom_type == "Polygon":
            xs, ys = geom.exterior.xy
            ax.fill(xs, ys, **kwargs)
            ax.plot(xs, ys, color=kwargs.get("edgecolor", "#94a3b8"), linewidth=0.8)
        elif geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                xs, ys = poly.exterior.xy
                ax.fill(xs, ys, **kwargs)
                ax.plot(xs, ys, color=kwargs.get("edgecolor", "#94a3b8"), linewidth=0.6)

    plot_geom(muni_geojson, facecolor="#1e293b", edgecolor="#fbbf24", alpha=0.15)
    for item in bairro_payloads:
        if item.get("geom"):
            plot_geom(
                item["geom"],
                facecolor=item.get("color", "#6366f1"),
                edgecolor="#e2e8f0",
                alpha=0.55,
            )

    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, color="#e2e8f0", fontsize=14, pad=12, loc="left")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def render_map_screenshot(
    db: Session,
    muni: Municipio,
    layer: str = "vulnerabilidade",
    *,
    width: int = 1200,
    height: int = 700,
) -> bytes:
    layer_key = (layer or "vulnerabilidade").lower()
    if layer_key not in VALID_LAYERS:
        layer_key = "vulnerabilidade"

    geojson = json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))
    value_by_name = _layer_values(db, muni, layer_key)

    bairros_rows = (
        db.query(Bairro.id, Bairro.nome, func.ST_AsGeoJSON(Bairro.geom).label("geom"))
        .filter(Bairro.municipio_id == muni.id)
        .all()
    )

    bairro_payloads = []
    for row in bairros_rows:
        score = value_by_name.get(row.nome, 30 if layer_key != "bairros" else 50)
        color = "#475569" if layer_key == "bairros" else _score_color(score)
        bairro_payloads.append({"nome": row.nome, "geom": json.loads(row.geom), "color": color, "score": score})

    title = LAYER_TITLES.get(layer_key, "Mapa territorial")
    return _render_matplotlib_map(geojson, bairro_payloads, title=title, width=width, height=height)


def map_screenshot_base64(db: Session, muni: Municipio, layer: str = "vulnerabilidade") -> str:
    png = render_map_screenshot(db, muni, layer)
    return base64.b64encode(png).decode("ascii")


def save_map_screenshot(
    db: Session,
    muni: Municipio,
    layer: str = "vulnerabilidade",
) -> Path:
    out_dir = Path(settings.REPORTS_DIR) / "map-screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"map_{muni.codigo_ibge}_{layer}.png"
    path.write_bytes(render_map_screenshot(db, muni, layer))
    return path
