"""Infraestrutura verde × calor (17d.4).

Cenário what-if: arborização / parques / corredores verdes (ganho_vegetal_pct)
reduzem ΔT da ilha de calor por bairro — baseline × mitigado.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Municipio
from app.services.heat_simulator import DEFAULT_PEAK_TEMP_C, run_heat_island_simulation


def run_green_infra_heat(
    db: Session,
    codigo_ibge: str,
    *,
    temperatura_pico_c: float = DEFAULT_PEAK_TEMP_C,
    arborizacao_pct: float = 25.0,
) -> dict[str, Any]:
    """Compara ilha de calor sem vs com ganho de vegetação (infraverde)."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    arbor = max(0.0, min(60.0, float(arborizacao_pct)))
    peak = float(temperatura_pico_c)

    baseline = run_heat_island_simulation(
        db,
        muni.id,
        temperatura_pico_c=peak,
        perda_vegetal_pct=0.0,
        impermeabilizacao_extra_pct=0.0,
        ganho_vegetal_pct=0.0,
    )
    mitigated = run_heat_island_simulation(
        db,
        muni.id,
        temperatura_pico_c=peak,
        perda_vegetal_pct=0.0,
        impermeabilizacao_extra_pct=0.0,
        ganho_vegetal_pct=arbor,
    )

    base_meta = baseline.get("simulation_meta") or {}
    mit_meta = mitigated.get("simulation_meta") or {}
    base_max = float(base_meta.get("max_delta_t_c") or baseline.get("impact_value") or 0)
    mit_max = float(mit_meta.get("max_delta_t_c") or mitigated.get("impact_value") or 0)
    cooling_max = round(max(0.0, base_max - mit_max), 2)
    cooling_mean = float(mit_meta.get("resfriamento_medio_c") or 0)

    # Ranking de bairros que mais resfriam
    base_exp = {row["bairro"]: row for row in (baseline.get("risk_context") or [])}
    # exposures are in a custom structure — use geometry features
    base_by = {
        f["properties"]["name"]: f["properties"]
        for f in (baseline.get("geometry") or {}).get("features") or []
        if f.get("properties", {}).get("name")
    }
    mit_by = {
        f["properties"]["name"]: f["properties"]
        for f in (mitigated.get("geometry") or {}).get("features") or []
        if f.get("properties", {}).get("name")
    }
    ranking: list[dict[str, Any]] = []
    for nome, mit_p in mit_by.items():
        base_p = base_by.get(nome) or {}
        d_base = float(base_p.get("temp_increase_celsius") or 0)
        d_mit = float(mit_p.get("temp_increase_celsius") or 0)
        cool = round(max(0.0, d_base - d_mit), 2)
        if cool <= 0 and d_base <= 0:
            continue
        ranking.append({
            "bairro": nome,
            "delta_t_antes_c": d_base,
            "delta_t_depois_c": d_mit,
            "resfriamento_c": cool or float(mit_p.get("resfriamento_celsius") or 0),
            "temp_local_depois_c": mit_p.get("temp_local_celsius"),
            "populacao_exposta": mit_p.get("populacao_exposta"),
        })
    ranking.sort(key=lambda r: r["resfriamento_c"], reverse=True)

    pop_base = int(baseline.get("affected_population") or 0)
    pop_mit = int(mitigated.get("affected_population") or 0)

    return {
        "scenario_type": "infraestrutura_verde_calor",
        "codigo_ibge": code,
        "municipio": muni.nome,
        "uf": muni.uf,
        "input_value": arbor,
        "temperatura_pico_c": peak,
        "metric_impact": "Resfriamento máximo da ilha de calor (°C)",
        "impact_value": cooling_max,
        "affected_area_km2": float(mitigated.get("affected_area_km2") or 0),
        "affected_population": pop_mit,
        "affected_bairros": mitigated.get("affected_bairros") or [],
        "geometry": mitigated.get("geometry"),
        "baseline": {
            "max_delta_t_c": base_max,
            "affected_population": pop_base,
            "affected_area_km2": baseline.get("affected_area_km2"),
            "geometry": baseline.get("geometry"),
        },
        "mitigated": {
            "max_delta_t_c": mit_max,
            "affected_population": pop_mit,
            "affected_area_km2": mitigated.get("affected_area_km2"),
            "resfriamento_medio_c": cooling_mean,
        },
        "delta": {
            "resfriamento_max_c": cooling_max,
            "resfriamento_medio_c": cooling_mean,
            "populacao_menos_exposta": max(0, pop_base - pop_mit),
            "area_km2": round(
                float(baseline.get("affected_area_km2") or 0) - float(mitigated.get("affected_area_km2") or 0),
                3,
            ),
        },
        "ranking_bairros": ranking[:15],
        "parametros": {
            "arborizacao_pct": arbor,
            "temperatura_pico_c": peak,
            "qualidade": "Estimado",
            "nota": (
                "Proxy UHI: ganho de vegetação converte superfície impermeável em vegetada "
                "(Oke). Não substitui LST satélite nem estudo microclimático."
            ),
        },
        "simulation_meta": {
            **mit_meta,
            "method": "green_infra_heat_compare",
            "model_version": "17d.4",
            "arborizacao_pct": arbor,
            "baseline_max_delta_t_c": base_max,
            "resfriamento_max_c": cooling_max,
        },
        "from_cache": False,
    }
