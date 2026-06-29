"""Sincronização manual/agendada de OpenMeteo + CEMADEN."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.cemaden_monitor import emit_recent_alerts, sync_cemaden_alerts
from app.services.weather_monitor import sync_weather_for_municipalities

logger = logging.getLogger(__name__)


async def sync_monitoring_all(db: Session, codigos: list[str] | None = None) -> dict[str, Any]:
    """Executa ciclo completo: CEMADEN → OpenMeteo → broadcast WebSocket."""
    cemaden = sync_cemaden_alerts(db)
    weather = await sync_weather_for_municipalities(db, codigos)
    try:
        await emit_recent_alerts(db)
    except Exception as exc:
        logger.warning("Broadcast pós-sync falhou: %s", exc)
    return {
        "cemaden": cemaden,
        "weather": weather,
        "ok": True,
    }


def sync_monitoring_all_sync(db: Session, codigos: list[str] | None = None) -> dict[str, Any]:
    return asyncio.run(sync_monitoring_all(db, codigos))
