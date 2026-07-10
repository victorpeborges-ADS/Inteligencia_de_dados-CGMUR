"""Simulação de ilha de calor urbana (UHI) — proxy territorial v1.1 (°C).

Metodologia temperatura-driven (exploratória, calibrada com dados Sinidu+Clima):
- Entrada operacional: temperatura de pico prevista para a cidade (°C).
- Intensidade da ilha de calor (ΔT) por bairro derivada da cobertura do solo
  MapBiomas (impermeabilização × vegetação) e densidade populacional.
- Onda de calor mais severa amplifica a UHI (amplificação sinótica documentada).
- Temperatura local por bairro = pico previsto + ΔT (intensidade UHI local).
- IVC entra apenas na priorização de exposição, não na física da temperatura.

Referências conceituais:
- Oke (1982) "The energetic basis of the urban heat island" — impermeabilização e
  perda de cobertura vegetal como principais controles da UHI de dossel.
- Li & Bou-Zeid (2013) — sinergia entre ondas de calor e ilhas de calor urbanas.
- EPA Heat Island Compendium — priorização por vulnerabilidade social.

Não substitui medição de LST (satélite) nem estudo microclimático de campo.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shapely.geometry import mapping, shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Bairro, CoberturaVegetalMapBiomas, Municipio, SetorCensitario
from app.services.analytical_engine import AnalyticalEngine
from app.services.official_climate import OfficialClimateService

logger = logging.getLogger(__name__)

HEAT_MODEL_VERSION = "1.1"

# Temperatura normal climatológica de fallback (°C) e pico padrão de onda de calor.
BASELINE_NORMAL_FALLBACK_C = 27.0
DEFAULT_PEAK_TEMP_C = 34.0

# Coeficientes de intensidade UHI de dossel (°C), calibrados para cidades
# tropicais/subtropicais brasileiras (ΔT típico 2–6 °C, extremos até ~8 °C).
UHI_COEF_IMPERM = 3.5   # superfície totalmente impermeável adiciona até +3.5 °C
UHI_COEF_URBAN = 1.2    # tecido urbano construído (calor antropogênico estrutural)
UHI_COEF_VEG = 2.5      # dossel pleno resfria até -2.5 °C (evapotranspiração/sombra)
UHI_COEF_DENSITY = 1.0  # calor antropogênico proporcional à densidade
HEATWAVE_AMP_K = 0.35   # amplificação da UHI sob onda de calor (por 10 °C de excesso)

CLASS_IMPERM = {
    "Área Urbana": 0.88,
    "Área construída/outros": 0.82,
    "Corpo d'água": 0.05,
    "Vegetação / Floresta": 0.22,
}

HEAT_BANDS = (
    ("leve", 0.0, 1.5, "#fbbf24"),
    ("moderada", 1.5, 3.0, "#f97316"),
    ("severa", 3.0, 99.0, "#ef4444"),
)


def _baseline_air_temp_c(db: Session, municipio: Municipio) -> tuple[float, str]:
    try:
        series = OfficialClimateService.urban_climate_series(db, municipio)
        timeline = series.get("timeline") or []
        temps = [
            float(row["temperatura_media"])
            for row in timeline
            if row.get("temperatura_media") is not None
        ]
        if temps:
            fonte = series.get("temperatura_fonte") or "INMET/MapBiomas"
            return round(temps[-1], 1), fonte
    except Exception as exc:
        logger.debug("baseline temp fallback: %s", exc)
    return BASELINE_NORMAL_FALLBACK_C, "estimado_sinidu"


def _landcover_fractions(
    db: Session,
    municipio_id: int,
    bairro_geom,
    area_deg: float,
) -> dict[str, float]:
    if not area_deg or area_deg <= 0:
        return {"vegetacao": 0.0, "urbana": 0.0, "impermeabilidade": 0.65}

    rows = (
        db.query(CoberturaVegetalMapBiomas.classe_uso, CoberturaVegetalMapBiomas.geom)
        .filter(
            CoberturaVegetalMapBiomas.municipio_id == municipio_id,
            func.ST_Intersects(bairro_geom, CoberturaVegetalMapBiomas.geom),
        )
        .all()
    )

    veg_deg = 0.0
    urban_deg = 0.0
    imperm_weighted = 0.0
    covered = 0.0

    for row in rows:
        frac_deg = AnalyticalEngine._covered_area_deg(db, bairro_geom, [row])
        if not frac_deg:
            continue
        covered += frac_deg
        classe = row.classe_uso or ""
        coef = CLASS_IMPERM.get(classe, 0.55)
        imperm_weighted += frac_deg * coef
        if classe == "Vegetação / Floresta":
            veg_deg += frac_deg
        if classe in ("Área Urbana", "Área construída/outros"):
            urban_deg += frac_deg

    denom = float(area_deg)
    veg_frac = min(1.0, veg_deg / denom)
    urban_frac = min(1.0, urban_deg / denom)
    imperm = imperm_weighted / denom if denom else 0.65

    return {
        "vegetacao": round(veg_frac, 3),
        "urbana": round(urban_frac, 3),
        "impermeabilidade": round(min(1.0, imperm), 3),
    }


def _heat_band(delta_t: float) -> str:
    for band_id, lo, hi, _ in HEAT_BANDS:
        if lo <= delta_t < hi:
            return band_id
    return "severa"


def _heatwave_amplification(temperatura_pico_c: float, baseline_normal_c: float) -> float:
    """Fator de amplificação da UHI sob onda de calor (>= 1.0).

    Quanto mais o pico previsto excede a normal climatológica local, maior a
    intensificação da ilha de calor (sinergia onda de calor × UHI).
    """
    heat_excess = max(0.0, temperatura_pico_c - baseline_normal_c)
    return 1.0 + HEATWAVE_AMP_K * min(heat_excess, 15.0) / 10.0


def _delta_t_bairro(
    *,
    land: dict[str, float],
    density_norm: float,
    temperatura_pico_c: float,
    baseline_normal_c: float,
    perda_vegetal_pct: float,
    impermeabilizacao_extra_pct: float,
    ganho_vegetal_pct: float = 0.0,
) -> float:
    """Intensidade da ilha de calor local ΔT (°C) acima do pico previsto.

    Fluxo: aplica mudanças de cobertura do cenário (perda vegetal, asfalto extra e
    ganho de vegetação/arborização), calcula a UHI de dossel (Oke) e amplifica pela
    severidade da onda de calor. Arborização converte superfície impermeável em
    vegetada, reduzindo simultaneamente os dois principais controles da UHI.
    """
    veg = land["vegetacao"]
    imperm = land["impermeabilidade"]
    urban = land["urbana"]

    veg_loss = max(0.0, min(100.0, perda_vegetal_pct)) / 100.0
    veg_gain = max(0.0, min(60.0, ganho_vegetal_pct)) / 100.0
    imperm_extra = max(0.0, min(50.0, impermeabilizacao_extra_pct)) / 100.0

    # Cobertura efetiva após perda vegetal e asfalto adicional
    imperm_after = min(1.0, imperm + imperm_extra * (1.0 - imperm) + veg_loss * veg)
    veg_after = max(0.0, veg * (1.0 - veg_loss))

    # Arborização/telhado verde converte superfície impermeável em vegetada
    convert = min(veg_gain, imperm_after)
    imperm_eff = max(0.0, imperm_after - convert)
    veg_eff = min(1.0, veg_after + convert)

    uhi = (
        UHI_COEF_IMPERM * imperm_eff
        + UHI_COEF_URBAN * urban
        - UHI_COEF_VEG * veg_eff
        + UHI_COEF_DENSITY * density_norm
    )
    uhi = max(0.0, uhi)

    delta = uhi * _heatwave_amplification(temperatura_pico_c, baseline_normal_c)
    return round(max(0.0, min(8.0, delta)), 2)


def run_heat_island_simulation(
    db: Session,
    muni_id: int,
    *,
    temperatura_pico_c: float = DEFAULT_PEAK_TEMP_C,
    perda_vegetal_pct: float = 30.0,
    impermeabilizacao_extra_pct: float = 15.0,
    ganho_vegetal_pct: float = 0.0,
) -> dict[str, Any]:
    """Simula ilha de calor por bairro com polígonos e metadados ricos.

    ``temperatura_pico_c`` é a temperatura de pico prevista para a cidade (°C).
    Cada bairro recebe ΔT (intensidade UHI local) e a temperatura local resultante.
    """
    muni = db.query(Municipio).filter(Municipio.id == muni_id).first()
    if not muni:
        raise ValueError("Município não encontrado")

    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni_id).all()
    ivc_map = {
        row["bairro_nome"]: row
        for row in AnalyticalEngine.calculate_climate_vulnerability(db, muni_id)
    }
    baseline_normal, temp_fonte = _baseline_air_temp_c(db, muni)

    features: list[dict[str, Any]] = []
    exposures: list[dict[str, Any]] = []
    affected_bairros: list[str] = []
    affected_pop = 0
    affected_area_km2 = 0.0
    max_delta = 0.0
    band_counts = {"leve": 0, "moderada": 0, "severa": 0}
    # Métrica de resfriamento por arborização: soma das reduções de ΔT ponderada por população
    cooling_sum = 0.0
    cooling_pop = 0
    cooling_max = 0.0

    def _local_temp(delta: float) -> float:
        return round(temperatura_pico_c + delta, 1)

    for b in bairros:
        area_deg = float(db.scalar(func.ST_Area(b.geom)) or 0)
        if area_deg <= 0:
            continue
        area_km2 = area_deg * 12300.0

        sectors = (
            db.query(SetorCensitario)
            .filter(
                SetorCensitario.municipio_id == muni_id,
                func.ST_Intersects(b.geom, SetorCensitario.geom),
            )
            .all()
        )
        pop = sum(s.populacao for s in sectors)
        density = pop / area_km2 if area_km2 > 0 else 0
        density_norm = min(1.0, density / 15000.0)

        land = _landcover_fractions(db, muni_id, b.geom, area_deg)
        ivc_row = ivc_map.get(b.nome, {})
        ivc = float(ivc_row.get("indice_vulnerabilidade", 0.4))

        delta_t = _delta_t_bairro(
            land=land,
            density_norm=density_norm,
            temperatura_pico_c=temperatura_pico_c,
            baseline_normal_c=baseline_normal,
            perda_vegetal_pct=perda_vegetal_pct,
            impermeabilizacao_extra_pct=impermeabilizacao_extra_pct,
            ganho_vegetal_pct=ganho_vegetal_pct,
        )

        # Referência sem arborização para quantificar o resfriamento obtido
        reducao = 0.0
        if ganho_vegetal_pct > 0:
            delta_ref = _delta_t_bairro(
                land=land,
                density_norm=density_norm,
                temperatura_pico_c=temperatura_pico_c,
                baseline_normal_c=baseline_normal,
                perda_vegetal_pct=perda_vegetal_pct,
                impermeabilizacao_extra_pct=impermeabilizacao_extra_pct,
                ganho_vegetal_pct=0.0,
            )
            reducao = max(0.0, round(delta_ref - delta_t, 2))
            if reducao > 0:
                cooling_sum += reducao * max(pop, 1)
                cooling_pop += max(pop, 1)
                cooling_max = max(cooling_max, reducao)

        if delta_t < 0.8:
            continue

        band = _heat_band(delta_t)
        band_counts[band] = band_counts.get(band, 0) + 1
        max_delta = max(max_delta, delta_t)
        local_temp = _local_temp(delta_t)

        b_geom = shape(json.loads(db.scalar(b.geom.ST_AsGeoJSON())))
        # Exposição ponderada pela intensidade térmica e pela vulnerabilidade social (IVC)
        exposure_ratio = min(1.0, (0.35 + delta_t / 8.0) * (0.7 + 0.6 * ivc))
        pop_exposta = int(pop * min(1.0, exposure_ratio))
        affected_pop += pop_exposta
        affected_area_km2 += area_km2
        affected_bairros.append(b.nome)

        exposicao_pct = round(min(100.0, (delta_t / 8.0) * 100), 1)
        exposures.append({
            "bairro": b.nome,
            "delta_t_c": delta_t,
            "temp_local_c": local_temp,
            "temp_superficie_c": local_temp,
            "faixa_calor": band,
            "exposicao_pct": exposicao_pct,
            "populacao_exposta": pop_exposta,
            "resfriamento_c": reducao,
            "vegetacao_pct": round(land["vegetacao"] * 100, 1),
            "impermeabilidade_pct": round(land["impermeabilidade"] * 100, 1),
            "ivc": ivc,
        })

        features.append({
            "type": "Feature",
            "geometry": mapping(b_geom),
            "properties": {
                "name": b.nome,
                "layer_type": "heat_band",
                "heat_band": band,
                "temp_increase_celsius": delta_t,
                "temp_local_celsius": local_temp,
                "temp_surface_celsius": local_temp,
                "temp_pico_celsius": temperatura_pico_c,
                "resfriamento_celsius": reducao,
                "vegetacao_pct": round(land["vegetacao"] * 100, 1),
                "impermeabilizacao_pct": round(land["impermeabilidade"] * 100, 1),
                "ivc": ivc,
                "populacao_exposta": pop_exposta,
            },
        })

    features.sort(key=lambda f: f["properties"]["temp_increase_celsius"], reverse=True)

    if not features:
        muni_geom = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
        fallback_delta = round(
            _delta_t_bairro(
                land={"vegetacao": 0.12, "urbana": 0.55, "impermeabilidade": 0.75},
                density_norm=0.6,
                temperatura_pico_c=temperatura_pico_c,
                baseline_normal_c=baseline_normal,
                perda_vegetal_pct=perda_vegetal_pct,
                impermeabilizacao_extra_pct=impermeabilizacao_extra_pct,
                ganho_vegetal_pct=ganho_vegetal_pct,
            ),
            2,
        )
        features.append({
            "type": "Feature",
            "geometry": mapping(muni_geom),
            "properties": {
                "name": "Município (agregado)",
                "layer_type": "heat_band",
                "heat_band": _heat_band(fallback_delta),
                "temp_increase_celsius": fallback_delta,
                "temp_local_celsius": _local_temp(fallback_delta),
                "temp_surface_celsius": _local_temp(fallback_delta),
                "temp_pico_celsius": temperatura_pico_c,
            },
        })
        max_delta = fallback_delta
        affected_pop = min(muni.populacao or 0, int((muni.populacao or 0) * 0.4))

    from app.services.hydro_simulator import build_bairro_risk_context

    risk_context = [
        row for row in build_bairro_risk_context(db, muni_id)
        if row.get("bairro") in affected_bairros
    ]

    temp_pico_local_c = round(temperatura_pico_c + max_delta, 1)
    resfriamento_medio_c = round(cooling_sum / cooling_pop, 2) if cooling_pop else 0.0

    simulation_meta = {
        "model_version": HEAT_MODEL_VERSION,
        "model_name": "UHI Territorial Sinidu+Clima",
        "method": "UHI Territorial",
        "temperatura_pico_c": temperatura_pico_c,
        "temp_pico_local_c": temp_pico_local_c,
        "baseline_normal_c": baseline_normal,
        "baseline_temp_c": baseline_normal,
        "baseline_temp_fonte": temp_fonte,
        "heatwave_amplification": round(
            _heatwave_amplification(temperatura_pico_c, baseline_normal), 3
        ),
        "perda_vegetal_pct": perda_vegetal_pct,
        "impermeabilizacao_extra_pct": impermeabilizacao_extra_pct,
        "ganho_vegetal_pct": ganho_vegetal_pct,
        "resfriamento_max_c": round(cooling_max, 2),
        "resfriamento_medio_c": resfriamento_medio_c,
        "max_delta_t_c": max_delta,
        "faixas_contagem": band_counts,
        "bairros_exposicao": exposures[:20],
        "data_sources": [
            "MapBiomas (cobertura do solo)",
            "INMET / série climática urbana (normal de referência)",
            "IBGE setores censitários (densidade)",
            "IVC Sinidu+Clima (priorização de exposição)",
        ],
        "metodologia": (
            "Modelo temperatura-driven: o gestor informa a temperatura de pico prevista; "
            "a intensidade da ilha de calor (ΔT) por bairro deriva da impermeabilização e "
            "cobertura vegetal (MapBiomas) e da densidade populacional (Oke, 1982), "
            "amplificada pela severidade da onda de calor. A arborização/telhado verde "
            "converte superfície impermeável em vegetada, reduzindo o ΔT; o resfriamento "
            "obtido é medido contra o mesmo cenário sem arborização. Temperatura local = pico + ΔT."
        ),
        "disclaimer": (
            "Simulação exploratória — não substitui medição de temperatura de superfície "
            "(LST) nem estudo microclimático. Use para priorização territorial e oficinas."
        ),
    }

    fc = {"type": "FeatureCollection", "features": features}

    return {
        "scenario_type": "HeatIsland",
        "input_value": temperatura_pico_c,
        "metric_impact": "Intensidade da ilha de calor (ΔT local, °C)",
        "impact_value": max_delta,
        "affected_area_km2": round(affected_area_km2, 2),
        "affected_population": min(affected_pop, muni.populacao or affected_pop),
        "affected_bairros": affected_bairros,
        "geometry": fc,
        "simulation_meta": simulation_meta,
        "risk_context": risk_context[:15],
    }
