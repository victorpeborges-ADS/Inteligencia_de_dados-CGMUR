"""Previsão OpenMeteo + cruzamento com risco de inundação (Fase 21a)."""

from __future__ import annotations

from app.timeutil import utc_now
import datetime
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import (
    MonitoringAlert,
    MonitoringAlertArchive,
    Municipio,
    PrevisaoVerificacao,
    SeriePluviometricaObservada,
    WeatherForecastArchive,
    WeatherForecastCache,
)
from app.services.alert_broadcaster import alert_manager
from app.services.forecast_source_seal import build_forecast_seal

logger = logging.getLogger(__name__)

OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"
RISK_THRESHOLD = 0.7
PRECIP_ALERT_MM = 80.0
HOT_RETENTION_DAYS = 7


def _muni_centroid(muni: Municipio) -> tuple[float, float]:
    if muni.geom is not None:
        from geoalchemy2.shape import to_shape
        c = to_shape(muni.geom).centroid
        return c.y, c.x
    return -8.047, -34.877


def fetch_openmeteo(lat: float, lng: float) -> dict[str, Any]:
    """Forecast + 30 dias passados para alinhar precip_5/10/30d com o treino ML."""
    params = {
        "latitude": lat,
        "longitude": lng,
        "hourly": "precipitation,temperature_2m",
        "forecast_days": 3,
        "past_days": 30,
        "timezone": "America/Sao_Paulo",
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(OPENMETEO_URL, params=params)
        resp.raise_for_status()
        return resp.json()


def _precip_windows(data: dict) -> dict[str, float]:
    """Acumulados alinhados ao treino: 24/48/72h à frente + antecedentes 5/7/10/30d."""
    hourly = data.get("hourly") or {}
    precips = [float(p or 0) for p in (hourly.get("precipitation") or [])]
    times = hourly.get("time") or []

    # OpenMeteo com past_days=30: primeiras 720 h = passado; restante = forecast.
    past_hours = 30 * 24
    if len(precips) <= past_hours:
        # Fallback se a API não devolver past_days (ou só 7d)
        if len(precips) > 7 * 24:
            past = precips[: 7 * 24]
            forecast = precips[7 * 24 :]
        else:
            forecast = precips
            past = []
    else:
        past = precips[:past_hours]
        forecast = precips[past_hours:]

    def _sum(series: list[float], n: int) -> float:
        return float(sum(series[:n])) if series else 0.0

    def _sum_tail(series: list[float], n: int) -> float:
        if not series:
            return 0.0
        return float(sum(series[-n:])) if len(series) >= n else float(sum(series))

    p24 = _sum(forecast, 24)
    p48 = _sum(forecast, 48)
    p72 = _sum(forecast, 72)
    p5d = _sum_tail(past, 5 * 24)
    p7d = _sum_tail(past, 7 * 24) if past else _sum(precips, min(len(precips), 168))
    p10d = _sum_tail(past, 10 * 24)
    p30d = float(sum(past)) if past else p7d

    return {
        "precip_24h": round(p24, 2),
        "precip_48h": round(p48, 2),
        "precip_72h": round(p72, 2),
        "precip_5d": round(p5d, 2),
        "precip_7d": round(p7d, 2),
        "precip_10d": round(p10d, 2),
        "precip_30d": round(p30d, 2),
        "forecast_hours": len(forecast),
        "past_hours": len(past),
        "time_points": len(times),
    }


def _precip_sums(data: dict) -> tuple[float, float]:
    """Compat: (p24, p72) — preferir `_precip_windows`."""
    w = _precip_windows(data)
    return w["precip_24h"], w["precip_72h"]


def cemaden_observed_precip_mm(db: Session, codigo_ibge: str) -> dict[str, float | None]:
    """Máximo recente de precipitação CEMADEN persistida para o município."""
    code = str(codigo_ibge).zfill(7)[:7]
    cutoff = utc_now() - datetime.timedelta(hours=36)
    rows = (
        db.query(SeriePluviometricaObservada)
        .filter(
            SeriePluviometricaObservada.codigo_ibge == code,
            SeriePluviometricaObservada.fonte == "cemaden",
            SeriePluviometricaObservada.observed_at >= cutoff,
        )
        .all()
    )
    if not rows:
        return {"obs_mm": None, "n_estacoes": 0}
    vals = [float(r.precip_mm or 0) for r in rows]
    return {
        "obs_mm": round(max(vals), 2) if vals else None,
        "n_estacoes": len(rows),
        "obs_mean_mm": round(sum(vals) / len(vals), 2) if vals else None,
    }


def _risk_probability(precip_24h: float) -> float:
    """Score heurístico de chuva (não é probabilidade calibrada)."""
    if precip_24h <= 20:
        return 0.15
    if precip_24h <= 50:
        return 0.35 + (precip_24h - 20) / 100
    if precip_24h <= 100:
        return 0.55 + (precip_24h - 50) / 120
    return min(0.95, 0.75 + (precip_24h - 100) / 200)


def resolve_risk_probability(
    db: Session,
    codigo_ibge: str,
    precip_24h: float,
    precip_72h: float,
    *,
    precip_48h: float | None = None,
    precip_7d: float | None = None,
    precip_5d: float | None = None,
    precip_10d: float | None = None,
    precip_30d: float | None = None,
) -> tuple[float, str]:
    """ML só se model_kind=full; senão score heurístico de precipitação (21a.1)."""
    heuristic = _risk_probability(float(precip_24h))
    try:
        from ml.model_policy import production_model_ready
        from ml.paths import model_path
        from ml.predictor import predictor

        code = str(codigo_ibge).zfill(7)[:7]
        # Só tenta ML se já existir artefato full — não bootstrapa baseline sintético.
        if not model_path(code).exists() or not production_model_ready(code):
            return heuristic, "precip_curve"

        p48 = float(precip_48h) if precip_48h is not None else (float(precip_24h) + float(precip_72h)) / 2.0
        # Nota: p48 acima só como último recurso; o sync sempre passa p48 real.
        out = predictor.predict(
            db,
            code,
            float(precip_24h),
            p48,
            float(precip_72h),
            precip_7d=precip_7d,
            precip_5d=precip_5d,
            precip_10d=precip_10d,
            precip_30d=precip_30d,
        )
        if out.get("model_kind") != "full" or not out.get("production_ready"):
            return heuristic, "precip_curve"
        return float(out["risk_probability"]), "ml_full"
    except Exception as exc:
        logger.info("ML risk fallback %s: %s", codigo_ibge, exc)
    return heuristic, "precip_curve"


def _score_label(risk_source: str) -> str:
    if risk_source == "ml_full":
        return "probabilidade_modelo"
    return "score_heuristico_chuva"


async def _emit_proactive_risk_events(
    muni: Municipio,
    prev_risk: float,
    risk: float,
    p24: float,
    p72: float,
    risk_source: str,
) -> None:
    """Dispara eventos proativos quando o score cruza limiares 30/50/75%."""
    label = "probabilidade" if risk_source == "ml_full" else "score heurístico"
    tiers = [
        (0.30, "WARN", f"{label.capitalize()} de evento crítico acima de 30% — reforçar monitoramento."),
        (0.50, "ORANGE", f"{label.capitalize()} acima de 50% — considere abrir o módulo de Contingência."),
        (0.75, "CRITICAL", f"{label.capitalize()} acima de 75% — ative protocolo de resposta imediata."),
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
                    "risk_source": risk_source,
                    "score_kind": _score_label(risk_source),
                    "precip_24h_mm": round(p24, 1),
                    "precip_72h_mm": round(p72, 1),
                    "mensagem": msg,
                    "nivel_sugerido": "LARANJA" if tier in ("ORANGE", "CRITICAL") else "AMARELO",
                },
            })


