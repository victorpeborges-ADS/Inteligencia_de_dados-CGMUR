"""Previsão OpenMeteo + cruzamento com risco de inundação."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import MonitoringAlert, Municipio, WeatherForecastCache
from app.services.alert_broadcaster import alert_manager

logger = logging.getLogger(__name__)

OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"
RISK_THRESHOLD = 0.7
PRECIP_ALERT_MM = 80.0


def _muni_centroid(muni: Municipio) -> tuple[float, float]:
    if muni.geom is not None:
        from geoalchemy2.shape import to_shape
        c = to_shape(muni.geom).centroid
        return c.y, c.x
    return -8.047, -34.877


def fetch_openmeteo(lat: float, lng: float) -> dict[str, Any]:
    params = {
        "latitude": lat,
        "longitude": lng,
        "hourly": "precipitation",
        "forecast_days": 3,
        "timezone": "America/Sao_Paulo",
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(OPENMETEO_URL, params=params)
        resp.raise_for_status()
        return resp.json()


def _precip_sums(data: dict) -> tuple[float, float]:
    precips = data.get("hourly", {}).get("precipitation") or []
    p24 = sum(float(p or 0) for p in precips[:24])
    p72 = sum(float(p or 0) for p in precips[:72])
    return p24, p72


def _risk_probability(precip_24h: float) -> float:
    if precip_24h <= 20:
        return 0.15
    if precip_24h <= 50:
        return 0.35 + (precip_24h - 20) / 100
    if precip_24h <= 100:
        return 0.55 + (precip_24h - 50) / 120
    return min(0.95, 0.75 + (precip_24h - 100) / 200)


async def _emit_proactive_risk_events(
    muni: Municipio,
    prev_risk: float,
    risk: float,
    p24: float,
    p72: float,
) -> None:
    """Dispara eventos proativos quando probabilidade cruza limiares 30/50/75%."""
    tiers = [
        (0.30, "WARN", "Probabilidade de evento crítico acima de 30% — reforçar monitoramento."),
        (0.50, "ORANGE", "Probabilidade acima de 50% — considere abrir o módulo de Contingência."),
        (0.75, "CRITICAL", "Probabilidade acima de 75% — ative protocolo de resposta imediata."),
    ]
    for threshold, tier, msg in tiers:
        if prev_risk < threshold <= risk:
            await alert_manager.broadcast(muni.codigo_ibge, {
                "type": "PROACTIVE_RISK",
                "data": {
                    "codigo_ibge": muni.codigo_ibge,
                    "tier": tier,
                    "threshold": threshold,
                    "risk_probability": round(risk, 3),
                    "precip_24h_mm": round(p24, 1),
                    "precip_72h_mm": round(p72, 1),
                    "mensagem": msg,
                    "nivel_sugerido": "LARANJA" if tier in ("ORANGE", "CRITICAL") else "AMARELO",
                },
            })


async def sync_weather_for_municipalities(db: Session, codigos: list[str] | None = None) -> dict:
    query = db.query(Municipio)
    if codigos:
        query = query.filter(Municipio.codigo_ibge.in_(codigos))
    municipios = query.limit(80).all()

    updated = 0
    alerts_created = 0

    for muni in municipios:
        lat, lng = _muni_centroid(muni)
        try:
            raw = fetch_openmeteo(lat, lng)
        except Exception as exc:
            logger.warning("OpenMeteo %s: %s", muni.codigo_ibge, exc)
            continue

        p24, p72 = _precip_sums(raw)
        risk = _risk_probability(p24)

        prev = (
            db.query(WeatherForecastCache)
            .filter(WeatherForecastCache.codigo_ibge == muni.codigo_ibge)
            .order_by(WeatherForecastCache.fetched_at.desc())
            .first()
        )
        prev_risk = float(prev.risk_probability) if prev else 0.0

        db.add(WeatherForecastCache(
            codigo_ibge=muni.codigo_ibge,
            lat=lat,
            lng=lng,
            precip_24h_mm=p24,
            precip_72h_mm=p72,
            risk_probability=risk,
            raw_payload=raw,
        ))
        updated += 1

        await alert_manager.broadcast(muni.codigo_ibge, {
            "type": "WEATHER_UPDATE",
            "data": {
                "codigo_ibge": muni.codigo_ibge,
                "precip_24h_mm": round(p24, 1),
                "precip_72h_mm": round(p72, 1),
                "risk_probability": round(risk, 3),
            },
        })

        await _emit_proactive_risk_events(muni, prev_risk, risk, p24, p72)

        if risk >= RISK_THRESHOLD or p24 >= PRECIP_ALERT_MM:
            nivel = "VERMELHO" if risk >= 0.85 else "LARANJA"
            db.add(MonitoringAlert(
                municipio_id=muni.id,
                codigo_ibge=muni.codigo_ibge,
                tipo="RISK_THRESHOLD",
                nivel=nivel,
                titulo=f"Risco hidrológico elevado — {nivel}",
                mensagem=f"Precipitação prevista 24h: {p24:.0f} mm · prob.: {risk:.0%}",
                payload={"precip_24h_mm": p24, "risk_probability": risk},
                expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=24),
            ))
            alerts_created += 1
            await alert_manager.broadcast(muni.codigo_ibge, {
                "type": "RISK_THRESHOLD",
                "data": {
                    "codigo_ibge": muni.codigo_ibge,
                    "nivel": nivel,
                    "risk_probability": risk,
                    "precip_24h_mm": round(p24, 1),
                },
            })
            if nivel in ("LARANJA", "VERMELHO"):
                from app.services.gotify_notifier import push_risk_alert
                push_risk_alert(
                    muni.nome,
                    muni.codigo_ibge,
                    nivel,
                    f"Precip. 24h: {p24:.0f} mm · probabilidade: {risk:.0%}",
                )

    db.commit()
    return {"updated": updated, "alerts_created": alerts_created}


def cleanup_old_records(db: Session, days: int = 7) -> dict:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    alerts_del = db.query(MonitoringAlert).filter(MonitoringAlert.created_at < cutoff).delete()
    weather_del = db.query(WeatherForecastCache).filter(WeatherForecastCache.fetched_at < cutoff).delete()
    db.commit()
    return {"alerts_deleted": alerts_del, "weather_deleted": weather_del}
