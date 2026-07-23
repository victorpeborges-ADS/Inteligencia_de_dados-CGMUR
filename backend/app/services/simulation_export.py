"""Exportação de simulações territoriais — GeoJSON, KMZ e PDF para oficina."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.models import Municipio

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "reports" / "templates"

# Cores KML (aabbggrr) por tipo de camada / faixa
_KML_COLORS = {
    "simulation": "9900aaff",
    "flood_band": "9900aaff",
    "contour": "cc888888",
    "flow_path": "ff00ffff",
    "heat": "990000ff",
    "default": "9900ffff",
}
_DEPTH_COLORS = {
    "superficial": "6600ff00",
    "leve": "9900ffff",
    "moderada": "9900aaff",
    "severa": "990000ff",
    "critica": "cc0000ff",
    "alta": "990000ff",
}


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


def _kml_color_for_props(props: dict[str, Any]) -> str:
    depth = str(props.get("depth_band") or props.get("heat_band") or "").lower()
    if depth in _DEPTH_COLORS:
        return _DEPTH_COLORS[depth]
    layer = str(props.get("layer_type") or "default")
    return _KML_COLORS.get(layer, _KML_COLORS["default"])


def _ring_coords_kml(ring: list[Any]) -> str:
    parts: list[str] = []
    for pt in ring:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        lon, lat = float(pt[0]), float(pt[1])
        alt = float(pt[2]) if len(pt) > 2 and pt[2] is not None else 0.0
        parts.append(f"{lon},{lat},{alt}")
    return " ".join(parts)


def _geometry_to_kml(geom: dict[str, Any] | None) -> str:
    """Converte geometria GeoJSON (EPSG:4326) em fragmento KML."""
    if not geom or not isinstance(geom, dict):
        return ""
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not gtype or coords is None:
        return ""

    if gtype == "Point":
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            return ""
        lon, lat = float(coords[0]), float(coords[1])
        alt = float(coords[2]) if len(coords) > 2 and coords[2] is not None else 0.0
        return f"<Point><coordinates>{lon},{lat},{alt}</coordinates></Point>"

    if gtype == "LineString":
        return (
            "<LineString><tessellate>1</tessellate>"
            f"<coordinates>{_ring_coords_kml(coords)}</coordinates></LineString>"
        )

    if gtype == "Polygon":
        if not coords:
            return ""
        outer = _ring_coords_kml(coords[0])
        inners = "".join(
            "<innerBoundaryIs><LinearRing>"
            f"<coordinates>{_ring_coords_kml(ring)}</coordinates>"
            "</LinearRing></innerBoundaryIs>"
            for ring in coords[1:]
        )
        return (
            "<Polygon><tessellate>1</tessellate>"
            f"<outerBoundaryIs><LinearRing><coordinates>{outer}</coordinates></LinearRing></outerBoundaryIs>"
            f"{inners}</Polygon>"
        )

    if gtype == "MultiPoint":
        return "".join(
            _geometry_to_kml({"type": "Point", "coordinates": c}) for c in coords or []
        )

    if gtype == "MultiLineString":
        parts = [
            _geometry_to_kml({"type": "LineString", "coordinates": line})
            for line in coords or []
        ]
        joined = "".join(p for p in parts if p)
        return f"<MultiGeometry>{joined}</MultiGeometry>" if joined else ""

    if gtype == "MultiPolygon":
        parts = [
            _geometry_to_kml({"type": "Polygon", "coordinates": poly})
            for poly in coords or []
        ]
        joined = "".join(p for p in parts if p)
        return f"<MultiGeometry>{joined}</MultiGeometry>" if joined else ""

    if gtype == "GeometryCollection":
        parts = [_geometry_to_kml(g) for g in geom.get("geometries") or [] if isinstance(g, dict)]
        joined = "".join(p for p in parts if p)
        return f"<MultiGeometry>{joined}</MultiGeometry>" if joined else ""

    return ""


def _placemark_name(props: dict[str, Any], idx: int) -> str:
    for key in ("name", "nome", "bairro", "label", "depth_band", "heat_band", "layer_type"):
        val = props.get(key)
        if val not in (None, ""):
            return str(val)
    return f"feature_{idx + 1}"


def _placemark_description(props: dict[str, Any], collection_props: dict[str, Any]) -> str:
    rows = [
        f"<tr><td><b>{xml_escape(str(k))}</b></td><td>{xml_escape(str(v))}</td></tr>"
        for k, v in props.items()
        if v is not None and not isinstance(v, (dict, list))
    ]
    meta_bits = []
    for key in ("municipio", "codigo_ibge", "scenario_type", "input_value"):
        if collection_props.get(key) is not None:
            meta_bits.append(f"{key}={collection_props[key]}")
    header = xml_escape(" · ".join(meta_bits)) if meta_bits else "Sinidu+Clima"
    body = "".join(rows) if rows else "<tr><td colspan='2'>Sem atributos</td></tr>"
    return (
        f"<![CDATA[<div><p>{header}</p>"
        f"<table border='1' cellpadding='3'>{body}</table></div>]]>"
    )


def build_simulation_kml(
    simulation: dict[str, Any],
    muni: Municipio,
    *,
    comparison: dict[str, Any] | None = None,
) -> str:
    """Gera documento KML 2.2 a partir do empacotamento GeoJSON da simulação."""
    fc = build_simulation_geojson(simulation, muni, comparison=comparison)
    coll_props = fc.get("properties") or {}
    name = xml_escape(str(fc.get("name") or f"sinidu_{muni.codigo_ibge}"))
    desc = xml_escape(
        f"Simulação Sinidu+Clima — {muni.nome}/{muni.uf} — "
        f"{coll_props.get('scenario_type')} ({coll_props.get('input_value')})"
    )

    placemarks: list[str] = []
    for idx, feat in enumerate(fc.get("features") or []):
        if not isinstance(feat, dict):
            continue
        geom_kml = _geometry_to_kml(feat.get("geometry") if isinstance(feat.get("geometry"), dict) else None)
        if not geom_kml:
            continue
        props = dict(feat.get("properties") or {})
        color = _kml_color_for_props(props)
        pm_name = xml_escape(_placemark_name(props, idx))
        pm_desc = _placemark_description(props, coll_props)
        is_line = (feat.get("geometry") or {}).get("type") in {"LineString", "MultiLineString"}
        style = (
            f"<Style><LineStyle><color>{color}</color><width>2</width></LineStyle>"
            f"<PolyStyle><color>{color}</color><fill>0</fill><outline>1</outline></PolyStyle></Style>"
            if is_line
            else (
                f"<Style><LineStyle><color>ffffffff</color><width>1</width></LineStyle>"
                f"<PolyStyle><color>{color}</color><fill>1</fill><outline>1</outline></PolyStyle></Style>"
            )
        )
        placemarks.append(
            f"<Placemark><name>{pm_name}</name><description>{pm_desc}</description>"
            f"{style}{geom_kml}</Placemark>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        f"<Document><name>{name}</name><description>{desc}</description>\n"
        f"{''.join(placemarks)}\n"
        "</Document></kml>\n"
    )


def save_simulation_kmz(
    simulation: dict[str, Any],
    muni: Municipio,
    *,
    comparison: dict[str, Any] | None = None,
) -> Path:
    """Gera KMZ (ZIP com doc.kml) compatível com Google Earth / QGIS / ArcGIS."""
    kml = build_simulation_kml(simulation, muni, comparison=comparison)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = _slug_scenario(str(simulation.get("scenario_type", "sim")))
    filename = f"simulacao_{muni.codigo_ibge}_{slug}_{ts}.kmz"
    path = simulation_export_dir() / filename
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml.encode("utf-8"))
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
