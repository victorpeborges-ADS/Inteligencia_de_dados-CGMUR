"""Nível de alerta vivo (CEMADEN / monitoramento) para contingência e dashboard."""

from __future__ import annotations

from app.timeutil import utc_now
import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AlertaCemaden, MonitoringAlert, Municipio

NIVEL_ORDER = {"VERDE": 0, "AMARELO": 1, "LARANJA": 2, "VERMELHO": 3}
VALID_NIVEIS = set(NIVEL_ORDER)


def normalize_nivel(value: str | None, *, default: str = "VERDE") -> str:
    nivel = str(value or default).strip().upper()
    return nivel if nivel in VALID_NIVEIS else default


def max_alert_level(niveis: list[str], *, default: str = "VERDE") -> str:
    best = normalize_nivel(default)
    for raw in niveis:
        nivel = normalize_nivel(raw, default=best)
        if NIVEL_ORDER[nivel] > NIVEL_ORDER[best]:
            best = nivel
    return best


def live_alert_snapshot(db: Session, codigo_ibge: str, *, hours: int = 24) -> dict[str, Any]:
    """Consolida nível máximo e contagens de alertas das últimas N horas."""
    code = str(codigo_ibge).zfill(7)[:7]
    since = utc_now() - datetime.timedelta(hours=max(1, hours))
    alerts = (
        db.query(MonitoringAlert)
        .filter(MonitoringAlert.codigo_ibge == code, MonitoringAlert.created_at >= since)
        .order_by(MonitoringAlert.created_at.desc())
        .limit(50)
        .all()
    )
    cemaden = [a for a in alerts if a.tipo == "CEMADEN_ALERT"]
    risk = [a for a in alerts if a.tipo == "RISK_THRESHOLD"]
    nivel = max_alert_level([a.nivel for a in alerts])

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    camada_cemaden = 0
    if muni:
        camada_cemaden = (
            db.query(AlertaCemaden)
            .filter(AlertaCemaden.municipio_id == muni.id)
            .count()
        )

    fonte = "monitoramento"
    if cemaden:
        fonte = "cemaden"
    elif risk:
        fonte = "risco_interno"
    elif camada_cemaden and nivel == "VERDE":
        fonte = "camada_cemaden_sem_alerta_24h"

    return {
        "codigo_ibge": code,
        "nivel_alerta": nivel,
        "cemaden_ativos_24h": len(cemaden),
        "alertas_risco_24h": len(risk),
        "alertas_total_24h": len(alerts),
        "camada_cemaden_count": camada_cemaden,
        "fonte": fonte,
        "vivo": nivel != "VERDE" or len(cemaden) > 0,
        "titulo_recente": alerts[0].titulo if alerts else None,
    }
