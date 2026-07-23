"""Relógio UTC único da aplicação (18a.4).

Substitui `datetime.utcnow()` (deprecated). Retorna instante UTC como
datetime *naive* para compatibilidade com colunas SQLAlchemy `DateTime`
sem `timezone=True` (Postgres TIMESTAMP WITHOUT TIME ZONE).
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """UTC agora (naive). Use em defaults SQLAlchemy e comparações com o banco."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_now_iso_z() -> str:
    """UTC agora em ISO-8601 com sufixo Z."""
    return utc_now().replace(microsecond=0).isoformat() + "Z"
