"""Módulos climáticos extras (17g.1g): estresse hídrico/seca e proxy de arbovírus.

Proxies ambientais territoriais — não são incidência epidemiológica nem SPEI oficial.
"""

from __future__ import annotations

import json
import math
from typing import Any, Literal

from shapely.geometry import mapping, shape
from sqlalchemy.orm import Session

from app.models import Bairro, Municipio, SetorCensitario, WeatherForecastCache
from app.services.drainage_capacity_service import resolve_drainage_capacity
from app.services.heat_simulator import _baseline_air_temp_c, _landcover_fractions

CLIMATE_MODULES_VERSION = "1.0"

Modo = Literal["seca", "arbovirus"]

NIVEL_LABEL = {
    "baixo": "Baixo",
    "moderado": "Moderado",
    "alto": "Alto",
    "muito_alto": "Muito alto",
}

SECA_COLORS = {
    "baixo": "#84cc16",
    "moderado": "#eab308",
    "alto": "#f97316",
    "muito_alto": "#b91c1c",
}

ARBO_COLORS = {
    "baixo": "#67e8f9",
    "moderado": "#fbbf24",
    "alto": "#fb923c",
    "muito_alto": "#e11d48",
}


def _nivel(score: float) -> str:
    if score < 25:
        return "baixo"
    if score < 50:
        return "moderado"
    if score < 75:
        return "alto"
    return "muito_alto"


def _latest_weather(db: Session, codigo_ibge: str) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    row = (
        db.query(WeatherForecastCache)
        .filter(WeatherForecastCache.codigo_ibge == code)
        .order_by(WeatherForecastCache.fetched_at.desc())
        .first()
    )
    if not row:
        return {
            "precip_24h_mm": None,
            "precip_72h_mm": None,
            "temp_media_c": None,
            "fonte": "ausente",
        }
    temp = None
    raw = row.raw_payload if isinstance(row.raw_payload, dict) else {}
    hourly = (raw.get("hourly") or {}) if isinstance(raw, dict) else {}
    temps = hourly.get("temperature_2m") or []
    if temps:
        vals = [float(t) for t in temps[:24] if t is not None]
        if vals:
            temp = sum(vals) / len(vals)
    return {
        "precip_24h_mm": float(row.precip_24h_mm) if row.precip_24h_mm is not None else None,
        "precip_72h_mm": float(row.precip_72h_mm) if row.precip_72h_mm is not None else None,
        "temp_media_c": round(temp, 1) if temp is not None else None,
        "fonte": "openmeteo_cache",
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
    }


def _temp_suitability_aedes(temp_c: float) -> float:
    """Adequação térmica Aedes (0–1): ótimo ~28 °C, faixa útil 18–34 °C."""
    t = float(temp_c)
    if t < 18 or t > 34:
        return 0.05
    # Gaussiana em torno de 28 °C
    return float(math.exp(-0.5 * ((t - 28.0) / 4.5) ** 2))


def _bairro_density_norm(db: Session, municipio_id: int, bairro_geom, area_km2: float) -> float:
    from sqlalchemy import func

    sectors = (
        db.query(SetorCensitario)
        .filter(
            SetorCensitario.municipio_id == municipio_id,
            func.ST_Intersects(bairro_geom, SetorCensitario.geom),
        )
        .all()
    )
    total = sum(int(s.populacao or 0) for s in sectors)
    if area_km2 <= 0:
        return 0.0
    return min(1.0, (total / area_km2) / 8000.0)


