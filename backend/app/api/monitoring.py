from __future__ import annotations

from app.timeutil import utc_now
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import ContingencyPlan, MonitoringAlert, Municipio, WeatherForecastCache
from app.services.contingency_planner import plan_to_dict
from app.security.municipio_access import assert_codigo_ibge_access, filter_municipio_query, get_accessible_municipio
from app.services.audit_service import resolve_actor, log_audit
from app.services.scenario_analysis_service import (
    alert_icon_and_category,
    analyze_scenario,
    compare_municipalities,
    group_timeline_entries,
    interpret_alert,
)

router = APIRouter()


class MonitoringSyncRequest(BaseModel):
    codigos: list[str] | None = None


@router.post("/sync")
async def trigger_monitoring_sync(
    body: MonitoringSyncRequest | None = None,
    codigo_ibge: str | None = Query(default=None, description="Sincronizar só este município"),
    db: Session = Depends(get_db),
):
    """Dispara sincronização OpenMeteo + CEMADEN (manual ou pós-boot)."""
    from app.services.monitoring_sync import sync_monitoring_all

    codigos = body.codigos if body and body.codigos else ([codigo_ibge] if codigo_ibge else None)
    try:
        return await sync_monitoring_all(db, codigos)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sync monitoramento falhou: {exc}") from exc


def _muni_centroid(m: Municipio) -> tuple[float | None, float | None]:
    if m.geom is None:
        return None, None
    try:
        from geoalchemy2.shape import to_shape
        c = to_shape(m.geom).centroid
        return c.y, c.x
    except Exception:
        return None, None


