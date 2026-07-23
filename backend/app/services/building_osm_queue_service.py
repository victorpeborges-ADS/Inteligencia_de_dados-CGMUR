"""Fila de ingestão OSM (footprints) com limite e backoff (18c.2).

Evita martelar o Overpass: um município por vez, intervalo mínimo entre
chamadas, e reenfileira itens com `rate_limited`.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections import deque
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Edificacao, Municipio
from app.timeutil import utc_now, utc_now_iso_z

logger = logging.getLogger(__name__)

# Intervalo mínimo entre consultas Overpass (segundos)
MIN_INTERVAL_S = float(os.getenv("OSM_QUEUE_MIN_INTERVAL_S", "12") or 12)
MAX_QUEUE = 80

_lock = threading.Lock()
_queue: deque[dict[str, Any]] = deque()
_history: deque[dict[str, Any]] = deque(maxlen=40)
_last_overpass_at = 0.0
_processing = False


def queue_status() -> dict[str, Any]:
    with _lock:
        pending = [dict(item) for item in _queue]
        hist = list(_history)
        processing = _processing
    return {
        "pending": len(pending),
        "processing": processing,
        "items": pending[:30],
        "recent": hist[:15],
        "min_interval_s": MIN_INTERVAL_S,
        "max_queue": MAX_QUEUE,
        "versao": "18c.2",
    }


def enqueue_buildings(
    codigo_ibge: str,
    *,
    force: bool = False,
    priority: int = 100,
) -> dict[str, Any]:
    """Enfileira município para ingestão OSM. Deduplica por código."""
    code = str(codigo_ibge).strip().zfill(7)[:7]
    if not code.isdigit() or len(code) != 7:
        raise ValueError("Código IBGE inválido")

    with _lock:
        for item in _queue:
            if item["codigo_ibge"] == code:
                item["force"] = item["force"] or force
                item["priority"] = min(int(item.get("priority", 100)), priority)
                return {"enqueued": False, "reason": "already_queued", "item": dict(item)}

        if len(_queue) >= MAX_QUEUE:
            raise ValueError(f"Fila cheia (máx. {MAX_QUEUE}). Aguarde o processamento.")

        item = {
            "id": str(uuid.uuid4())[:8],
            "codigo_ibge": code,
            "force": force,
            "priority": priority,
            "enqueued_at": utc_now_iso_z(),
            "attempts": 0,
        }
        _queue.append(item)
        # reordenar por prioridade
        ordered = sorted(_queue, key=lambda x: (int(x.get("priority", 100)), x["enqueued_at"]))
        _queue.clear()
        _queue.extend(ordered)
        return {"enqueued": True, "item": dict(item), "pending": len(_queue)}


def enqueue_many(
    codigos: list[str],
    *,
    force: bool = False,
) -> dict[str, Any]:
    added = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    for code in codigos:
        try:
            out = enqueue_buildings(code, force=force)
            if out.get("enqueued"):
                added += 1
            else:
                skipped += 1
        except ValueError as exc:
            errors.append({"codigo_ibge": str(code), "error": str(exc)})
    return {
        "requested": len(codigos),
        "added": added,
        "skipped": skipped,
        "errors": errors,
        "queue": queue_status(),
    }


def enqueue_uf(uf: str, *, limit: int = 15, force: bool = False) -> dict[str, Any]:
    """Enfileira municípios da UF que já existem no PostGIS (bootstrap prévio)."""
    from app.services.uf_bootstrap_service import normalize_uf

    uf_code = normalize_uf(uf)
    limit = max(1, min(int(limit), 40))
    db = SessionLocal()
    try:
        rows = (
            db.query(Municipio.codigo_ibge)
            .filter(Municipio.uf == uf_code)
            .order_by(Municipio.nome.asc())
            .limit(limit * 3)
            .all()
        )
        codes: list[str] = []
        for (code,) in rows:
            if force:
                codes.append(code)
                continue
            muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
            if not muni:
                continue
            n = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
            if n == 0:
                codes.append(code)
            if len(codes) >= limit:
                break
        result = enqueue_many(codes, force=force)
        result["uf"] = uf_code
        return result
    finally:
        db.close()


def _wait_rate_limit() -> None:
    global _last_overpass_at
    now = time.monotonic()
    with _lock:
        elapsed = now - _last_overpass_at
        wait = max(0.0, MIN_INTERVAL_S - elapsed)
    if wait > 0:
        time.sleep(wait)


def process_next(db: Session | None = None) -> dict[str, Any] | None:
    """Processa o próximo item da fila. Retorna None se fila vazia."""
    global _last_overpass_at, _processing

    with _lock:
        if not _queue:
            return None
        if _processing:
            return {"status": "busy"}
        item = _queue.popleft()
        _processing = True

    own_session = db is None
    session = db or SessionLocal()
    result: dict[str, Any] = {
        "status": "failed",
        "codigo_ibge": item["codigo_ibge"],
        "error": "unknown",
    }
    try:
        _wait_rate_limit()
        from app.data_connectors.building_footprints_collector import (
            OverpassRateLimitError,
            collect_buildings_municipality,
        )
        from app.services.building_tiles_api_service import invalidate_gemeo_tile_cache

        item["attempts"] = int(item.get("attempts") or 0) + 1
        try:
            out = collect_buildings_municipality(
                session,
                item["codigo_ibge"],
                force=bool(item.get("force")),
            )
            with _lock:
                _last_overpass_at = time.monotonic()

            if out.get("status") == "rate_limited" or out.get("retryable"):
                item["priority"] = int(item.get("priority", 100)) + 50
                if item["attempts"] < 5:
                    with _lock:
                        _queue.append(item)
                    result = {
                        "status": "requeued",
                        "codigo_ibge": item["codigo_ibge"],
                        "attempts": item["attempts"],
                        "detail": out.get("error"),
                    }
                else:
                    result = {
                        "status": "failed",
                        "codigo_ibge": item["codigo_ibge"],
                        "error": out.get("error") or "rate_limited",
                        "attempts": item["attempts"],
                    }
            else:
                try:
                    invalidate_gemeo_tile_cache(item["codigo_ibge"])
                except Exception:
                    pass
                result = {
                    "status": out.get("status") or "ok",
                    "codigo_ibge": item["codigo_ibge"],
                    "count": out.get("count"),
                    "fonte": out.get("fonte"),
                    "attempts": item["attempts"],
                    "finished_at": utc_now_iso_z(),
                }
        except OverpassRateLimitError as exc:
            item["priority"] = int(item.get("priority", 100)) + 50
            if item["attempts"] < 5:
                with _lock:
                    _queue.append(item)
                result = {
                    "status": "requeued",
                    "codigo_ibge": item["codigo_ibge"],
                    "attempts": item["attempts"],
                    "detail": str(exc),
                }
            else:
                result = {
                    "status": "failed",
                    "codigo_ibge": item["codigo_ibge"],
                    "error": str(exc),
                    "attempts": item["attempts"],
                }
        except Exception as exc:
            logger.exception("Fila OSM falhou %s", item["codigo_ibge"])
            result = {
                "status": "failed",
                "codigo_ibge": item["codigo_ibge"],
                "error": str(exc),
                "attempts": item["attempts"],
            }
    finally:
        with _lock:
            _processing = False
            _history.appendleft(result)
        if own_session:
            session.close()

    return result


def drain_queue(*, max_items: int = 20) -> dict[str, Any]:
    """Processa até max_items da fila (para job background)."""
    max_items = max(1, min(int(max_items), 40))
    results: list[dict[str, Any]] = []
    db = SessionLocal()
    try:
        for _ in range(max_items):
            with _lock:
                empty = len(_queue) == 0
            if empty:
                break
            out = process_next(db)
            if out is None:
                break
            if out.get("status") == "busy":
                time.sleep(1)
                continue
            results.append(out)
        return {
            "processed": len(results),
            "ok": sum(1 for r in results if r.get("status") in ("ok", "cached")),
            "requeued": sum(1 for r in results if r.get("status") == "requeued"),
            "failed": sum(1 for r in results if r.get("status") == "failed"),
            "results": results,
            "queue": queue_status(),
            "finished_at": utc_now().isoformat() + "Z",
            "versao": "18c.2",
        }
    finally:
        db.close()
