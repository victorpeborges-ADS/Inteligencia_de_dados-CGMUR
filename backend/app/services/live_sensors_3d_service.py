"""Sensores e alertas vivos para o gêmeo 3D (17e.3).

Consolida CEMADEN (camada + monitoramento), ponto de previsão climática
e, quando disponível, a estação INMET mais próxima — como GeoJSON de pontos
para overlay pulsante no MapLibre 3D.
"""

from __future__ import annotations

from app.timeutil import utc_now
import datetime
import logging
from typing import Any

from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.models import AlertaCemaden, MonitoringAlert, Municipio, WeatherForecastCache
from app.services.live_alert_level import live_alert_snapshot, normalize_nivel

logger = logging.getLogger(__name__)

NIVEL_TO_CEMADEN = {
    "VERMELHO": "MUITO_ALTO",
    "LARANJA": "ALTO",
    "AMARELO": "MEDIO",
    "VERDE": "BAIXO",
}

COLOR_BY_NIVEL = {
    "VERMELHO": "#f43f5e",
    "LARANJA": "#f97316",
    "AMARELO": "#eab308",
    "VERDE": "#22c55e",
}


def _muni_centroid_xy(muni: Municipio) -> tuple[float, float] | None:
    if muni.geom is None:
        return None
    try:
        c = to_shape(muni.geom).centroid
        return float(c.x), float(c.y)
    except Exception:
        return None


def _centroid_from_geom(geom) -> tuple[float, float] | None:
    if geom is None:
        return None
    try:
        c = to_shape(geom).centroid
        return float(c.x), float(c.y)
    except Exception:
        return None


def _coords_from_payload(payload: dict | None) -> tuple[float, float] | None:
    if not isinstance(payload, dict):
        return None
    for lat_k, lon_k in (
        ("lat", "lng"),
        ("lat", "lon"),
        ("latitude", "longitude"),
        ("VL_LATITUDE", "VL_LONGITUDE"),
    ):
        try:
            lat = float(payload[lat_k])
            lon = float(payload[lon_k])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lon, lat
        except (KeyError, TypeError, ValueError):
            continue
    geom = payload.get("geometry")
    if isinstance(geom, dict) and geom.get("type") == "Point":
        coords = geom.get("coordinates") or []
        if len(coords) >= 2:
            try:
                return float(coords[0]), float(coords[1])
            except (TypeError, ValueError):
                pass
    return None


