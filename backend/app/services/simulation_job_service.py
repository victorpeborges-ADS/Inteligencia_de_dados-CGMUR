"""Jobs assíncronos de simulação pluvial com progresso para a UI."""

from __future__ import annotations

from typing import Any

from app.db import SessionLocal
from app.services.background_jobs import create_job, get_job, run_in_background, _update
from app.services.simulation_cache import compare_rainfall_cached, run_rainfall_cached


def _progress(job_id: str, pct: int, stage: str, label: str) -> None:
    _update(
        job_id,
        progress=min(max(pct, 0), 99) if pct < 100 else 100,
        result={"stage": stage, "stage_label": label},
    )


def run_rainfall_simulation_job(
    codigo_ibge: str,
    muni_id: int,
    precip_mm: float,
    *,
    nivel_mar_m: float = 0.0,
    chuva_antecedente_mm: float = 0.0,
    sea_level_meta: dict | None = None,
    drain_removed_mm: float = 0.0,
    rede_saturada: bool = False,
    drenagem_meta: dict | None = None,
    duracao_h: float = 1.0,
) -> str:
    job_id = create_job(
        "rainfall_simulation",
        label=f"Simulação pluvial {precip_mm:.0f} mm ({codigo_ibge})",
    )

    def _task() -> dict[str, Any]:
        _progress(job_id, 8, "dem", "Carregando DEM e malha territorial…")
        db = SessionLocal()
        try:
            _progress(job_id, 25, "hydro", "Calculando acúmulo D8 e manchas de alagamento…")
            result = run_rainfall_cached(
                db,
                muni_id,
                codigo_ibge,
                precip_mm,
                nivel_mar_m=nivel_mar_m,
                chuva_antecedente_mm=chuva_antecedente_mm,
                sea_level_meta=sea_level_meta,
                drain_removed_mm=drain_removed_mm,
                rede_saturada=rede_saturada,
                drenagem_meta=drenagem_meta,
                duracao_h=duracao_h,
            )
            _progress(job_id, 70, "uncertainty", "Calculando bandas de incerteza (±15%)…")
            try:
                from app.services.uncertainty_bands_service import attach_uncertainty_bands

                result = attach_uncertainty_bands(db, muni_id, codigo_ibge, result)
            except Exception:
                pass
            _progress(job_id, 85, "metrics", "Consolidando métricas de impacto…")
            return {
                "kind": "rainfall",
                "codigo_ibge": codigo_ibge,
                "precipitacao_mm": precip_mm,
                "result": result,
                "from_cache": bool(result.get("from_cache")),
            }
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def run_rainfall_compare_job(
    codigo_ibge: str,
    muni_id: int,
    scenario_mm: float,
    baseline_mm: float,
    *,
    duracao_h: float = 1.0,
) -> str:
    job_id = create_job(
        "rainfall_compare",
        label=f"Compare {baseline_mm:.0f}→{scenario_mm:.0f} mm ({codigo_ibge})",
    )

    def _task() -> dict[str, Any]:
        _progress(job_id, 10, "baseline", f"Cenário referência ({baseline_mm:.0f} mm)…")
        db = SessionLocal()
        try:
            _progress(job_id, 35, "scenario", f"Cenário atual ({scenario_mm:.0f} mm)…")
            comparison = compare_rainfall_cached(
                db, muni_id, codigo_ibge, baseline_mm, scenario_mm, duracao_h=duracao_h,
            )
            _progress(job_id, 90, "delta", "Calculando delta entre cenários…")
            return {
                "kind": "rainfall_compare",
                "codigo_ibge": codigo_ibge,
                "comparison": comparison,
                "from_cache": bool(comparison.get("from_cache")),
            }
        finally:
            db.close()

    run_in_background(job_id, _task)
    return job_id


def get_simulation_job_progress(job_id: str) -> dict[str, Any] | None:
    job = get_job(job_id)
    if not job or job.get("type") not in {"rainfall_simulation", "rainfall_compare"}:
        return None
    result = job.get("result") or {}
    payload: dict[str, Any] = {
        "job_id": job_id,
        "type": job.get("type"),
        "status": job.get("status"),
        "progress": job.get("progress", 0),
        "stage": result.get("stage"),
        "stage_label": result.get("stage_label"),
        "error": job.get("error"),
    }
    if job.get("status") == "completed" and isinstance(result, dict):
        if result.get("kind") == "rainfall":
            payload["result"] = result.get("result")
            payload["from_cache"] = result.get("from_cache")
        elif result.get("kind") == "rainfall_compare":
            payload["comparison"] = result.get("comparison")
            payload["from_cache"] = result.get("from_cache")
    return payload
