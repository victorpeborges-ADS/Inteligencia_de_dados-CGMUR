"""Comparador de intervenções (17d.5) — antes/depois unificado.

Reaproveita solar, telhado verde e infraverde×calor num payload comparável
para o painel (métricas + geometrias baseline/scenario).
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import Municipio

InterventionTipo = Literal["telhado_verde", "infraverde_calor", "solar"]


def compare_interventions(
    db: Session,
    codigo_ibge: str,
    *,
    tipo: InterventionTipo = "telhado_verde",
    precipitacao_mm: float = 100.0,
    telhado_verde_pct: float = 30.0,
    temperatura_pico_c: float = 36.0,
    arborizacao_pct: float = 25.0,
) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    if tipo == "solar":
        from app.services.solar_rooftop_service import compute_solar_potential

        solar = compute_solar_potential(db, code)
        return {
            "scenario_type": "comparador_intervencoes",
            "tipo": tipo,
            "codigo_ibge": code,
            "municipio": muni.nome,
            "uf": muni.uf,
            "label_antes": "Sem PV em telhados",
            "label_depois": "Potencial solar LOD1",
            "baseline": {
                "potencia_kwp": 0,
                "geracao_mwh_ano": 0,
            },
            "scenario": {
                "potencia_kwp": solar.get("potencia_total_kwp"),
                "geracao_mwh_ano": solar.get("geracao_total_mwh_ano"),
                "edificios": solar.get("edificios_avaliados"),
            },
            "delta": {
                "potencia_kwp": solar.get("potencia_total_kwp"),
                "geracao_mwh_ano": solar.get("geracao_total_mwh_ano"),
                "resumo": f"+{solar.get('potencia_total_mwp')} MWp potenciais em telhados",
            },
            "geometry_antes": {"type": "FeatureCollection", "features": []},
            "geometry_depois": solar.get("geometry"),
            "detalhe": solar,
            "metric_impact": "Potência FV potencial (kWp)",
            "impact_value": solar.get("potencia_total_kwp") or 0,
            "input_value": float(solar.get("edificios_avaliados") or 0),
            "affected_area_km2": solar.get("affected_area_km2") or 0,
            "affected_population": 0,
            "affected_bairros": [],
            "geometry": solar.get("geometry"),
            "simulation_meta": {"model_version": "17d.5", "tipo": tipo},
        }

    if tipo == "infraverde_calor":
        from app.services.green_infra_heat_service import run_green_infra_heat

        heat = run_green_infra_heat(
            db, code, temperatura_pico_c=temperatura_pico_c, arborizacao_pct=arborizacao_pct
        )
        return {
            "scenario_type": "comparador_intervencoes",
            "tipo": tipo,
            "codigo_ibge": code,
            "municipio": muni.nome,
            "uf": muni.uf,
            "label_antes": "Sem arborização adicional",
            "label_depois": f"+{arborizacao_pct:.0f}% vegetação (infraverde)",
            "baseline": heat.get("baseline"),
            "scenario": heat.get("mitigated"),
            "delta": {
                **(heat.get("delta") or {}),
                "resumo": (
                    f"Resfriamento até {heat.get('delta', {}).get('resfriamento_max_c')} °C · "
                    f"{heat.get('delta', {}).get('populacao_menos_exposta')} hab. menos expostos"
                ),
            },
            "geometry_antes": (heat.get("baseline") or {}).get("geometry"),
            "geometry_depois": heat.get("geometry"),
            "detalhe": heat,
            "metric_impact": heat.get("metric_impact"),
            "impact_value": heat.get("impact_value"),
            "input_value": arborizacao_pct,
            "affected_area_km2": heat.get("affected_area_km2"),
            "affected_population": heat.get("affected_population"),
            "affected_bairros": heat.get("affected_bairros") or [],
            "geometry": heat.get("geometry"),
            "simulation_meta": {"model_version": "17d.5", "tipo": tipo, **(heat.get("simulation_meta") or {})},
        }

    # default: telhado_verde
    from app.services.green_roof_mitigation_service import run_green_roof_mitigation

    roof = run_green_roof_mitigation(
        db,
        code,
        precipitacao_mm=precipitacao_mm,
        telhado_verde_pct=telhado_verde_pct,
    )
    return {
        "scenario_type": "comparador_intervencoes",
        "tipo": "telhado_verde",
        "codigo_ibge": code,
        "municipio": muni.nome,
        "uf": muni.uf,
        "label_antes": f"Chuva {precipitacao_mm:.0f} mm (baseline)",
        "label_depois": f"{telhado_verde_pct:.0f}% telhados verdes",
        "baseline": roof.get("baseline"),
        "scenario": roof.get("mitigated"),
        "delta": {
            **(roof.get("delta") or {}),
            "resumo": (
                f"Área evitada {roof.get('delta', {}).get('area_evitada_km2')} km² · "
                f"pop. evitada {roof.get('delta', {}).get('populacao_evitada')}"
            ),
        },
        "geometry_antes": None,  # baseline geometry not stored separately in green roof
        "geometry_depois": roof.get("geometry"),
        "detalhe": roof,
        "metric_impact": roof.get("metric_impact"),
        "impact_value": roof.get("impact_value"),
        "input_value": telhado_verde_pct,
        "affected_area_km2": roof.get("affected_area_km2"),
        "affected_population": roof.get("affected_population"),
        "affected_bairros": roof.get("affected_bairros") or [],
        "geometry": roof.get("geometry"),
        "simulation_meta": {"model_version": "17d.5", "tipo": "telhado_verde", **(roof.get("simulation_meta") or {})},
    }
