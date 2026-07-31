"""Pré-aquecimento do cache de simulação pluvial (demo Recife/Aracaju)."""

from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Municipio
from app.services.simulation_cache import compare_rainfall_cached, run_rainfall_cached

logger = logging.getLogger(__name__)

_prewarm_lock = threading.Lock()
_prewarm_inflight: set[str] = set()
_compare_inflight: set[str] = set()


def _cache_key(codigo_ibge: str, precip_mm: float) -> str:
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    return f"{ibge}:{precip_mm:.1f}"


def _compare_cache_key(codigo_ibge: str, baseline_mm: float, scenario_mm: float) -> str:
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    return f"{ibge}:cmp:{baseline_mm:.1f}:{scenario_mm:.1f}"


def _ensure_dem_ready(db: Session, codigo_ibge: str) -> None:
    if not settings.DEM_PREWARM_ENABLED:
        return
    from app.services.dem_prewarm import prewarm_municipality_dem

    try:
        prewarm_municipality_dem(db, codigo_ibge)
    except Exception as exc:
        logger.warning("Prewarm DEM %s antes da simulação falhou: %s", codigo_ibge, exc)


def prewarm_municipality_rainfall_compare(
    db: Session,
    codigo_ibge: str,
    baseline_mm: float = 80.0,
    scenario_mm: float = 120.0,
) -> dict[str, Any]:
    """Pré-aquece o par baseline+cenário usado na oficina (compare 80×120 mm)."""
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == ibge).first()
    if not muni:
        return {
            "codigo_ibge": ibge,
            "baseline_mm": baseline_mm,
            "scenario_mm": scenario_mm,
            "skipped": True,
            "reason": "municipio_nao_encontrado",
        }

    _ensure_dem_ready(db, ibge)
    result = compare_rainfall_cached(db, muni.id, ibge, baseline_mm, scenario_mm)
    return {
        "codigo_ibge": ibge,
        "baseline_mm": baseline_mm,
        "scenario_mm": scenario_mm,
        "from_cache": bool(result.get("from_cache")),
        "ok": True,
    }


def schedule_compare_prewarm(
    codigo_ibge: str,
    baseline_mm: float = 80.0,
    scenario_mm: float = 120.0,
) -> dict[str, Any]:
    """Dispara compare em background (idempotente por município+par de mm)."""
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    token = _compare_cache_key(ibge, baseline_mm, scenario_mm)
    with _prewarm_lock:
        if token in _compare_inflight:
            return {
                "codigo_ibge": ibge,
                "baseline_mm": baseline_mm,
                "scenario_mm": scenario_mm,
                "status": "already_running",
            }
        _compare_inflight.add(token)

    def _runner(
        code: str = ibge,
        base: float = baseline_mm,
        scen: float = scenario_mm,
        key: str = token,
    ) -> None:
        db = SessionLocal()
        try:
            outcome = prewarm_municipality_rainfall_compare(db, code, base, scen)
            logger.info("Prewarm compare %s %.0f×%.0fmm: %s", code, base, scen, outcome)
        except Exception as exc:
            logger.warning("Prewarm compare %s %.0f×%.0fmm falhou: %s", code, base, scen, exc)
        finally:
            db.close()
            with _prewarm_lock:
                _compare_inflight.discard(key)

    threading.Thread(
        target=_runner,
        daemon=True,
        name=f"prewarm-raincmp-{ibge}-{baseline_mm:.0f}x{scenario_mm:.0f}",
    ).start()
    return {
        "codigo_ibge": ibge,
        "baseline_mm": baseline_mm,
        "scenario_mm": scenario_mm,
        "status": "scheduled",
    }


def prewarm_municipality_rainfall(
    db: Session,
    codigo_ibge: str,
    precip_mm: float = 120.0,
) -> dict[str, Any]:
    """Calcula e grava no cache Redis a simulação pluvial do município."""
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == ibge).first()
    if not muni:
        return {"codigo_ibge": ibge, "precip_mm": precip_mm, "skipped": True, "reason": "municipio_nao_encontrado"}

    _ensure_dem_ready(db, ibge)
    result = run_rainfall_cached(db, muni.id, ibge, precip_mm)
    return {
        "codigo_ibge": ibge,
        "precip_mm": precip_mm,
        "from_cache": bool(result.get("from_cache")),
        "ok": True,
    }


def schedule_rainfall_prewarm(
    codigo_ibge: str,
    precip_mm: float = 120.0,
    *,
    extra_mm: list[float] | None = None,
) -> dict[str, Any]:
    """Dispara pré-aquecimento em background (idempotente por município+mm)."""
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    amounts = [precip_mm]
    if extra_mm:
        amounts.extend(extra_mm)
    unique_mm = []
    seen_mm: set[float] = set()
    for mm in amounts:
        if mm not in seen_mm:
            seen_mm.add(mm)
            unique_mm.append(mm)

    scheduled: list[dict[str, Any]] = []
    for mm in unique_mm:
        token = _cache_key(ibge, mm)
        with _prewarm_lock:
            if token in _prewarm_inflight:
                scheduled.append({"precip_mm": mm, "status": "already_running"})
                continue
            _prewarm_inflight.add(token)

        def _runner(code: str = ibge, amount: float = mm, key: str = token) -> None:
            db = SessionLocal()
            try:
                outcome = prewarm_municipality_rainfall(db, code, amount)
                logger.info("Prewarm simulação %s %.0fmm: %s", code, amount, outcome)
            except Exception as exc:
                logger.warning("Prewarm simulação %s %.0fmm falhou: %s", code, amount, exc)
            finally:
                db.close()
                with _prewarm_lock:
                    _prewarm_inflight.discard(key)

        threading.Thread(
            target=_runner,
            daemon=True,
            name=f"prewarm-rain-{ibge}-{mm:.0f}",
        ).start()
        scheduled.append({"precip_mm": mm, "status": "scheduled"})

    baseline_mm = float(getattr(settings, "SIMULATION_PREWARM_BASELINE_MM", 80.0))
    default_mm = float(getattr(settings, "SIMULATION_PREWARM_MM", 120.0))
    if baseline_mm in unique_mm and default_mm in unique_mm:
        schedule_compare_prewarm(ibge, baseline_mm, default_mm)

    return {"codigo_ibge": ibge, "scheduled": scheduled}


def prewarm_boot_priority_municipalities() -> None:
    """Pré-aquece cenários padrão dos municípios prioritários de boot."""
    default_mm = float(getattr(settings, "SIMULATION_PREWARM_MM", 120.0))
    baseline_mm = float(getattr(settings, "SIMULATION_PREWARM_BASELINE_MM", 80.0))
    for codigo in settings.BOOT_PRIORITY_IBGE_CODES:
        schedule_rainfall_prewarm(codigo, default_mm, extra_mm=[baseline_mm])
        schedule_compare_prewarm(codigo, baseline_mm, default_mm)
