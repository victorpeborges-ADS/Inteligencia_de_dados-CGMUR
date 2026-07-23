"""Testes sensores vivos 3D (17e.3)."""

from __future__ import annotations

from app.timeutil import utc_now
from unittest.mock import MagicMock, patch

from app.services.live_sensors_3d_service import (
    _coords_from_payload,
    build_live_sensors_geojson,
)


def test_coords_from_payload_lat_lng():
    assert _coords_from_payload({"lat": -8.05, "lng": -34.88}) == (-34.88, -8.05)


def test_coords_from_payload_point_geometry():
    assert _coords_from_payload(
        {"geometry": {"type": "Point", "coordinates": [-34.9, -8.1]}}
    ) == (-34.9, -8.1)


def test_coords_from_payload_invalid():
    assert _coords_from_payload(None) is None
    assert _coords_from_payload({}) is None


def test_build_live_sensors_geojson_empty_muni():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    out = build_live_sensors_geojson(db, "2611606", include_inmet=False)
    assert out["features"] == []
    assert out["meta"]["erro"] == "municipio_nao_encontrado"


def test_build_live_sensors_with_monitoring_and_weather():
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    muni.nome = "Recife"
    muni.uf = "PE"
    muni.geom = None

    alert = MagicMock()
    alert.id = 10
    alert.tipo = "CEMADEN_ALERT"
    alert.nivel = "LARANJA"
    alert.titulo = "Alerta teste"
    alert.mensagem = "Chuva"
    alert.payload = {"lat": -8.05, "lng": -34.88}
    alert.created_at = utc_now()

    weather = MagicMock()
    weather.lat = -8.06
    weather.lng = -34.89
    weather.precip_72h_mm = 55
    weather.precip_24h_mm = 20
    weather.risk_probability = 0.5

    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        name = getattr(model, "__name__", str(model))
        if name == "Municipio" or "Municipio" in str(model):
            q.filter.return_value.first.return_value = muni
        elif "AlertaCemaden" in str(model):
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        elif "MonitoringAlert" in str(model):
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [alert]
        elif "WeatherForecastCache" in str(model):
            q.filter.return_value.order_by.return_value.first.return_value = weather
        else:
            q.filter.return_value.first.return_value = None
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            q.filter.return_value.count.return_value = 0
        return q

    db.query.side_effect = query_side_effect

    with patch(
        "app.services.live_sensors_3d_service.live_alert_snapshot",
        return_value={
            "nivel_alerta": "LARANJA",
            "vivo": True,
            "titulo_recente": "Alerta teste",
        },
    ):
        out = build_live_sensors_geojson(db, "2611606", include_inmet=False)

    kinds = {f["properties"]["kind"] for f in out["features"]}
    assert "cemaden_vivo" in kinds
    assert "previsao_clima" in kinds
    assert out["meta"]["vivo"] is True
    assert out["meta"]["count"] >= 2
