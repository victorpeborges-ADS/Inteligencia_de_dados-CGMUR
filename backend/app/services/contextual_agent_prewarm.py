"""Pré-aquecimento do bundle de contexto do agente Sinidu."""

from __future__ import annotations

import logging
import threading

from app.config import settings
from app.db import SessionLocal
from app.models import Municipio
from app.services.contextual_agent_cache import get_cached_bundle, get_cached_municipal_context, set_cached_bundle
from app.services.contextual_agent_service import build_municipio_data_bundle

logger = logging.getLogger(__name__)

_inflight: set[str] = set()
_lock = threading.Lock()


def prewarm_agent_bundle(codigo_ibge: str) -> None:
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    if get_cached_bundle(ibge) and get_cached_municipal_context(ibge):
        return
    with _lock:
        if ibge in _inflight:
            return
        _inflight.add(ibge)

    def _runner() -> None:
        db = SessionLocal()
        try:
            muni = db.query(Municipio).filter(Municipio.codigo_ibge == ibge).first()
            if not muni:
                return
            bundle = build_municipio_data_bundle(db, muni)
            set_cached_bundle(ibge, bundle)
            from app.services.municipal_assistant_context import build_municipal_assistant_context

            build_municipal_assistant_context(db, muni)
            logger.info("Bundle + contexto do agente pré-aquecidos: %s", ibge)
        except Exception as exc:
            logger.warning("Prewarm bundle agente %s falhou: %s", ibge, exc)
        finally:
            db.close()
            with _lock:
                _inflight.discard(ibge)

    threading.Thread(target=_runner, daemon=True, name=f"prewarm-agent-{ibge}").start()


def prewarm_boot_priority_agent_bundles() -> None:
    for codigo in settings.BOOT_PRIORITY_IBGE_CODES:
        prewarm_agent_bundle(codigo)
