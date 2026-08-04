"""SCS Curve Number a partir de MapBiomas + grupo hidrológico (Fase 21d.3).

Grupo hidrológico: SoilGrids/ISRIC (areia/silte/argila 0–5 cm) quando disponível;
fallback grupo C (moderadamente alto potencial de escoamento).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CoberturaVegetalMapBiomas, Municipio

logger = logging.getLogger(__name__)

# CN médio por classe MapBiomas × grupo hidrológico (TR-55 / adaptações urbanas)
# Fonte: USDA NRCS TR-55 + literatura urbana BR; proxy até SoilGrids/Embrapa.
CN_BY_CLASS_GROUP: dict[str, dict[str, float]] = {
    "Área Urbana": {"A": 77.0, "B": 85.0, "C": 90.0, "D": 92.0},
    "Vegetação / Floresta": {"A": 30.0, "B": 55.0, "C": 70.0, "D": 77.0},
    "Corpo d'água": {"A": 98.0, "B": 98.0, "C": 98.0, "D": 98.0},
    "Pastagem / Campo": {"A": 39.0, "B": 61.0, "C": 74.0, "D": 80.0},
    "Agricultura": {"A": 67.0, "B": 78.0, "C": 85.0, "D": 89.0},
    "Solo Exposto": {"A": 72.0, "B": 82.0, "C": 87.0, "D": 89.0},
}

DEFAULT_CLASS_CN = {"A": 60.0, "B": 72.0, "C": 80.0, "D": 85.0}
DEFAULT_SOIL_GROUP = "C"


def _normalize_class(classe: str) -> str:
    c = (classe or "").strip()
    for key in CN_BY_CLASS_GROUP:
        if key.lower() in c.lower() or c.lower() in key.lower():
            return key
    if "urban" in c.lower() or "edific" in c.lower():
        return "Área Urbana"
    if "florest" in c.lower() or "veget" in c.lower() or "mata" in c.lower():
        return "Vegetação / Floresta"
    if "água" in c.lower() or "agua" in c.lower() or "rio" in c.lower():
        return "Corpo d'água"
    if "past" in c.lower() or "campo" in c.lower():
        return "Pastagem / Campo"
    if "agric" in c.lower() or "cultura" in c.lower():
        return "Agricultura"
    return c


def cn_for_class(classe: str, soil_group: str = DEFAULT_SOIL_GROUP) -> float:
    g = (soil_group or DEFAULT_SOIL_GROUP).upper()[:1]
    if g not in "ABCD":
        g = DEFAULT_SOIL_GROUP
    key = _normalize_class(classe)
    table = CN_BY_CLASS_GROUP.get(key) or DEFAULT_CLASS_CN
    return float(table.get(g, DEFAULT_CLASS_CN[g]))


def scs_runoff_mm(precip_mm: float, cn: float) -> float:
    """Escoamento direto SCS (mm) para precipitação e CN dados."""
    p = max(0.0, float(precip_mm))
    cn_v = max(1.0, min(100.0, float(cn)))
    s = (1000.0 / cn_v) - 10.0  # polegadas → converter
    s_mm = s * 25.4
    ia = 0.2 * s_mm
    if p <= ia:
        return 0.0
    q = ((p - ia) ** 2) / (p - ia + s_mm)
    return round(max(0.0, q), 3)


def municipal_cn_features(
    db: Session,
    codigo_ibge: str,
    *,
    soil_group: str | None = None,
    precip_ref_mm: float = 50.0,
) -> dict[str, Any]:
    """CN ponderado por área MapBiomas + escoamento de referência (50 mm)."""
    code = str(codigo_ibge).zfill(7)[:7]
    soil_meta: dict[str, Any] = {}
    if soil_group is None:
        try:
            from app.services.soilgrids_service import resolve_municipal_soil_group

            soil_meta = resolve_municipal_soil_group(db, code)
            soil_group = str(soil_meta.get("grupo_hidrologico_solo") or DEFAULT_SOIL_GROUP)
        except Exception as exc:
            logger.info("SoilGrids CN %s: %s — default C", code, exc)
            soil_group = DEFAULT_SOIL_GROUP
    g = (soil_group or DEFAULT_SOIL_GROUP).upper()[:1]
    if g not in "ABCD":
        g = DEFAULT_SOIL_GROUP

    defaults = {
        "curve_number": 85.0,
        "grupo_hidrologico_solo": g,
        "escoamento_ref_50mm": scs_runoff_mm(precip_ref_mm, 85.0),
        "cn_fonte": "default_urbano",
        "soil_fonte": soil_meta.get("fonte") or "default_grupo_C",
        "soil_texture": soil_meta.get("texture"),
        "runoff_scale_solo": float(soil_meta.get("runoff_scale") or 1.0),
    }
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return defaults

    rows = (
        db.query(
            CoberturaVegetalMapBiomas.classe_uso,
            func.sum(func.ST_Area(CoberturaVegetalMapBiomas.geom)).label("area"),
        )
        .filter(CoberturaVegetalMapBiomas.municipio_id == muni.id)
        .group_by(CoberturaVegetalMapBiomas.classe_uso)
        .all()
    )
    if not rows:
        return defaults

    total = 0.0
    weighted = 0.0
    for classe, area in rows:
        a = float(area or 0.0)
        if a <= 0:
            continue
        total += a
        weighted += a * cn_for_class(str(classe), g)

    if total <= 0:
        return defaults

    cn = round(weighted / total, 2)
    soil_src = soil_meta.get("fonte") or "default_grupo_C"
    return {
        "curve_number": cn,
        "grupo_hidrologico_solo": g,
        "escoamento_ref_50mm": scs_runoff_mm(precip_ref_mm, cn),
        "cn_fonte": f"mapbiomas_x_{soil_src}_grupo_{g}",
        "soil_fonte": soil_src,
        "soil_texture": soil_meta.get("texture"),
        "sand_pct": soil_meta.get("sand_pct"),
        "silt_pct": soil_meta.get("silt_pct"),
        "clay_pct": soil_meta.get("clay_pct"),
        "runoff_scale_solo": float(soil_meta.get("runoff_scale") or 1.0),
    }


def bairro_cn_proxy(
    impermeabilizacao_pct: float,
    cobertura_vegetal_pct: float,
    water_proximity: float = 0.0,
    *,
    soil_group: str = DEFAULT_SOIL_GROUP,
) -> float:
    """CN local por composição de uso do bairro (sem geometria MapBiomas)."""
    urban = max(0.0, min(100.0, float(impermeabilizacao_pct))) / 100.0
    veg = max(0.0, min(100.0, float(cobertura_vegetal_pct))) / 100.0
    water = max(0.0, min(1.0, float(water_proximity)))
    other = max(0.0, 1.0 - urban - veg - water)
    cn = (
        urban * cn_for_class("Área Urbana", soil_group)
        + veg * cn_for_class("Vegetação / Floresta", soil_group)
        + water * cn_for_class("Corpo d'água", soil_group)
        + other * cn_for_class("Pastagem / Campo", soil_group)
    )
    return round(cn, 2)
