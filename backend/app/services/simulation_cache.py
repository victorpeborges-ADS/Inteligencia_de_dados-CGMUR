"""Cache Redis/memória para simulações pluviais (evita recomputar DEM+D8 na oficina)."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy.orm import Session

from app.data_connectors.cache import cache_get_json, cache_set_json
from app.services.analytical_engine import AnalyticalEngine
from app.services.hydro_calibration_service import calibration_cache_stamp
from app.services.hydro_simulator import HYDRO_MODEL_VERSION

SIMULATION_CACHE_TTL = int(os.getenv("SIMULATION_CACHE_TTL", str(24 * 3600)))
SIMULATION_CACHE_ENABLED = os.getenv("SIMULATION_CACHE_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)


def _rainfall_key(
    codigo_ibge: str,
    precip_mm: float,
    *,
    nivel_mar_m: float = 0.0,
    chuva_antecedente_mm: float = 0.0,
    drain_removed_mm: float = 0.0,
    aplicar_drenagem: bool = True,
) -> str:
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    stamp = calibration_cache_stamp(ibge)
    drain_flag = "1" if aplicar_drenagem else "0"
    return (
        f"sinidu:sim:rain:{ibge}:{precip_mm:.1f}"
        f":slr{float(nivel_mar_m or 0):.2f}"
        f":ant{float(chuva_antecedente_mm or 0):.0f}"
        f":drn{float(drain_removed_mm or 0):.1f}:{drain_flag}"
        f":v{HYDRO_MODEL_VERSION}:{stamp}"
    )


def _compare_key(codigo_ibge: str, baseline_mm: float, scenario_mm: float) -> str:
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    stamp = calibration_cache_stamp(ibge)
    return (
        f"sinidu:sim:raincmp:{ibge}:{baseline_mm:.1f}:{scenario_mm:.1f}"
        f":v{HYDRO_MODEL_VERSION}:{stamp}"
    )


def run_rainfall_cached(
    db: Session,
    muni_id: int,
    codigo_ibge: str,
    precip_mm: float,
    *,
    nivel_mar_m: float = 0.0,
    chuva_antecedente_mm: float = 0.0,
    sea_level_meta: dict | None = None,
    drain_removed_mm: float = 0.0,
    rede_saturada: bool = False,
    drenagem_meta: dict | None = None,
) -> dict[str, Any]:
    aplicar = bool((drenagem_meta or {}).get("aplicado", drain_removed_mm > 0))
    key = _rainfall_key(
        codigo_ibge,
        precip_mm,
        nivel_mar_m=nivel_mar_m,
        chuva_antecedente_mm=chuva_antecedente_mm,
        drain_removed_mm=drain_removed_mm,
        aplicar_drenagem=aplicar,
    )
    if SIMULATION_CACHE_ENABLED:
        cached = cache_get_json(key)
        if cached and isinstance(cached, dict):
            out = dict(cached)
            out["from_cache"] = True
            return out

    result = AnalyticalEngine.run_chuva_extrema_simulation(
        db,
        muni_id,
        precip_mm,
        nivel_mar_m=nivel_mar_m,
        chuva_antecedente_mm=chuva_antecedente_mm,
        sea_level_meta=sea_level_meta,
        drain_removed_mm=drain_removed_mm,
        rede_saturada=rede_saturada,
        drenagem_meta=drenagem_meta,
    )
    payload = {**result, "from_cache": False}
    if SIMULATION_CACHE_ENABLED:
        cache_set_json(key, payload, ttl=SIMULATION_CACHE_TTL)
    return payload


def get_compare_delta(baseline: dict[str, Any], scenario: dict[str, Any], baseline_mm: float, scenario_mm: float) -> dict[str, Any]:
    base_bairros = set(baseline.get("affected_bairros") or [])
    scen_bairros = set(scenario.get("affected_bairros") or [])
    base_meta = baseline.get("simulation_meta") or {}
    scen_meta = scenario.get("simulation_meta") or {}
    return {
        "baseline_mm": baseline_mm,
        "scenario_mm": scenario_mm,
        "affected_area_km2": round(
            float(scenario.get("affected_area_km2", 0)) - float(baseline.get("affected_area_km2", 0)), 2
        ),
        "affected_population": int(scenario.get("affected_population", 0)) - int(baseline.get("affected_population", 0)),
        "max_depth_m": round(
            float(scen_meta.get("max_depth_m") or 0) - float(base_meta.get("max_depth_m") or 0), 2
        ),
        "flood_patches": int(scen_meta.get("flood_patches") or 0) - int(base_meta.get("flood_patches") or 0),
        "bairros_novos": sorted(scen_bairros - base_bairros),
        "bairros_removidos": sorted(base_bairros - scen_bairros),
    }


def compare_rainfall_cached(
    db: Session,
    muni_id: int,
    codigo_ibge: str,
    baseline_mm: float,
    scenario_mm: float,
) -> dict[str, Any]:
    cmp_key = _compare_key(codigo_ibge, baseline_mm, scenario_mm)
    if SIMULATION_CACHE_ENABLED:
        cached = cache_get_json(cmp_key)
        if cached and isinstance(cached, dict):
            out = dict(cached)
            out["from_cache"] = True
            return out

    from concurrent.futures import ThreadPoolExecutor

    from app.db import SessionLocal

    def _run(mm: float) -> dict[str, Any]:
        session = SessionLocal()
        try:
            return run_rainfall_cached(session, muni_id, codigo_ibge, mm)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_base = pool.submit(_run, baseline_mm)
        fut_scen = pool.submit(_run, scenario_mm)
        baseline = fut_base.result()
        scenario = fut_scen.result()

    payload = {
        "baseline": baseline,
        "scenario": scenario,
        "delta": get_compare_delta(baseline, scenario, baseline_mm, scenario_mm),
        "from_cache": bool(baseline.get("from_cache") and scenario.get("from_cache")),
    }
    if SIMULATION_CACHE_ENABLED:
        cache_set_json(cmp_key, payload, ttl=SIMULATION_CACHE_TTL)
    return payload
