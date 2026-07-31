"""Potencial solar em telhados LOD1 (17d.1).

Área de telhado ≈ footprint (m²) × fração útil + irradiância por latitude
→ kWp e geração anual estimada por edifício / município.
"""

from __future__ import annotations

import json
import math
from typing import Any

from shapely.geometry import mapping, shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Edificacao, Municipio

# Fração do footprint utilizável para PV (setbacks, HVAC, sombra própria)
ROOF_USABLE_FRACTION = 0.70
# Densidade típica de módulos em telhado plano (kWp / m² útil)
KWP_PER_M2 = 0.15
# Performance ratio (sujidade, temperatura, inverter)
PERFORMANCE_RATIO = 0.75
MAX_BUILDINGS = 5000

# HSP aproximado (horas de sol pleno / dia) por faixa de latitude S
def _hsp_from_lat(lat: float) -> float:
    """Horas de sol pleno médias anuais — proxy Brasil (INPE/CRESESB-like)."""
    alat = abs(lat)
    if alat <= 8:
        return 5.4  # Norte / litoral NE equatorial
    if alat <= 12:
        return 5.2  # Recife / Aracaju
    if alat <= 16:
        return 5.0
    if alat <= 20:
        return 4.8
    if alat <= 24:
        return 4.6
    return 4.4


def _muni_centroid_lat(db: Session, muni: Municipio) -> float:
    try:
        if muni.geom is not None:
            cj = db.scalar(func.ST_AsGeoJSON(func.ST_Centroid(muni.geom)))
            if cj:
                c = shape(json.loads(cj))
                return float(c.y)
    except Exception:
        pass
    # Recife fallback
    return -8.05


def _footprint_area_m2(db: Session, row: Edificacao) -> float | None:
    try:
        # geography → m² reais
        area = db.scalar(func.ST_Area(func.ST_Transform(row.geom, 3857)))
        if area is None:
            return None
        # Web Mercator distorce — correção aproximada por cos²(lat)
        gjson = db.scalar(func.ST_AsGeoJSON(func.ST_Centroid(row.geom)))
        lat = 0.0
        if gjson:
            lat = float(shape(json.loads(gjson)).y)
        corr = math.cos(math.radians(lat)) ** 2
        return max(0.0, float(area) * corr)
    except Exception:
        try:
            gjson = db.scalar(row.geom.ST_AsGeoJSON())
            g = shape(json.loads(gjson))
            # graus² → m² aproximado
            lat = g.centroid.y
            m_per_deg_lat = 110_540.0
            m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))
            return abs(g.area) * m_per_deg_lat * m_per_deg_lon
        except Exception:
            return None


def compute_building_solar(
    area_m2: float,
    *,
    hsp: float,
    usable_fraction: float = ROOF_USABLE_FRACTION,
) -> dict[str, float]:
    area_util = area_m2 * usable_fraction
    kwp = area_util * KWP_PER_M2
    kwh_ano = kwp * hsp * 365.0 * PERFORMANCE_RATIO
    return {
        "area_telhado_m2": round(area_m2, 1),
        "area_util_m2": round(area_util, 1),
        "potencia_kwp": round(kwp, 2),
        "geracao_kwh_ano": round(kwh_ano, 0),
    }


def compute_solar_potential(
    db: Session,
    codigo_ibge: str,
    *,
    limit: int = MAX_BUILDINGS,
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

    lat = _muni_centroid_lat(db, muni)
    hsp = _hsp_from_lat(lat)

    rows = (
        db.query(Edificacao)
        .filter(Edificacao.municipio_id == muni.id, Edificacao.geom.isnot(None))
        .limit(max(1, min(int(limit), MAX_BUILDINGS)))
        .all()
    )

    features: list[dict[str, Any]] = []
    tot_area = 0.0
    tot_kwp = 0.0
    tot_kwh = 0.0

    for row in rows:
        area = _footprint_area_m2(db, row)
        if area is None or area < 15:
            continue
        solar = compute_building_solar(area, hsp=hsp)
        tot_area += solar["area_telhado_m2"]
        tot_kwp += solar["potencia_kwp"]
        tot_kwh += solar["geracao_kwh_ano"]

        try:
            geo = json.loads(db.scalar(row.geom.ST_AsGeoJSON()))
        except Exception:
            continue

        features.append({
            "type": "Feature",
            "geometry": geo,
            "properties": {
                "id": row.id,
                "osm_id": row.osm_id,
                "nome": row.nome,
                "uso": row.uso,
                "altura_m": float(row.altura_m or 0),
                **solar,
                "hsp": hsp,
                "layer_type": "solar_rooftop",
                "_extrusionHeightM": float(row.altura_m or 6),
                "_fill": "#f59e0b" if solar["potencia_kwp"] >= 10 else "#fbbf24",
            },
        })

    # Top 20 para painel
    top = sorted(features, key=lambda f: f["properties"]["potencia_kwp"], reverse=True)[:20]

    return {
        "scenario_type": "potencial_solar_telhado",
        "codigo_ibge": code,
        "municipio": muni.nome,
        "uf": muni.uf,
        "edificios_avaliados": len(features),
        "area_telhado_total_m2": round(tot_area, 0),
        "area_telhado_total_km2": round(tot_area / 1e6, 3),
        "potencia_total_kwp": round(tot_kwp, 1),
        "potencia_total_mwp": round(tot_kwp / 1000.0, 2),
        "geracao_total_mwh_ano": round(tot_kwh / 1000.0, 1),
        "hsp": hsp,
        "latitude_ref": round(lat, 4),
        "parametros": {
            "fracao_util": ROOF_USABLE_FRACTION,
            "kwp_por_m2": KWP_PER_M2,
            "performance_ratio": PERFORMANCE_RATIO,
            "orientacao": "telhado plano LOD1 (fator 1.0) — refinar com LOD2/orientação",
            "qualidade": "Estimado",
            "nota": (
                "Proxy a partir do footprint OSM; não substitui estudo de sombreamento, "
                "orientação de águas nem levantamento estrutural."
            ),
        },
        "top_edificios": [
            {
                "id": f["properties"]["id"],
                "nome": f["properties"].get("nome"),
                "potencia_kwp": f["properties"]["potencia_kwp"],
                "geracao_kwh_ano": f["properties"]["geracao_kwh_ano"],
                "area_telhado_m2": f["properties"]["area_telhado_m2"],
            }
            for f in top
        ],
        "geometry": {"type": "FeatureCollection", "features": features},
        "metric_impact": "Potência fotovoltaica potencial em telhados (kWp)",
        "impact_value": round(tot_kwp, 1),
        "input_value": float(len(features)),
        "affected_area_km2": round(tot_area / 1e6, 3),
        "affected_population": 0,
        "affected_bairros": [],
        "simulation_meta": {
            "method": "footprint_hsp_pv",
            "model_version": "17d.1",
            "qualidade": "Estimado",
        },
    }
