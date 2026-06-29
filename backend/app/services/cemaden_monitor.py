"""Coleta CEMADEN + alertas internos."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import AlertaCemaden, MonitoringAlert, Municipio
from app.services.alert_broadcaster import alert_manager

logger = logging.getLogger(__name__)

CEMADEN_URLS = [
    "https://www.cemaden.gov.br/mapainterativo/alertas.json",
]

NIVEL_MAP = {
    "MUITO_ALTO": "VERMELHO",
    "ALTO": "LARANJA",
    "MEDIO": "AMARELO",
    "BAIXO": "VERDE",
}


def _fetch_cemaden_remote() -> list[dict]:
    for url in CEMADEN_URLS:
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "Sinidu+Clima/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict):
                        return data.get("features") or data.get("alertas") or []
        except Exception as exc:
            logger.warning("CEMADEN fetch %s: %s", url, exc)
    return []


def sync_cemaden_alerts(db: Session) -> dict[str, Any]:
    remote = _fetch_cemaden_remote()
    created = 0
    municipios = {m.codigo_ibge: m for m in db.query(Municipio).all()}

    if remote:
        for item in remote[:200]:
            props = item.get("properties") or item
            ibge = str(props.get("codigo_ibge") or props.get("ibge") or "").zfill(7)[:7]
            if not ibge or ibge not in municipios:
                continue
            nivel_raw = str(props.get("nivel_alerta") or props.get("nivel") or "MEDIO").upper()
            nivel = NIVEL_MAP.get(nivel_raw, "AMARELO")
            muni = municipios[ibge]
            db.add(MonitoringAlert(
                municipio_id=muni.id,
                codigo_ibge=ibge,
                tipo="CEMADEN_ALERT",
                nivel=nivel,
                titulo=f"Alerta CEMADEN — {nivel_raw}",
                mensagem=props.get("descricao") or props.get("description"),
                payload=props,
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2),
            ))
            created += 1
            if nivel in ("LARANJA", "VERMELHO"):
                from app.services.gotify_notifier import push_risk_alert
                push_risk_alert(
                    muni.nome,
                    ibge,
                    nivel,
                    props.get("descricao") or props.get("description") or f"Alerta CEMADEN — {nivel_raw}",
                )
    else:
        for ac in db.query(AlertaCemaden).order_by(AlertaCemaden.data_alerta.desc()).limit(50):
            muni = db.query(Municipio).filter(Municipio.id == ac.municipio_id).first()
            if not muni:
                continue
            nivel = NIVEL_MAP.get(ac.nivel_alerta.upper(), "AMARELO")
            db.add(MonitoringAlert(
                municipio_id=muni.id,
                codigo_ibge=muni.codigo_ibge,
                tipo="CEMADEN_ALERT",
                nivel=nivel,
                titulo=f"Alerta CEMADEN — {ac.nivel_alerta}",
                mensagem=ac.descricao,
                payload={"nivel_alerta": ac.nivel_alerta, "fonte": "db_local"},
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=2),
            ))
            created += 1
            if nivel in ("LARANJA", "VERMELHO"):
                from app.services.gotify_notifier import push_risk_alert
                push_risk_alert(
                    muni.nome,
                    muni.codigo_ibge,
                    nivel,
                    ac.descricao or f"Alerta CEMADEN — {ac.nivel_alerta}",
                )

    db.commit()

    return {"created": created, "source": "remote" if remote else "local_db"}


async def emit_recent_alerts(db: Session, since_minutes: int = 35) -> int:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=since_minutes)
    rows = (
        db.query(MonitoringAlert)
        .filter(MonitoringAlert.created_at >= cutoff)
        .order_by(MonitoringAlert.created_at.desc())
        .limit(100)
        .all()
    )
    for row in rows:
        await alert_manager.broadcast(row.codigo_ibge, {
            "type": row.tipo,
            "data": {
                "id": row.id,
                "codigo_ibge": row.codigo_ibge,
                "nivel": row.nivel,
                "titulo": row.titulo,
                "mensagem": row.mensagem,
                "payload": row.payload,
                "created_at": row.created_at.isoformat(),
            },
        })
    return len(rows)
