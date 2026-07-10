"""Pré-aquecimento do cache de simulação pluvial (demo Recife/Aracaju)."""

from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Municipio
from app.services.simulation_cache import run_rainfall_cached

logger = logging.getLogger(__name__)

_prewarm_lock = threading.Lock()
_prewarm_inflight: set[str] = set()


def _cache_key(codigo_ibge: str, precip_mm: float) -> str:
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    return f"{ibge}:{precip_mm:.1f}"


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

    return {"codigo_ibge": ibge, "scheduled": scheduled}


def prewarm_boot_priority_municipalities() -> None:
    """Pré-aquece cenários padrão dos municípios prioritários de boot."""
    default_mm = float(getattr(settings, "SIMULATION_PREWARM_MM", 120.0))
    baseline_mm = float(getattr(settings, "SIMULATION_PREWARM_BASELINE_MM", 80.0))
    for codigo in settings.BOOT_PRIORITY_IBGE_CODES:
        schedule_rainfall_prewarm(codigo, default_mm, extra_mm=[baseline_mm])
