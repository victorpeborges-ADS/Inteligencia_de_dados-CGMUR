"""Consulta de trilha de auditoria — acesso restrito a admin."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog
from app.security.auth import Role, User, require_role

router = APIRouter()


class AuditLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    action: str
    resource_type: str | None
    resource_id: str | None
    codigo_ibge: str | None
    metadata: dict
    ip_address: str | None
    created_at: datetime


@router.get("", response_model=list[AuditLogItem])
def list_audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    codigo_ibge: str | None = Query(default=None),
    username: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.ADMIN)),
):
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.filter(AuditLog.action == action)
    if codigo_ibge:
        query = query.filter(AuditLog.codigo_ibge == codigo_ibge)
    if username:
        query = query.filter(AuditLog.username == username)

    rows = query.offset(offset).limit(limit).all()
    return [
        AuditLogItem(
            id=row.id,
            username=row.username,
            role=row.role,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            codigo_ibge=row.codigo_ibge,
            metadata=row.metadata_json or {},
            ip_address=row.ip_address,
            created_at=row.created_at,
        )
        for row in rows
    ]
