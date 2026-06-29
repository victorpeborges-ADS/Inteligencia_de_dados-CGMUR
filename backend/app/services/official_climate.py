from __future__ import annotations

import datetime as dt
import math
from typing import Any, Dict, List, Optional

import requests
from shapely.geometry import shape
from sqlalchemy.orm import Session

from app.models import Municipio
from app.data_connectors.mapbiomas_collector import get_urban_series


INMET_BASE_URL = "https://apitempo.inmet.gov.br"
USER_AGENT = "SiniduClima/1.0"
REFERENCE_YEARS = [2015, 2020, 2024, 2025]
ESTIMATED_TIMELINE = [
    {"ano": 1985, "temperatura_media": 26.1, "area_urbanizada_km2": 85.0, "qualidade_dado": "Estimado"},
    {"ano": 1995, "temperatura_media": 26.6, "area_urbanizada_km2": 110.0, "qualidade_dado": "Estimado"},
    {"ano": 2005, "temperatura_media": 27.0, "area_urbanizada_km2": 145.0, "qualidade_dado": "Estimado"},
    {"ano": 2015, "temperatura_media": 27.5, "area_urbanizada_km2": 180.0, "qualidade_dado": "Estimado"},
    {"ano": 2025, "temperatura_media": 28.2, "area_urbanizada_km2": 218.4, "qualidade_dado": "Estimado"},
]


class OfficialClimateService:
    @staticmethod
    def urban_climate_series(db: Session, municipio: Municipio) -> Dict[str, Any]:
        centroid = shape_from_municipio(db, municipio).centroid
        station, station_lacuna = nearest_inmet_station(centroid.y, centroid.x)

        timeline = []
        lacunas: list[str] = []
        if station_lacuna:
            lacunas.append(station_lacuna)

        urban_by_year = {item["ano"]: item for item in get_urban_series(db, municipio.codigo_ibge)}
        has_mapbiomas_urban = bool(urban_by_year)

        if station:
            start_year = parse_station_start_year(station.get("DT_INICIO_OPERACAO"))
            for year in REFERENCE_YEARS:
                if start_year and year < start_year:
                    continue
                annual_temp = fetch_inmet_annual_temperature(station["CD_ESTACAO"], year)
                urban_point = urban_by_year.get(year)
                area_km2 = urban_point["area_urbanizada_km2"] if urban_point else None
                if annual_temp is not None or area_km2 is not None:
                    entry: dict[str, Any] = {"ano": year}
                    if annual_temp is not None:
                        entry["temperatura_media"] = annual_temp
                    if area_km2 is not None:
                        entry["area_urbanizada_km2"] = area_km2
                        entry["qualidade_dado"] = urban_point.get("qualidade_dado", "Derivado")
                    timeline.append(entry)

            if not timeline:
                lacunas.append(
                    "A estação INMET mais próxima foi localizada, mas a API pública não retornou dados para os anos testados."
                )
        elif has_mapbiomas_urban:
            for year in REFERENCE_YEARS:
                urban_point = urban_by_year.get(year)
                if urban_point:
                    timeline.append({
                        "ano": year,
                        "area_urbanizada_km2": urban_point["area_urbanizada_km2"],
                        "qualidade_dado": urban_point.get("qualidade_dado", "Derivado"),
                    })

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

        return {
            "municipio": {
                "codigo_ibge": municipio.codigo_ibge,
                "nome": municipio.nome,
                "uf": municipio.uf,
            },
            "station": station,
            "historical_timeline": timeline,
            "estimated_timeline": ESTIMATED_TIMELINE if not has_mapbiomas_urban else [],
            "source": f"INMET API pública (temperatura) + {urban_source}",
            "source_note": (
                "Temperatura anual quando disponível via INMET. "
                "Área urbanizada integrada via estatísticas MapBiomas por município/ano "
                "(oficial se CSV configurado; caso contrário calibrado Sinidu+Clima)."
            ),
            "estimated_source": "Estimativa interna Sinidu+Clima",
            "estimated_methodology": (
                "Timeline estimada usada apenas na ausência de série MapBiomas. "
                "Substituir por CSV oficial MapBiomas (MAPBIOMAS_STATS_CSV) para uso conclusivo."
            ),
            "lacunas": lacunas,
            "mapbiomas_integrado": has_mapbiomas_urban,
            "mapbiomas_oficial": has_official_urban,
        }


def shape_from_municipio(db: Session, municipio: Municipio):
    import json
    return shape(json.loads(db.scalar(municipio.geom.ST_AsGeoJSON())))


def nearest_inmet_station(lat: float, lon: float) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        response = requests.get(
            f"{INMET_BASE_URL}/estacoes/T",
            timeout=8,
            headers={"User-Agent": USER_AGENT},
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
                headers={"User-Agent": USER_AGENT},
            )
        except Exception:
            continue
        if response.status_code == 204:
            continue
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
    return round(sum(values) / len(values), 2)


def first_numeric(row: Dict[str, Any], keys: List[str]) -> Optional[float]:
    for key in keys:
        raw = row.get(key)
        if raw in (None, "", "null", "Null", "NULL", "9999"):
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
