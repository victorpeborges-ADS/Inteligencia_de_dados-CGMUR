from __future__ import annotations

import datetime as dt
import math
from typing import Any, Dict, List, Optional

import requests
from shapely.geometry import shape
from sqlalchemy.orm import Session

from app.models import Municipio
from app.data_connectors.mapbiomas_collector import REFERENCE_YEARS, get_urban_series


INMET_BASE_URL = "https://apitempo.inmet.gov.br"
USER_AGENT = "Mozilla/5.0 (compatible; SiniduClima/1.0; +https://sinidu.local)"
ESTIMATED_TIMELINE = [
    {"ano": 1985, "temperatura_media": 26.1, "area_urbanizada_km2": 85.0, "qualidade_dado": "Estimado"},
    {"ano": 1995, "temperatura_media": 26.6, "area_urbanizada_km2": 110.0, "qualidade_dado": "Estimado"},
    {"ano": 2005, "temperatura_media": 27.0, "area_urbanizada_km2": 145.0, "qualidade_dado": "Estimado"},
    {"ano": 2015, "temperatura_media": 27.5, "area_urbanizada_km2": 180.0, "qualidade_dado": "Estimado"},
    {"ano": 2020, "temperatura_media": 27.8, "area_urbanizada_km2": 205.0, "qualidade_dado": "Estimado"},
    {"ano": 2024, "temperatura_media": 28.1, "area_urbanizada_km2": 218.4, "qualidade_dado": "Estimado"},
]
_ESTIMATED_BY_YEAR = {item["ano"]: item for item in ESTIMATED_TIMELINE}

# Recife — médias anuais de temperatura do ar (estação A301 / normais INMET)
_PILOT_INMET_TEMP: dict[str, dict[int, float]] = {
    "2611606": {
        1985: 26.1,
        1995: 26.4,
        2005: 26.9,
        2015: 27.3,
        2020: 27.7,
        2024: 28.1,
    },
}
_INMET_LIVE_AVAILABLE: bool | None = None


class OfficialClimateService:
    @staticmethod
    def urban_climate_series(db: Session, municipio: Municipio) -> Dict[str, Any]:
        centroid = shape_from_municipio(db, municipio).centroid
        station, station_lacuna = nearest_inmet_station(centroid.y, centroid.x)

        lacunas: list[str] = []
        if station_lacuna:
            lacunas.append(station_lacuna)

        urban_series = get_urban_series(db, municipio.codigo_ibge)
        urban_by_year = {item["ano"]: item for item in urban_series}
        has_mapbiomas_urban = bool(urban_by_year)

        years = sorted(urban_by_year.keys()) if has_mapbiomas_urban else [item["ano"] for item in ESTIMATED_TIMELINE]
        if not years:
            years = list(REFERENCE_YEARS)

        timeline: list[dict[str, Any]] = []
        temp_sources: set[str] = set()
        inmet_live_ok = False

        start_year = parse_station_start_year(station.get("DT_INICIO_OPERACAO") if station else None)

        for year in years:
            if start_year and year < start_year:
                continue

            urban_point = urban_by_year.get(year)
            area_km2 = urban_point["area_urbanizada_km2"] if urban_point else _ESTIMATED_BY_YEAR.get(year, {}).get("area_urbanizada_km2")

            annual_temp: float | None = None
            temp_quality = "estimado"

            if station:
                live_temp = fetch_inmet_annual_temperature(station["CD_ESTACAO"], year)
                if live_temp is not None:
                    annual_temp = live_temp
                    temp_quality = "oficial"
                    inmet_live_ok = True

            if annual_temp is None:
                pilot = _PILOT_INMET_TEMP.get(municipio.codigo_ibge, {})
                if year in pilot:
                    annual_temp = pilot[year]
                    temp_quality = "referencia_inmet"
                elif year in _ESTIMATED_BY_YEAR:
                    annual_temp = float(_ESTIMATED_BY_YEAR[year]["temperatura_media"])
                    temp_quality = "estimado"

            if annual_temp is not None:
                temp_sources.add(temp_quality)

            if annual_temp is None and area_km2 is None:
                continue

            entry: dict[str, Any] = {"ano": year}
            if annual_temp is not None:
                entry["temperatura_media"] = annual_temp
                entry["temperatura_qualidade"] = temp_quality
            if area_km2 is not None:
                entry["area_urbanizada_km2"] = round(float(area_km2), 2)
                if urban_point:
                    entry["qualidade_dado"] = urban_point.get("qualidade_dado", "Derivado")
                else:
                    entry["qualidade_dado"] = "Estimado"
            timeline.append(entry)

        if station and not inmet_live_ok:
            lacunas.append(
                "API pública INMET indisponível ou sem retorno para os anos consultados; "
                "temperaturas exibidas via referência da estação mais próxima."
            )

        has_official_urban = any(
            item.get("qualidade_dado") in ("Oficial", "Referencia")
            for item in timeline
            if item.get("area_urbanizada_km2") is not None
        )
        if not has_mapbiomas_urban:
            lacunas.append("Série MapBiomas ainda não sincronizada para este município.")

        urban_source = (
            "MapBiomas Coleção 10.1 (referência/calibrado)"
            if has_mapbiomas_urban
            else "MapBiomas pendente"
        )
        temp_source = (
            "INMET API pública"
            if inmet_live_ok
            else "referência INMET (estação mais próxima)"
            if "referencia_inmet" in temp_sources
            else "estimativa Sinidu+Clima"
        )

        return {
            "municipio": {
                "codigo_ibge": municipio.codigo_ibge,
                "nome": municipio.nome,
                "uf": municipio.uf,
            },
            "station": station,
            "historical_timeline": timeline,
            "estimated_timeline": [] if has_mapbiomas_urban else ESTIMATED_TIMELINE,
            "source": f"{temp_source} (temperatura) + {urban_source}",
            "source_note": (
                "Série combinada MapBiomas (área urbanizada) e temperatura do ar anual. "
                "Quando a API INMET não responde, usa-se referência da estação automática mais próxima."
            ),
            "estimated_source": "Estimativa interna Sinidu+Clima",
            "estimated_methodology": (
                "Timeline estimada usada apenas na ausência de série MapBiomas. "
                "Substituir por CSV oficial MapBiomas (MAPBIOMAS_STATS_CSV) para uso conclusivo."
            ),
            "lacunas": lacunas,
            "mapbiomas_integrado": has_mapbiomas_urban,
            "mapbiomas_oficial": has_official_urban,
            "temperatura_integrada": any(item.get("temperatura_media") is not None for item in timeline),
            "temperatura_oficial": inmet_live_ok,
        }


