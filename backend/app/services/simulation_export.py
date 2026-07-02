"""Exportação de simulações territoriais — GeoJSON e PDF para oficina."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.models import Municipio

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "reports" / "templates"


def simulation_export_dir() -> Path:
    path = Path(settings.REPORTS_DIR) / "simulations"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slug_scenario(scenario_type: str) -> str:
    mapping = {
        "ExtremeRainfall": "chuva_extrema",
        "Waterproofing": "impermeabilizacao",
        "VegetationLoss": "perda_vegetacao",
        "DrainageDeficit": "deficit_drenagem",
    }
    return mapping.get(scenario_type, scenario_type.lower())


def build_simulation_geojson(
    simulation: dict[str, Any],
    muni: Municipio,
    *,
    comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Empacota manchas, curvas, escoamento e metadados em um FeatureCollection."""
    features: list[dict[str, Any]] = []

    def _append_fc(fc: dict[str, Any] | None, default_layer: str) -> None:
        if not fc or not isinstance(fc, dict):
            return
        for feat in fc.get("features") or []:
            if not isinstance(feat, dict):
                continue
            props = dict(feat.get("properties") or {})
            props.setdefault("layer_type", default_layer)
            props["municipio"] = muni.nome
            props["codigo_ibge"] = muni.codigo_ibge
            features.append({**feat, "properties": props})

    geom = simulation.get("geometry")
    if isinstance(geom, dict) and geom.get("type") == "Feature":
        props = dict(geom.get("properties") or {})
        props.setdefault("layer_type", "simulation")
        props["municipio"] = muni.nome
        props["codigo_ibge"] = muni.codigo_ibge
        features.append({**geom, "properties": props})
    else:
        _append_fc(geom if isinstance(geom, dict) else None, "simulation")
    _append_fc(simulation.get("contours"), "contour")
    _append_fc(simulation.get("flow_paths"), "flow_path")

    meta = simulation.get("simulation_meta") or {}
    return {
        "type": "FeatureCollection",
        "name": f"sinidu_simulacao_{muni.codigo_ibge}",
        "properties": {
            "platform": "Sinidu+Clima",
            "municipio": muni.nome,
            "uf": muni.uf,
            "codigo_ibge": muni.codigo_ibge,
            "scenario_type": simulation.get("scenario_type"),
            "input_value": simulation.get("input_value"),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "simulation_meta": meta,
            "comparison_delta": comparison,
            "feature_count": len(features),
            "crs_note": "EPSG:4326 — WGS84",
        },
        "features": features,
    }


def save_simulation_geojson(
    simulation: dict[str, Any],
    muni: Municipio,
    *,
    comparison: dict[str, Any] | None = None,
) -> Path:
    payload = build_simulation_geojson(simulation, muni, comparison=comparison)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = _slug_scenario(str(simulation.get("scenario_type", "sim")))
    filename = f"simulacao_{muni.codigo_ibge}_{slug}_{ts}.geojson"
    path = simulation_export_dir() / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def generate_simulation_pdf(
    simulation: dict[str, Any],
    muni: Municipio,
    *,
    comparison: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
) -> Path:
    from weasyprint import HTML

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("simulation_brief.html")
    meta = simulation.get("simulation_meta") or {}
    html = template.render(
        muni=muni,
        simulation=simulation,
        meta=meta,
        comparison=comparison,
        analysis=analysis or {},
        gerado_em=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
    )
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = _slug_scenario(str(simulation.get("scenario_type", "sim")))
    filename = f"simulacao_{muni.codigo_ibge}_{slug}_{ts}.pdf"
    path = simulation_export_dir() / filename
    HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(str(path))
    return path


def export_download_meta(path: Path, *, route_prefix: str = "/api/v1/simulations/download") -> dict[str, Any]:
    return {
        "nome_arquivo": path.name,
        "tamanho_bytes": path.stat().st_size,
        "download_url": f"{route_prefix}/{path.name}",
    }