def _point_feature(
    *,
    lon: float,
    lat: float,
    kind: str,
    nivel: str,
    titulo: str,
    mensagem: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nivel_n = normalize_nivel(nivel)
    props: dict[str, Any] = {
        "kind": kind,
        "nivel": nivel_n,
        "nivel_alerta": NIVEL_TO_CEMADEN.get(nivel_n, "MEDIO"),
        "titulo": titulo,
        "mensagem": mensagem,
        "fonte_referencia": "CEMADEN / monitoramento / INMET",
        "qualidade_dado": "oficial" if kind.startswith("cemaden") or kind == "inmet" else "derivado",
        "_fill": COLOR_BY_NIVEL.get(nivel_n, "#eab308"),
        "_fillOpacity": 0.92,
        "_radius": 9 if kind.startswith("cemaden") else 7,
        "_halo": True,
        "vivo": True,
    }
    if extra:
        props.update(extra)
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def _nearest_inmet_feature(lon: float, lat: float) -> dict[str, Any] | None:
    try:
        from app.services.official_climate import nearest_inmet_station

        station, lacuna = nearest_inmet_station(lat, lon)
        if not station or lacuna:
            return None
        slon = float(station["longitude"])
        slat = float(station["latitude"])
        return _point_feature(
            lon=slon,
            lat=slat,
            kind="inmet",
            nivel="VERDE",
            titulo=f"Estação INMET {station.get('codigo') or ''}".strip(),
            mensagem=station.get("nome"),
            extra={
                "codigo_estacao": station.get("codigo") or station.get("CD_ESTACAO"),
                "distancia_km": station.get("distancia_km"),
                "fonte_referencia": "INMET",
                "_fill": "#06b6d4",
                "_radius": 8,
            },
        )
    except Exception as exc:
        logger.debug("INMET opcional indisponível: %s", exc)
        return None


def build_live_sensors_geojson(
    db: Session,
    codigo_ibge: str,
    *,
    hours: int = 24,
    include_inmet: bool = True,
) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {
            "type": "FeatureCollection",
            "features": [],
            "meta": {"codigo_ibge": code, "erro": "municipio_nao_encontrado"},
        }

    centroid = _muni_centroid_xy(muni)
    features: list[dict[str, Any]] = []
    since = utc_now() - datetime.timedelta(hours=max(1, hours))

    # 1) Polígonos CEMADEN da camada → centroides vivos
    alertas = (
        db.query(AlertaCemaden)
        .filter(AlertaCemaden.municipio_id == muni.id)
        .order_by(AlertaCemaden.data_alerta.desc())
        .limit(80)
        .all()
    )
    for a in alertas:
        xy = _centroid_from_geom(a.geom) or centroid
        if not xy:
            continue
        nivel_raw = str(a.nivel_alerta or "MEDIO").upper()
        nivel = {
            "MUITO_ALTO": "VERMELHO",
            "ALTO": "LARANJA",
            "MEDIO": "AMARELO",
            "BAIXO": "VERDE",
        }.get(nivel_raw, "AMARELO")
        features.append(
            _point_feature(
                lon=xy[0],
                lat=xy[1],
                kind="cemaden_camada",
                nivel=nivel,
                titulo=f"CEMADEN — {nivel_raw}",
                mensagem=a.descricao,
                extra={
                    "data_alerta": a.data_alerta.isoformat() if a.data_alerta else None,
                    "fonte_referencia": "CEMADEN / GeoRiscos",
                },
            )
        )

    # 2) Alertas de monitoramento (WebSocket / sync)
    rows = (
        db.query(MonitoringAlert)
        .filter(MonitoringAlert.codigo_ibge == code, MonitoringAlert.created_at >= since)
        .order_by(MonitoringAlert.created_at.desc())
        .limit(40)
        .all()
    )
    for idx, row in enumerate(rows):
        xy = _coords_from_payload(row.payload if isinstance(row.payload, dict) else None)
        if not xy and centroid:
            # leve offset para não empilhar no mesmo pixel
            xy = (centroid[0] + 0.0008 * (idx % 5), centroid[1] + 0.0008 * (idx // 5))
        if not xy:
            continue
        kind = {
            "CEMADEN_ALERT": "cemaden_vivo",
            "RISK_THRESHOLD": "risco_interno",
            "WEATHER_UPDATE": "clima",
        }.get(row.tipo, "monitoramento")
        features.append(
            _point_feature(
                lon=xy[0],
                lat=xy[1],
                kind=kind,
                nivel=row.nivel,
                titulo=row.titulo,
                mensagem=row.mensagem,
                extra={
                    "alert_id": row.id,
                    "tipo": row.tipo,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                },
            )
        )

    # 3) Ponto da previsão climática (cache Open-Meteo)
    weather = (
        db.query(WeatherForecastCache)
        .filter(WeatherForecastCache.codigo_ibge == code)
        .order_by(WeatherForecastCache.fetched_at.desc())
        .first()
    )
    if weather and weather.lat is not None and weather.lng is not None:
        precip = float(weather.precip_72h_mm or 0)
        risk = float(weather.risk_probability or 0)
        nivel_w = "VERDE"
        if risk >= 0.7 or precip >= 80:
            nivel_w = "VERMELHO"
        elif risk >= 0.45 or precip >= 40:
            nivel_w = "LARANJA"
        elif risk >= 0.25 or precip >= 20:
            nivel_w = "AMARELO"
        features.append(
            _point_feature(
                lon=float(weather.lng),
                lat=float(weather.lat),
                kind="previsao_clima",
                nivel=nivel_w,
                titulo="Previsão precipitação (72h)",
                mensagem=f"{precip:.1f} mm · risco {risk:.0%}",
                extra={
                    "precip_72h_mm": precip,
                    "precip_24h_mm": float(weather.precip_24h_mm or 0),
                    "risk_probability": risk,
                    "fonte_referencia": "Open-Meteo (cache)",
                    "_fill": "#38bdf8",
                    "_radius": 7,
                },
            )
        )

    # 4) Estação INMET mais próxima (opcional / rede)
    if include_inmet and centroid:
        inmet_f = _nearest_inmet_feature(centroid[0], centroid[1])
        if inmet_f:
            features.append(inmet_f)

    snap = live_alert_snapshot(db, code, hours=hours)
    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "codigo_ibge": code,
            "municipio": muni.nome,
            "uf": muni.uf,
            "hours": hours,
            "count": len(features),
            "cemaden_camada": sum(1 for f in features if f["properties"]["kind"] == "cemaden_camada"),
            "cemaden_vivo": sum(1 for f in features if f["properties"]["kind"] == "cemaden_vivo"),
            "estacoes": sum(1 for f in features if f["properties"]["kind"] in ("inmet", "previsao_clima")),
            "nivel_alerta": snap.get("nivel_alerta"),
            "vivo": bool(snap.get("vivo")),
            "titulo_recente": snap.get("titulo_recente"),
        },
    }
