"""Telhado verde / permeabilidade (17d.2).

Cenário what-if: se X% dos telhados se tornarem permeáveis (telhado verde),
reduz o coeficiente de impermeabilização efetivo e a mancha de inundação.
"""

from __future__ import annotations

import json
import math
from typing import Any

from shapely.geometry import shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Edificacao, Municipio
from app.services.analytical_engine import AnalyticalEngine
from app.services.simulation_cache import get_compare_delta

# Eficiência hidrológica do telhado verde (redução de escoamento vs telhado convencional)
GREEN_ROOF_RUNOFF_REDUCTION = 0.55
MAX_BUILDINGS_SAMPLE = 4000


def _roof_area_total_m2(db: Session, muni: Municipio, *, limit: int = MAX_BUILDINGS_SAMPLE) -> float:
    rows = (
        db.query(Edificacao)
        .filter(Edificacao.municipio_id == muni.id, Edificacao.geom.isnot(None))
        .limit(limit)
        .all()
    )
    total = 0.0
    lat_c = -8.0
    try:
        cj = db.scalar(func.ST_AsGeoJSON(func.ST_Centroid(muni.geom)))
        if cj:
            lat_c = float(shape(json.loads(cj)).y)
    except Exception:
        pass
    corr = math.cos(math.radians(lat_c)) ** 2
    for row in rows:
        try:
            area = db.scalar(func.ST_Area(func.ST_Transform(row.geom, 3857)))
            if area:
                total += float(area) * corr
        except Exception:
            continue
    return total


def _muni_area_m2(db: Session, muni: Municipio) -> float:
    try:
        area = db.scalar(func.ST_Area(func.ST_Transform(muni.geom, 3857)))
        cj = db.scalar(func.ST_AsGeoJSON(func.ST_Centroid(muni.geom)))
        lat = float(shape(json.loads(cj)).y) if cj else -8.0
        return float(area) * (math.cos(math.radians(lat)) ** 2)
    except Exception:
        return 1.0


def impermeability_offset_from_green_roofs(
    roof_area_m2: float,
    muni_area_m2: float,
    telhado_verde_pct: float,
) -> float:
    """Offset negativo (0 a −0.25) aplicado ao raster de impermeabilização."""
    pct = max(0.0, min(100.0, float(telhado_verde_pct))) / 100.0
    if muni_area_m2 <= 0:
        return 0.0
    roof_frac = min(0.45, roof_area_m2 / muni_area_m2)
    delta = -roof_frac * pct * GREEN_ROOF_RUNOFF_REDUCTION
    return max(-0.25, round(delta, 4))


def run_green_roof_mitigation(
    db: Session,
    codigo_ibge: str,
    *,
    precipitacao_mm: float = 100.0,
    telhado_verde_pct: float = 30.0,
    ensure_buildings: bool = True,
) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    n = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    if n == 0 and ensure_buildings:
        from app.data_connectors.building_footprints_collector import collect_buildings_municipality

        collect_buildings_municipality(db, code, force=False)

    roof_m2 = _roof_area_total_m2(db, muni)
    muni_m2 = _muni_area_m2(db, muni)
    offset = impermeability_offset_from_green_roofs(roof_m2, muni_m2, telhado_verde_pct)

    baseline = AnalyticalEngine.run_chuva_extrema_simulation(
        db, muni.id, precipitacao_mm, impermeability_offset=0.0
    )
    mitigated = AnalyticalEngine.run_chuva_extrema_simulation(
        db, muni.id, precipitacao_mm, impermeability_offset=offset
    )

    delta = get_compare_delta(baseline, mitigated, precipitacao_mm, precipitacao_mm)
    # Reinterpret delta labels for mitigation (negative = improvement)
    area_saved = -float(delta.get("affected_area_km2") or 0)
    pop_saved = -int(delta.get("affected_population") or 0)

    base_iri_proxy = float((baseline.get("simulation_meta") or {}).get("mean_impermeability") or 0)
    mit_iri_proxy = float((mitigated.get("simulation_meta") or {}).get("mean_impermeability") or 0)

    return {
        "scenario_type": "telhado_verde_permeabilidade",
        "codigo_ibge": code,
        "municipio": muni.nome,
        "uf": muni.uf,
        "input_value": float(telhado_verde_pct),
        "precipitacao_mm": precipitacao_mm,
        "metric_impact": "Redução da mancha de inundação com telhados verdes",
        "impact_value": round(area_saved, 3),
        "affected_area_km2": float(mitigated.get("affected_area_km2") or 0),
        "affected_population": int(mitigated.get("affected_population") or 0),
        "affected_bairros": mitigated.get("affected_bairros") or [],
        "geometry": mitigated.get("geometry"),
        "contours": mitigated.get("contours"),
        "flow_paths": mitigated.get("flow_paths"),
        "risk_context": mitigated.get("risk_context"),
        "baseline": {
            "affected_area_km2": baseline.get("affected_area_km2"),
            "affected_population": baseline.get("affected_population"),
            "max_depth_m": (baseline.get("simulation_meta") or {}).get("max_depth_m"),
            "mean_impermeability": base_iri_proxy,
        },
        "mitigated": {
            "affected_area_km2": mitigated.get("affected_area_km2"),
            "affected_population": mitigated.get("affected_population"),
            "max_depth_m": (mitigated.get("simulation_meta") or {}).get("max_depth_m"),
            "mean_impermeability": mit_iri_proxy,
        },
        "delta": {
            **delta,
            "area_evitada_km2": round(area_saved, 3),
            "populacao_evitada": pop_saved,
            "impermeabilidade_delta": offset,
            "iri_proxy_delta": round(mit_iri_proxy - base_iri_proxy, 4),
        },
        "parametros": {
            "telhado_verde_pct": telhado_verde_pct,
            "area_telhado_m2": round(roof_m2, 0),
            "area_municipio_km2": round(muni_m2 / 1e6, 2),
            "impermeability_offset": offset,
            "eficacia_escoamento": GREEN_ROOF_RUNOFF_REDUCTION,
            "qualidade": "Estimado",
            "nota": (
                "Proxy: X% dos footprints tratados como telhado verde reduzem o coeficiente "
                "de escoamento no modelo DEM/D8. Não substitui dimensionamento de drenagem."
            ),
        },
        "simulation_meta": {
            **(mitigated.get("simulation_meta") or {}),
            "method": "green_roof_impermeability_offset",
            "model_version": "17d.2",
            "telhado_verde_pct": telhado_verde_pct,
            "impermeability_offset": offset,
            "baseline_area_km2": baseline.get("affected_area_km2"),
            "area_evitada_km2": round(area_saved, 3),
            "populacao_evitada": pop_saved,
        },
        "from_cache": False,
    }