def _record_previsao_verificacao(
    db: Session,
    muni: Municipio,
    windows: dict[str, float],
    risk: float,
    risk_source: str,
) -> None:
    """Grava o que foi previsto agora; desfecho preenchido depois (21a.4 / 21g)."""
    db.add(
        PrevisaoVerificacao(
            codigo_ibge=muni.codigo_ibge,
            municipio_id=muni.id,
            previsto_em=utc_now(),
            horizonte_h=24,
            precip_24h_mm=windows["precip_24h"],
            precip_48h_mm=windows["precip_48h"],
            precip_72h_mm=windows["precip_72h"],
            precip_7d_mm=windows["precip_7d"],
            risk_score=risk,
            risk_source=risk_source,
            score_kind=_score_label(risk_source),
            model_kind="full" if risk_source == "ml_full" else None,
            desfecho_ocorrido=None,
            payload={
                "forecast_hours": windows.get("forecast_hours"),
                "past_hours": windows.get("past_hours"),
            },
        )
    )


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

        windows = _precip_windows(raw)
        p24 = windows["precip_24h"]
        p48 = windows["precip_48h"]
        p72 = windows["precip_72h"]
        p5d = windows.get("precip_5d", 0.0)
        p7d = windows["precip_7d"]
        p10d = windows.get("precip_10d", 0.0)
        p30d = windows.get("precip_30d", 0.0)

        # Se houver chuva observada CEMADEN maior que a previsão, usa o observado no score
        cem = cemaden_observed_precip_mm(db, muni.codigo_ibge)
        obs = cem.get("obs_mm")
        precip_for_risk = p24
        if obs is not None and float(obs) > float(p24):
            precip_for_risk = float(obs)

        risk, risk_source = resolve_risk_probability(
            db,
            muni.codigo_ibge,
            precip_for_risk,
            p72,
            precip_48h=p48,
            precip_7d=p7d,
            precip_5d=p5d,
            precip_10d=p10d,
            precip_30d=p30d,
        )

        prev = (
            db.query(WeatherForecastCache)
            .filter(WeatherForecastCache.codigo_ibge == muni.codigo_ibge)
            .order_by(WeatherForecastCache.fetched_at.desc())
            .first()
        )
        prev_risk = float(prev.risk_probability) if prev else 0.0

        payload = dict(raw) if isinstance(raw, dict) else {"openmeteo": raw}
        payload["_risk_source"] = risk_source
        payload["_score_kind"] = _score_label(risk_source)
        payload["_precip_windows"] = {
            "precip_24h": p24,
            "precip_48h": p48,
            "precip_72h": p72,
            "precip_5d": p5d,
            "precip_7d": p7d,
            "precip_10d": p10d,
            "precip_30d": p30d,
            "precip_for_risk_mm": precip_for_risk,
            "cemaden_obs_mm": obs,
            "cemaden_estacoes": cem.get("n_estacoes"),
        }
        seal = build_forecast_seal(
            risk_source=risk_source,
            precip_forecast_mm=p24,
            precip_for_risk_mm=precip_for_risk,
            cemaden_obs_mm=obs,
            cemaden_estacoes=cem.get("n_estacoes"),
        )
        payload["_selo_previsao"] = seal

        db.add(WeatherForecastCache(
            codigo_ibge=muni.codigo_ibge,
            lat=lat,
            lng=lng,
            precip_24h_mm=p24,
            precip_72h_mm=p72,
            risk_probability=risk,
            raw_payload=payload,
        ))
        updated += 1

        _record_previsao_verificacao(db, muni, windows, risk, risk_source)

        await alert_manager.broadcast(muni.codigo_ibge, {
            "type": "WEATHER_UPDATE",
            "data": {
                "codigo_ibge": muni.codigo_ibge,
                "precip_24h_mm": round(p24, 1),
                "precip_72h_mm": round(p72, 1),
                "risk_probability": round(risk, 3),
                "risk_source": risk_source,
                "score_kind": seal["score_kind"],
                "selo_previsao": seal,
            },
        })

        await _emit_proactive_risk_events(muni, prev_risk, risk, p24, p72, risk_source)

        if risk >= RISK_THRESHOLD or p24 >= PRECIP_ALERT_MM or precip_for_risk >= PRECIP_ALERT_MM:
            nivel = "VERMELHO" if risk >= 0.85 else "LARANJA"
            chuva_txt = (
                f"Chuva observada CEMADEN 24h: {obs:.0f} mm (previsão OpenMeteo: {p24:.0f} mm)"
                if seal.get("usou_chuva_observada") and obs is not None
                else f"Precipitação prevista 24h (OpenMeteo): {p24:.0f} mm"
            )
            db.add(MonitoringAlert(
                municipio_id=muni.id,
                codigo_ibge=muni.codigo_ibge,
                tipo="RISK_THRESHOLD",
                nivel=nivel,
                titulo=f"Risco hidrológico elevado — {nivel}",
                mensagem=(
                    f"{chuva_txt} · {seal['label_ui']}: {risk:.0%} — {seal['narrativa']}"
                ),
                payload={
                    "precip_24h_mm": p24,
                    "precip_for_risk_mm": precip_for_risk,
                    "risk_probability": risk,
                    "risk_source": risk_source,
                    "score_kind": seal["score_kind"],
                    "selo_previsao": seal,
                },
                expires_at=utc_now() + datetime.timedelta(hours=24),
            ))
            alerts_created += 1
            await alert_manager.broadcast(muni.codigo_ibge, {
                "type": "RISK_THRESHOLD",
                "data": {
                    "codigo_ibge": muni.codigo_ibge,
                    "nivel": nivel,
                    "risk_probability": risk,
                    "risk_source": risk_source,
                    "precip_24h_mm": round(p24, 1),
                    "selo_previsao": seal,
                },
            })
            if nivel in ("LARANJA", "VERMELHO"):
                from app.services.gotify_notifier import push_risk_alert
                push_risk_alert(
                    muni.nome,
                    muni.codigo_ibge,
                    nivel,
                    f"{chuva_txt} · {seal['label_ui']}: {risk:.0%}",
                )

    db.commit()

    # 21g.1 — fecha desfechos cujo horizonte já passou (piloto + escopo do sync)
    try:
        from app.services.previsao_verificacao_service import backfill_desfechos

        if codigos and len(codigos) == 1:
            backfill_desfechos(db, codigos[0])
        else:
            backfill_desfechos(db)
    except Exception as exc:
        logger.info("backfill desfechos pós-sync: %s", exc)

    return {"updated": updated, "alerts_created": alerts_created}