@router.get("/dashboard/{codigo_ibge}")
def monitoring_dashboard(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    since = utc_now() - datetime.timedelta(hours=24)

    alerts = (
        db.query(MonitoringAlert)
        .filter(MonitoringAlert.codigo_ibge == codigo_ibge, MonitoringAlert.created_at >= since)
        .order_by(MonitoringAlert.created_at.desc())
        .limit(50)
        .all()
    )

    weather = (
        db.query(WeatherForecastCache)
        .filter(WeatherForecastCache.codigo_ibge == codigo_ibge)
        .order_by(WeatherForecastCache.fetched_at.desc())
        .first()
    )

    from app.services.live_alert_level import live_alert_snapshot, max_alert_level

    cemaden_active = [a for a in alerts if a.tipo == "CEMADEN_ALERT"]
    risk_alerts = [a for a in alerts if a.tipo == "RISK_THRESHOLD"]
    nivel_atual = max_alert_level([a.nivel for a in alerts])
    _live = live_alert_snapshot(db, codigo_ibge, hours=24)

    active_plan = None
    if muni:
        plan = (
            db.query(ContingencyPlan)
            .filter(ContingencyPlan.municipio_id == muni.id, ContingencyPlan.status == "ATIVO")
            .first()
        )
        if plan:
            active_plan = plan_to_dict(plan, muni)

    timeline_raw = [
        {
            "id": a.id,
            "tipo": a.tipo,
            "nivel": a.nivel,
            "titulo": a.titulo,
            "mensagem": a.mensagem,
            "created_at": a.created_at.isoformat(),
            "alert_icon": alert_icon_and_category(a.tipo, a.titulo, a.mensagem or "")[0],
            "alert_category": alert_icon_and_category(a.tipo, a.titulo, a.mensagem or "")[1],
        }
        for a in alerts
    ]

    return {
        "codigo_ibge": codigo_ibge,
        "nome_municipio": muni.nome if muni else None,
        "uf": muni.uf if muni else None,
        "nivel_risco_atual": nivel_atual,
        "cemaden_ativos": len(cemaden_active),
        "alertas_risco": len(risk_alerts),
        "alerta_vivo": _live,
        "precip_24h_mm": float(weather.precip_24h_mm) if weather else None,
        "precip_72h_mm": float(weather.precip_72h_mm) if weather else None,
        "risk_probability": float(weather.risk_probability) if weather else None,
        "risk_source": (
            (weather.raw_payload or {}).get("_risk_source")
            if weather and isinstance(weather.raw_payload, dict)
            else None
        ),
        "weather_updated_at": weather.fetched_at.isoformat() if weather else None,
        "weather_disponivel": weather is not None,
        "timeline": timeline_raw,
        "timeline_grouped": group_timeline_entries(timeline_raw),
        "plano_ativo": active_plan,
    }


@router.get("/scenario-analysis/{codigo_ibge}")
def get_scenario_analysis(
    codigo_ibge: str,
    request: Request,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    get_accessible_municipio(db, codigo_ibge, request=request)
    return analyze_scenario(db, codigo_ibge, force=force)


@router.get("/alert-interpretation/{codigo_ibge}/{alert_id}")
def get_alert_interpretation(
    codigo_ibge: str,
    alert_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    get_accessible_municipio(db, codigo_ibge, request=request)
    alert = (
        db.query(MonitoringAlert)
        .filter(MonitoringAlert.id == alert_id, MonitoringAlert.codigo_ibge == codigo_ibge)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado.")
    return interpret_alert(alert.tipo, alert.nivel, alert.titulo or "")


@router.get("/compare/{codigo_a}/{codigo_b}")
def compare_monitoring_municipalities(
    codigo_a: str,
    codigo_b: str,
    request: Request,
    db: Session = Depends(get_db),
):
    actor = resolve_actor(request)
    get_accessible_municipio(db, codigo_a, request=request)
    get_accessible_municipio(db, codigo_b, request=request)
    result = compare_municipalities(db, codigo_a, codigo_b)
    log_audit(
        db,
        user=actor,
        action="compare.monitoring",
        resource_type="comparacao",
        codigo_ibge=codigo_a,
        metadata={"codigo_b": codigo_b, "mais_critico": result.get("mais_critico_ibge")},
        request=request,
    )
    return result


@router.get("/map-overview")
def map_overview(request: Request, db: Session = Depends(get_db)):
    """Nível de alerta por município para mini-mapa."""
    since = utc_now() - datetime.timedelta(hours=24)
    actor = resolve_actor(request)
    municipios = filter_municipio_query(db.query(Municipio), actor).order_by(Municipio.nome.asc()).all()
    items = []
    com_geometria = 0
    com_coordenadas = 0

    for m in municipios:
        if m.geom is not None:
            com_geometria += 1
        muni_alerts = (
            db.query(MonitoringAlert)
            .filter(MonitoringAlert.codigo_ibge == m.codigo_ibge, MonitoringAlert.created_at >= since)
            .all()
        )
        latest = max(muni_alerts, key=lambda a: a.created_at) if muni_alerts else None
        weather = (
            db.query(WeatherForecastCache)
            .filter(WeatherForecastCache.codigo_ibge == m.codigo_ibge)
            .order_by(WeatherForecastCache.fetched_at.desc())
            .first()
        )
        nivel = latest.nivel if latest else "VERDE"
        cemaden_count = sum(1 for a in muni_alerts if a.tipo == "CEMADEN_ALERT")
        lat, lng = _muni_centroid(m)
        if lat is not None and lng is not None:
            com_coordenadas += 1
        items.append({
            "codigo_ibge": m.codigo_ibge,
            "nome": m.nome,
            "uf": m.uf,
            "nivel": nivel,
            "cemaden_ativos": cemaden_count,
            "precip_72h_mm": float(weather.precip_72h_mm) if weather else None,
            "risk_probability": float(weather.risk_probability) if weather else 0,
            "lat": lat,
            "lng": lng,
        })
    return {
        "total_municipios": len(municipios),
        "com_geometria": com_geometria,
        "com_coordenadas": com_coordenadas,
        "municipios": items,
    }


@router.get("/alerts/{codigo_ibge}")
def list_alerts(
    codigo_ibge: str,
    request: Request,
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    since = utc_now() - datetime.timedelta(hours=hours)
    rows = (
        db.query(MonitoringAlert)
        .filter(MonitoringAlert.codigo_ibge == codigo_ibge, MonitoringAlert.created_at >= since)
        .order_by(MonitoringAlert.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "tipo": r.tipo,
            "nivel": r.nivel,
            "titulo": r.titulo,
            "mensagem": r.mensagem,
            "payload": r.payload,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


class DisseminateAlertBody(BaseModel):
    nivel: str | None = None
    mensagem: str | None = None
    canais: list[str] | None = None
    checklist_itens: list[str] | None = None


@router.get("/disseminate/{codigo_ibge}/draft")
def disseminate_draft(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """Prévia da mensagem e canais disponíveis (17h.3d)."""
    from app.services.public_alert_service import draft_dissemination

    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    try:
        return draft_dissemination(db, codigo_ibge)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/disseminate/{codigo_ibge}")
async def disseminate_alert(
    codigo_ibge: str,
    body: DisseminateAlertBody,
    request: Request,
    db: Session = Depends(get_db),
):
    """Registra disseminação DC/população com status por canal (17h.3d)."""
    from app.services.alert_broadcaster import alert_manager
    from app.services.public_alert_service import dispatch_public_alert

    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    actor = resolve_actor(request)
    criado_por = getattr(actor, "username", None) or "gestor"
    try:
        result = dispatch_public_alert(
            db,
            codigo_ibge,
            nivel=body.nivel,
            mensagem=body.mensagem,
            canais=body.canais,
            checklist_itens=body.checklist_itens,
            criado_por=str(criado_por),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_audit(
        db,
        user=actor,
        action="alert.disseminate",
        resource_type="public_alert",
        codigo_ibge=str(codigo_ibge).zfill(7)[:7],
        metadata={
            "id": result.get("id"),
            "nivel": result.get("nivel"),
            "canais": result.get("canais"),
            "status_por_canal": result.get("status_por_canal"),
        },
        request=request,
    )
    try:
        await alert_manager.broadcast(
            str(codigo_ibge).zfill(7)[:7],
            {
                "type": "PUBLIC_ALERT_DISPATCH",
                "nivel": result.get("nivel"),
                "titulo": f"Disseminação DC · {result.get('nivel')}",
                "mensagem": result.get("mensagem"),
                "id": result.get("id"),
            },
        )
    except Exception:
        pass
    return result


@router.get("/disseminate/{codigo_ibge}/history")
def disseminate_history(
    codigo_ibge: str,
    request: Request,
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db),
):
    from app.services.public_alert_service import list_disseminations

    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    return {"items": list_disseminations(db, codigo_ibge, limit=limit)}


@router.get("/live-sensors/{codigo_ibge}")
def live_sensors_3d(
    codigo_ibge: str,
    request: Request,
    hours: int = Query(24, ge=1, le=168),
    include_inmet: bool = Query(True, description="Incluir estação INMET mais próxima"),
    db: Session = Depends(get_db),
):
    """GeoJSON de alertas CEMADEN/estações para overlay vivo no gêmeo 3D (17e.3)."""
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    from app.services.live_sensors_3d_service import build_live_sensors_geojson

    return build_live_sensors_geojson(
        db,
        codigo_ibge,
        hours=hours,
        include_inmet=include_inmet,
    )


@router.get("/critical-pois/{codigo_ibge}")
def critical_pois_3d(
    codigo_ibge: str,
    request: Request,
    escolas: bool = Query(True),
    saude: bool = Query(True),
    abrigos: bool = Query(True),
    equipamentos: bool = Query(True),
    db: Session = Depends(get_db),
):
    """POIs críticos (INEP/CNES/abrigos) para o gêmeo 3D (17f.3)."""
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    from app.services.critical_pois_3d_service import build_critical_pois_geojson

    return build_critical_pois_geojson(
        db,
        codigo_ibge,
        include_escolas=escolas,
        include_saude=saude,
        include_abrigos=abrigos,
        include_equipamentos=equipamentos,
    )


@router.get("/urban-context/{codigo_ibge}")
def urban_context_3d(
    codigo_ibge: str,
    request: Request,
    hidrografia: bool = Query(True),
    vias: bool = Query(True),
    curvas: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Hidrografia, vias e curvas de nível para o gêmeo 3D (17f.6)."""
    assert_codigo_ibge_access(db, codigo_ibge, request=request)
    from app.services.urban_context_3d_service import build_urban_context_geojson

    return build_urban_context_geojson(
        db,
        codigo_ibge,
        include_hidrografia=hidrografia,
        include_vias=vias,
        include_curvas=curvas,
    )
