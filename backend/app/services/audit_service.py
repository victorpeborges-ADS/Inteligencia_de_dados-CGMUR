"""Registro de auditoria institucional — Fase 4.6."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.security.auth import Role, User


def resolve_actor(request: Request | None, explicit: User | None = None) -> User:
    if explicit is not None:
        return explicit
    if request is not None:
        user = getattr(request.state, "user", None)
        if user is not None:
            return user
    from app.config import settings

    if not settings.AUTH_ENABLED:
        return User(username="dev", role=Role.ADMIN)
    return User(username="anonymous", role=Role.LEITOR)


def log_audit(
    db: Session,
    *,
    user: User,
    action: str,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    codigo_ibge: str | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    ip_address = None
    user_agent = None
    if request is not None:
        if request.client:
            ip_address = request.client.host
        user_agent = request.headers.get("user-agent")

    entry = AuditLog(
        username=user.username,
        role=user.role.value,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        codigo_ibge=codigo_ibge,
        metadata_json=metadata or {},
        ip_address=ip_address,
        user_agent=(user_agent[:512] if user_agent else None),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