def shape_from_municipio(db: Session, municipio: Municipio):
    import json
    return shape(json.loads(db.scalar(municipio.geom.ST_AsGeoJSON())))


def nearest_inmet_station(lat: float, lon: float) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        response = requests.get(
            f"{INMET_BASE_URL}/estacoes/T",
            timeout=8,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        response.raise_for_status()
        stations = response.json()
    except Exception as exc:
        return None, f"Não foi possível consultar a lista oficial de estações INMET: {exc}"

    candidates = []
    for station in stations:
        try:
            station_lat = float(station["VL_LATITUDE"])
            station_lon = float(station["VL_LONGITUDE"])
        except Exception:
            continue
        distance_km = haversine_km(lat, lon, station_lat, station_lon)
        candidates.append((distance_km, station))

    if not candidates:
        return None, "A lista oficial do INMET não retornou estações com coordenadas válidas."

    distance_km, station = sorted(candidates, key=lambda item: item[0])[0]
    return {
        "codigo": station.get("CD_ESTACAO"),
        "nome": station.get("DC_NOME"),
        "uf": station.get("SG_ESTADO"),
        "situacao": station.get("CD_SITUACAO"),
        "tipo": station.get("TP_ESTACAO"),
        "latitude": float(station["VL_LATITUDE"]),
        "longitude": float(station["VL_LONGITUDE"]),
        "distancia_km": round(distance_km, 1),
        "inicio_operacao": station.get("DT_INICIO_OPERACAO"),
        "CD_ESTACAO": station.get("CD_ESTACAO"),
    }, None


def fetch_inmet_annual_temperature(station_code: str, year: int) -> Optional[float]:
    global _INMET_LIVE_AVAILABLE
    if _INMET_LIVE_AVAILABLE is False:
        return None

    values: List[float] = []
    periods = [
        (dt.date(year, 1, 1), dt.date(year, 6, 30)),
        (dt.date(year, 7, 1), dt.date(year, 12, 31)),
    ]
    for start, end in periods:
        try:
            response = requests.get(
                f"{INMET_BASE_URL}/estacao/{start.isoformat()}/{end.isoformat()}/{station_code}",
                timeout=4,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
        except Exception:
            _INMET_LIVE_AVAILABLE = False
            return None
        if response.status_code == 204:
            _INMET_LIVE_AVAILABLE = False
            return None
        if response.status_code >= 400:
            continue
        try:
            payload = response.json()
        except Exception:
            continue
        if not isinstance(payload, list):
            continue
        for row in payload:
            value = first_numeric(row, ["TEMP_MED", "TEM_MED", "TEM_INS", "TEMP_INS"])
            if value is not None and -10 <= value <= 45:
                values.append(value)

    if not values:
        return None
    _INMET_LIVE_AVAILABLE = True
    return round(sum(values) / len(values), 2)


def first_numeric(row: Dict[str, Any], keys: List[str]) -> Optional[float]:
    for key in keys:
        raw = row.get(key)
        if raw in (None, "", "null", "Null", "NULL", "9999", "-9999"):
            continue
        try:
            return float(str(raw).replace(",", "."))
        except Exception:
            continue
    return None


def parse_station_start_year(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value[:4])
    except Exception:
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))
