"""Sincronização manual/agendada de OpenMeteo + CEMADEN."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.cemaden_monitor import emit_recent_alerts, sync_cemaden_alerts
from app.services.weather_monitor import sync_weather_for_municipalities

logger = logging.getLogger(__name__)


def _sync_cemaden_pluvio(db: Session, codigos: list[str] | None = None) -> dict[str, Any]:
    """Persiste snapshot de pluviômetros CEMADEN (getJson2) — Fase 21b.1."""
    try:
        from app.data_connectors.cemaden_pluvio_collector import (
            PILOT_UF_BY_IBGE,
            collect_cemaden_pluvio_municipality,
            collect_cemaden_pluvio_pilots,
        )

        if not codigos:
            return collect_cemaden_pluvio_pilots(db)

        results = []
        for code in codigos:
            c = str(code).zfill(7)[:7]
            if c not in PILOT_UF_BY_IBGE:
                # Ainda tenta se o município tiver UF no banco
                results.append(collect_cemaden_pluvio_municipality(db, c, use_api=True))
            else:
                results.append(collect_cemaden_pluvio_municipality(db, c, use_api=True))
        return {
            "municipios": results,
            "total_records": sum(int(r.get("records") or 0) for r in results),
        }
    except Exception as exc:
        logger.warning("CEMADEN pluvio sync falhou: %s", exc)
        return {"ok": False, "error": str(exc)[:200], "total_records": 0}


async def sync_monitoring_all(db: Session, codigos: list[str] | None = None) -> dict[str, Any]:
    """Executa ciclo completo: alertas CEMADEN → pluvio CEMADEN → OpenMeteo → WS."""
    cemaden = sync_cemaden_alerts(db)
    pluvio = _sync_cemaden_pluvio(db, codigos)
    weather = await sync_weather_for_municipalities(db, codigos)
    try:
        await emit_recent_alerts(db)
    except Exception as exc:
        logger.warning("Broadcast pós-sync falhou: %s", exc)
    return {
        "cemaden": cemaden,
        "cemaden_pluvio": pluvio,
        "weather": weather,
        "ok": True,
    }


def sync_monitoring_all_sync(db: Session, codigos: list[str] | None = None) -> dict[str, Any]:
    return asyncio.run(sync_monitoring_all(db, codigos))
