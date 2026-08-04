"""Pedologia aberta SoilGrids (ISRIC) → grupo hidrológico USDA A–D.

Consulta pontual REST (areia/silte/argila 0–5 cm) no centróide municipal,
com cache em disco. Substitui o default grupo C do SCS-CN quando disponível.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import requests
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
TIMEOUT_S = 20
CACHE_NAME = "soilgrids_hsg.json"

# Escala de escoamento relativa ao grupo C (neutro) — usada no motor pluvial
SOIL_RUNOFF_SCALE = {"A": 0.88, "B": 0.95, "C": 1.0, "D": 1.08}


def _cache_path(codigo_ibge: str) -> Path:
    from app.services.dem_processor import dem_dir

    return dem_dir(str(codigo_ibge).zfill(7)[:7]) / CACHE_NAME


def _fractions_from_response(payload: dict[str, Any]) -> dict[str, float] | None:
    layers = ((payload.get("properties") or {}).get("layers")) or []
    out: dict[str, float] = {}
    for layer in layers:
        name = str(layer.get("name") or "").lower()
        depths = layer.get("depths") or []
        if not depths:
            continue
        mean = (depths[0].get("values") or {}).get("mean")
        if mean is None:
            continue
        # SoilGrids: g/kg com d_factor=10 → % = mean/10
        unit = layer.get("unit_measure") or {}
        d_factor = float(unit.get("d_factor") or 10.0)
        pct = float(mean) / d_factor
        out[name] = pct
    if not all(k in out for k in ("clay", "sand", "silt")):
        return None
    return out


def texture_class(sand: float, silt: float, clay: float) -> str:
    """Classe textural USDA simplificada (triângulo)."""
    s, si, c = float(sand), float(silt), float(clay)
    total = s + si + c
    if total <= 0:
        return "loam"
    s, si, c = 100.0 * s / total, 100.0 * si / total, 100.0 * c / total
    if c >= 40:
        return "clay"
    if c >= 35 and s < 45:
        return "silty clay" if si >= 40 else "clay"
    if c >= 27 and s <= 20:
        return "silty clay loam"
    if c >= 27 and s > 45:
        return "sandy clay"
    if c >= 20 and c < 35 and si < 28 and s > 45:
        return "sandy clay loam"
    if c >= 27 and s <= 45:
        return "clay loam"
    if si >= 80 and c < 12:
        return "silt"
    if si >= 50 and c < 27:
        return "silt loam" if c >= 12 else "silt"
    if c < 7 and si < 50 and s >= 85:
        return "sand"
    if (c < 7 and s >= 70) or (c < 20 and s >= 85):
        return "loamy sand"
    if c < 20 and s >= 52:
        return "sandy loam"
    if c < 27 and s >= 23 and s < 52 and si < 28:
        return "sandy loam"
    if (si >= 28 and c < 27 and s < 52) or (c >= 7 and c < 27 and s < 50):
        return "loam"
    return "loam"


def hydrologic_soil_group(sand: float, silt: float, clay: float) -> str:
    """HSG A–D a partir da textura (proxy NRCS para escoamento)."""
    tex = texture_class(sand, silt, clay)
    if tex in ("sand", "loamy sand"):
        return "A"
    if tex in ("sandy loam", "loam"):
        return "B"
    if tex in ("silt loam", "silt", "sandy clay loam", "clay loam", "silty clay loam"):
        return "C"
    if tex in ("sandy clay", "silty clay", "clay"):
        return "D"
    # fallback por % argila/areia
    if clay >= 40:
        return "D"
    if sand >= 70:
        return "A"
    if sand >= 50:
        return "B"
    return "C"


def query_soilgrids_point(lon: float, lat: float) -> dict[str, Any] | None:
    params = [
        ("lon", f"{lon:.5f}"),
        ("lat", f"{lat:.5f}"),
        ("property", "clay"),
        ("property", "sand"),
        ("property", "silt"),
        ("depth", "0-5cm"),
        ("value", "mean"),
    ]
    headers = {"User-Agent": "SiniduClima/1.0 (soilgrids; contact=sinidu)", "Accept": "application/json"}
    try:
        resp = requests.get(SOILGRIDS_URL, params=params, headers=headers, timeout=TIMEOUT_S)
        if resp.status_code != 200:
            logger.warning("SoilGrids HTTP %s", resp.status_code)
            return None
        fracs = _fractions_from_response(resp.json())
        if not fracs:
            return None
        sand, silt, clay = fracs["sand"], fracs["silt"], fracs["clay"]
        hsg = hydrologic_soil_group(sand, silt, clay)
        return {
            "ok": True,
            "sand_pct": round(sand, 1),
            "silt_pct": round(silt, 1),
            "clay_pct": round(clay, 1),
            "texture": texture_class(sand, silt, clay),
            "grupo_hidrologico_solo": hsg,
            "runoff_scale": SOIL_RUNOFF_SCALE.get(hsg, 1.0),
            "fonte": "soilgrids_isric_0-5cm",
            "lon": lon,
            "lat": lat,
        }
    except Exception as exc:
        logger.warning("SoilGrids query falhou: %s", exc)
        return None


def resolve_municipal_soil_group(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Grupo hidrológico municipal (cache + SoilGrids no centróide)."""
    from shapely.geometry import shape

    from app.models import Municipio

    code = str(codigo_ibge).zfill(7)[:7]
    defaults = {
        "ok": False,
        "grupo_hidrologico_solo": "C",
        "runoff_scale": 1.0,
        "fonte": "default_grupo_C",
        "texture": None,
        "sand_pct": None,
        "silt_pct": None,
        "clay_pct": None,
    }
    cache = _cache_path(code)
    if not force and cache.exists():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if cached.get("grupo_hidrologico_solo") in "ABCD":
                return cached
        except Exception:
            pass

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni or muni.geom is None:
        return defaults
    try:
        g = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
        lon, lat = float(g.centroid.x), float(g.centroid.y)
    except Exception as exc:
        logger.warning("SoilGrids centroid %s: %s", code, exc)
        return defaults

    result = query_soilgrids_point(lon, lat)
    if not result:
        return defaults

    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.info("SoilGrids cache write %s: %s", code, exc)
    return result