def run_drought_stress_simulation(
    db: Session,
    muni: Municipio,
    *,
    precip_72h_mm: float | None = None,
    precip_esperada_72h_mm: float = 25.0,
) -> dict[str, Any]:
    """Estresse hídrico 0–100: déficit de chuva recente × impermeabilidade × baixa vegetação."""
    weather = _latest_weather(db, muni.codigo_ibge)
    p72 = precip_72h_mm
    if p72 is None:
        p72 = weather.get("precip_72h_mm")
    if p72 is None:
        p72 = 12.0  # fallback neutro-seco
        fonte_precip = "estimado"
    else:
        fonte_precip = weather.get("fonte") or "override"

    esperado = max(5.0, float(precip_esperada_72h_mm))
    deficit = max(0.0, min(1.0, 1.0 - float(p72) / esperado))

    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    features: list[dict[str, Any]] = []
    ranking: list[dict[str, Any]] = []
    scores: list[float] = []

    for b in bairros:
        try:
            g = shape(json.loads(db.scalar(b.geom.ST_AsGeoJSON())))
        except Exception:
            continue
        area_deg = float(g.area or 0)
        if area_deg <= 0:
            continue
        land = _landcover_fractions(db, muni.id, b.geom, area_deg)
        imperm = float(land["impermeabilidade"])
        veg = float(land["vegetacao"])
        # Solo urbano seco + pouca vegetação agrava estresse
        land_stress = 0.45 * imperm + 0.40 * (1.0 - veg) + 0.15 * float(land["urbana"])
        score = 100.0 * (0.55 * deficit + 0.45 * land_stress)
        score = max(0.0, min(100.0, score))
        nivel = _nivel(score)
        scores.append(score)
        props = {
            "layer_type": "drought_stress",
            "bairro": b.nome,
            "score": round(score, 1),
            "nivel": nivel,
            "nivel_label": NIVEL_LABEL[nivel],
            "fill_color": SECA_COLORS[nivel],
            "deficit_precip": round(deficit, 3),
            "impermeabilidade_pct": round(imperm * 100, 1),
            "vegetacao_pct": round(veg * 100, 1),
            "name": f"Estresse hídrico — {b.nome}",
        }
        features.append({"type": "Feature", "geometry": mapping(g), "properties": props})
        ranking.append({
            "bairro": b.nome,
            "score": round(score, 1),
            "nivel": nivel,
        })

    ranking.sort(key=lambda r: r["score"], reverse=True)
    media = round(sum(scores) / len(scores), 1) if scores else round(100.0 * deficit, 1)
    nivel_muni = _nivel(media)
    criticos = [r["bairro"] for r in ranking if r["score"] >= 50][:12]
    pop = int(muni.populacao or 0)
    affected_pop = int(pop * (media / 100.0) * 0.35) if pop else 0

    return {
        "scenario_type": "DroughtStress",
        "input_value": round(float(p72), 1),
        "metric_impact": "Índice municipal de estresse hídrico (0–100)",
        "impact_value": media,
        "affected_area_km2": round(float(muni.area_km2 or 0) * (media / 100.0) * 0.4, 2),
        "affected_population": affected_pop,
        "affected_bairros": criticos,
        "geometry": {"type": "FeatureCollection", "features": features},
        "simulation_meta": {
            "modulo": "seca",
            "model_version": CLIMATE_MODULES_VERSION,
            "method": "deficit_precip_x_cobertura",
            "indice_municipal": media,
            "nivel": nivel_muni,
            "nivel_label": NIVEL_LABEL[nivel_muni],
            "precip_72h_mm": round(float(p72), 1),
            "precip_esperada_72h_mm": esperado,
            "deficit_precip": round(deficit, 3),
            "fonte_precip": fonte_precip,
            "ranking_bairros": ranking[:15],
            "qualidade_dado": "Derivado",
            "nota": (
                "Proxy de estresse hídrico: déficit de precipitação recente (72h vs esperado) "
                "amplificado por impermeabilização e baixa vegetação. Não é SPEI/SPI oficial."
            ),
        },
    }


