"""Pré-aquecimento do DEM municipal antes da simulação pluvial (boot prioritário)."""

from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Municipio
from app.services.dem_processor import is_processed, process_municipality_dem

logger = logging.getLogger(__name__)

_prewarm_lock = threading.Lock()
_prewarm_inflight: set[str] = set()


def prewarm_municipality_dem(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Processa DEM se ainda não existir (LiDAR local → SRTM)."""
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    if not force and is_processed(ibge):
        return {
            "codigo_ibge": ibge,
            "skipped": True,
            "reason": "already_processed",
        }

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == ibge).first()
    if not muni:
        return {
            "codigo_ibge": ibge,
            "skipped": True,
            "reason": "municipio_nao_encontrado",
        }

    meta = process_municipality_dem(db, ibge, force=force)
    return {
        "codigo_ibge": ibge,
        "ok": True,
        "dem_source": meta.get("dem_source"),
        "dem_resolution_m": meta.get("dem_resolution_m"),
    }


def prewarm_boot_priority_dem(*, force: bool = False) -> list[dict[str, Any]]:
    """Processa DEM dos municípios de boot (síncrono — rodar em thread de background)."""
    db = SessionLocal()
    outcomes: list[dict[str, Any]] = []
    try:
        for codigo in settings.BOOT_PRIORITY_IBGE_CODES:
            try:
                outcome = prewarm_municipality_dem(db, codigo, force=force)
                outcomes.append(outcome)
                logger.info("Prewarm DEM %s: %s", codigo, outcome)
            except Exception as exc:
                logger.warning("Prewarm DEM %s falhou: %s", codigo, exc)
                outcomes.append({"codigo_ibge": codigo, "error": str(exc), "skipped": True})
    finally:
        db.close()
    return outcomes


def schedule_dem_prewarm(codigo_ibge: str, *, force: bool = False) -> dict[str, Any]:
    """Dispara processamento DEM em background (idempotente por município)."""
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    if not force and is_processed(ibge):
        return {"codigo_ibge": ibge, "status": "already_processed"}

    with _prewarm_lock:
        if ibge in _prewarm_inflight:
            return {"codigo_ibge": ibge, "status": "already_running"}
        _prewarm_inflight.add(ibge)

    def _runner(code: str = ibge, do_force: bool = force) -> None:
        db = SessionLocal()
        try:
            outcome = prewarm_municipality_dem(db, code, force=do_force)
            logger.info("Prewarm DEM agendado %s: %s", code, outcome)
        except Exception as exc:
            logger.warning("Prewarm DEM agendado %s falhou: %s", code, exc)
        finally:
            db.close()
            with _prewarm_lock:
                _prewarm_inflight.discard(code)

    threading.Thread(
        target=_runner,
        daemon=True,
        name=f"prewarm-dem-{ibge}",
    ).start()
    return {"codigo_ibge": ibge, "status": "scheduled"}


def prewarm_boot_priority_dem_async() -> None:
    """Agenda DEM dos municípios prioritários de boot."""
    for codigo in settings.BOOT_PRIORITY_IBGE_CODES:
        schedule_dem_prewarm(codigo)