def cleanup_old_records(db: Session, days: int = HOT_RETENTION_DAYS) -> dict:
    """Arquiva registros > N dias (não apaga — Fase 21a.3)."""
    cutoff = utc_now() - datetime.timedelta(days=days)
    archived_at = utc_now()

    old_alerts = (
        db.query(MonitoringAlert)
        .filter(MonitoringAlert.created_at < cutoff)
        .limit(5000)
        .all()
    )
    alerts_moved = 0
    for a in old_alerts:
        db.add(
            MonitoringAlertArchive(
                original_id=a.id,
                municipio_id=a.municipio_id,
                codigo_ibge=a.codigo_ibge,
                tipo=a.tipo,
                nivel=a.nivel,
                titulo=a.titulo,
                mensagem=a.mensagem,
                payload=a.payload,
                created_at=a.created_at,
                expires_at=a.expires_at,
                archived_at=archived_at,
            )
        )
        db.delete(a)
        alerts_moved += 1

    old_weather = (
        db.query(WeatherForecastCache)
        .filter(WeatherForecastCache.fetched_at < cutoff)
        .limit(5000)
        .all()
    )
    weather_moved = 0
    for w in old_weather:
        db.add(
            WeatherForecastArchive(
                original_id=w.id,
                codigo_ibge=w.codigo_ibge,
                lat=w.lat,
                lng=w.lng,
                precip_24h_mm=w.precip_24h_mm,
                precip_72h_mm=w.precip_72h_mm,
                risk_probability=w.risk_probability,
                raw_payload=w.raw_payload,
                fetched_at=w.fetched_at,
                archived_at=archived_at,
            )
        )
        db.delete(w)
        weather_moved += 1

    db.commit()
    return {
        "alerts_archived": alerts_moved,
        "weather_archived": weather_moved,
        # Compat com callers antigos
        "alerts_deleted": 0,
        "weather_deleted": 0,
    }