def run_arbovirus_proxy_simulation(
    db: Session,
    muni: Municipio,
    *,
    temperatura_media_c: float | None = None,
    precip_7d_mm: float | None = None,
) -> dict[str, Any]:
    """Proxy ambiental de risco de arbovírus (T ótimo × água parada pós-chuva)."""
    weather = _latest_weather(db, muni.codigo_ibge)
    baseline_t, fonte_t = _baseline_air_temp_c(db, muni)

    temp = temperatura_media_c
    if temp is None:
        temp = weather.get("temp_media_c")
    if temp is None:
        temp = baseline_t
        fonte_temp = fonte_t
    else:
        fonte_temp = "override" if temperatura_media_c is not None else (weather.get("fonte") or fonte_t)

    p72 = weather.get("precip_72h_mm")
    if precip_7d_mm is not None:
        p7 = float(precip_7d_mm)
        fonte_precip = "override"
    elif p72 is not None:
        # 72h como proxy de janela curta pós-chuva (~7d se só houver forecast)
        p7 = float(p72) * 1.35
        fonte_precip = weather.get("fonte") or "openmeteo_cache"
    else:
        p7 = 40.0
        fonte_precip = "estimado"

    dren = resolve_drainage_capacity(db, muni, precip_mm=max(p7, 10.0), duracao_h=1.0)
    # Capacidade baixa → mais água parada
    cap = float(dren.get("capacidade_mm_h") or 18.0)
    drain_factor = max(0.15, min(1.0, 1.0 - (cap - 8.0) / 42.0))

    t_suit = _temp_suitability_aedes(float(temp))
    # Água parada: chuva moderada favorece criadouros; chuva extrema dilui
    if p7 <= 5:
        water_pool = 0.15
    elif p7 <= 80:
        water_pool = min(1.0, p7 / 55.0)
    else:
        water_pool = max(0.35, 1.0 - (p7 - 80.0) / 120.0)

    standing = water_pool * drain_factor

    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    features: list[dict[str, Any]] = []
    ranking: list[dict[str, Any]] = []
    scores: list[float] = []

    for b in bairros:
        try:
            g = shape(json.loads(db.scalar(b.geom.ST_AsGeoJSON())))
        except Exception:
            continue
        area_deg = float(g.area or 0)
        if area_deg <= 0:
            continue
        area_km2 = max(area_deg * 12300.0, 0.01)
        land = _landcover_fractions(db, muni.id, b.geom, area_deg)
        imperm = float(land["impermeabilidade"])
        veg = float(land["vegetacao"])
        dens = _bairro_density_norm(db, muni.id, b.geom, area_km2)
        # Criadouros: impermeável + baixa veg + densidade
        habitat = 0.50 * imperm + 0.30 * (1.0 - veg) + 0.20 * dens
        score = 100.0 * (0.40 * t_suit + 0.35 * standing + 0.25 * habitat)
        score = max(0.0, min(100.0, score))
        nivel = _nivel(score)
        scores.append(score)
        props = {
            "layer_type": "arbovirus_proxy",
            "bairro": b.nome,
            "score": round(score, 1),
            "nivel": nivel,
            "nivel_label": NIVEL_LABEL[nivel],
            "fill_color": ARBO_COLORS[nivel],
            "temp_suitability": round(t_suit, 3),
            "agua_parada": round(standing, 3),
            "habitat_urbano": round(habitat, 3),
            "name": f"Proxy arbovírus — {b.nome}",
        }
        features.append({"type": "Feature", "geometry": mapping(g), "properties": props})
        ranking.append({"bairro": b.nome, "score": round(score, 1), "nivel": nivel})

    ranking.sort(key=lambda r: r["score"], reverse=True)
    media = round(sum(scores) / len(scores), 1) if scores else round(100.0 * (0.5 * t_suit + 0.5 * standing), 1)
    nivel_muni = _nivel(media)
    criticos = [r["bairro"] for r in ranking if r["score"] >= 50][:12]
    pop = int(muni.populacao or 0)
    affected_pop = int(pop * (media / 100.0) * 0.25) if pop else 0

    return {
        "scenario_type": "ArbovirusRiskProxy",
        "input_value": round(float(temp), 1),
        "metric_impact": "Proxy ambiental de risco de arbovírus (0–100)",
        "impact_value": media,
        "affected_area_km2": round(float(muni.area_km2 or 0) * (media / 100.0) * 0.35, 2),
        "affected_population": affected_pop,
        "affected_bairros": criticos,
        "geometry": {"type": "FeatureCollection", "features": features},
        "simulation_meta": {
            "modulo": "arbovirus",
            "model_version": CLIMATE_MODULES_VERSION,
            "method": "temp_aedes_x_agua_parada_x_habitat",
            "indice_municipal": media,
            "nivel": nivel_muni,
            "nivel_label": NIVEL_LABEL[nivel_muni],
            "temperatura_media_c": round(float(temp), 1),
            "fonte_temperatura": fonte_temp,
            "precip_7d_mm_proxy": round(float(p7), 1),
            "fonte_precip": fonte_precip,
            "temp_suitability": round(t_suit, 3),
            "agua_parada": round(standing, 3),
            "drenagem_capacidade_mm_h": dren.get("capacidade_mm_h"),
            "ranking_bairros": ranking[:15],
            "qualidade_dado": "Derivado",
            "nota": (
                "Proxy ambiental (temperatura ótima Aedes × água parada pós-chuva × habitat urbano). "
                "Não estima casos de dengue/zika/chikungunya nem substitui vigilância epidemiológica."
            ),
        },
    }


def run_climate_module(
    db: Session,
    muni: Municipio,
    modo: Modo,
    *,
    precip_72h_mm: float | None = None,
    precip_esperada_72h_mm: float = 25.0,
    temperatura_media_c: float | None = None,
    precip_7d_mm: float | None = None,
) -> dict[str, Any]:
    if modo == "seca":
        return run_drought_stress_simulation(
            db,
            muni,
            precip_72h_mm=precip_72h_mm,
            precip_esperada_72h_mm=precip_esperada_72h_mm,
        )
    return run_arbovirus_proxy_simulation(
        db,
        muni,
        temperatura_media_c=temperatura_media_c,
        precip_7d_mm=precip_7d_mm,
    )
