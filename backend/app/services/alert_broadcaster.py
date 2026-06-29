"""Broadcast de alertas via WebSocket (FastAPI nativo)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class AlertConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, codigo_ibge: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(codigo_ibge, set()).add(websocket)
        logger.info("WS conectado: %s (%d)", codigo_ibge, len(self._connections.get(codigo_ibge, [])))

    async def disconnect(self, codigo_ibge: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(codigo_ibge)
            if conns and websocket in conns:
                conns.discard(websocket)
            if conns is not None and len(conns) == 0:
                self._connections.pop(codigo_ibge, None)

    async def broadcast(self, codigo_ibge: str, event: dict[str, Any]) -> None:
        payload = json.dumps(event, default=str)
        async with self._lock:
            targets = list(self._connections.get(codigo_ibge, set()))
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(codigo_ibge, ws)


alert_manager = AlertConnectionManager()
