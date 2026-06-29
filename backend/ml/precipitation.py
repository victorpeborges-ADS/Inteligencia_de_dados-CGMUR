from __future__ import annotations

import logging
from datetime import date

import httpx
import pandas as pd
from sqlalchemy.orm import Session

from app.models import Municipio
from ml.paths import precip_parquet

logger = logging.getLogger(__name__)

OPENMETEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_START = "2000-01-01"
DEFAULT_END = "2024-12-31"


def _municipio_centroid(db: Session, codigo_ibge: str) -> tuple[float, float]:
    import json
    from shapely.geometry import shape
    from sqlalchemy import func

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise ValueError(f"Município {codigo_ibge} não encontrado.")
    geojson = json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))
    centroid = shape(geojson).centroid
    return centroid.y, centroid.x


def fetch_daily_precipitation(lat: float, lon: float, start: str = DEFAULT_START, end: str = DEFAULT_END) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": "precipitation_sum,precipitation_hours",
        "timezone": "America/Sao_Paulo",
    }
    response = httpx.get(OPENMETEO_ARCHIVE, params=params, timeout=120.0)
    response.raise_for_status()
    payload = response.json()
    daily = payload.get("daily") or {}
    df = pd.DataFrame({
        "date": pd.to_datetime(daily.get("time", [])),
        "precipitation_sum": daily.get("precipitation_sum", []),
        "precipitation_hours": daily.get("precipitation_hours", []),
    })
    df["precipitation_sum"] = df["precipitation_sum"].fillna(0.0).astype(float)
    df["precipitation_hours"] = df["precipitation_hours"].fillna(0.0).astype(float)
    return df.sort_values("date").reset_index(drop=True)


def enrich_precip_windows(df: pd.DataFrame) -> pd.DataFrame:
    """Acumulados móveis usados como features."""
    out = df.copy()
    out["precip_24h"] = out["precipitation_sum"]
    out["precip_48h"] = out["precipitation_sum"].rolling(2, min_periods=1).sum()
    out["precip_72h"] = out["precipitation_sum"].rolling(3, min_periods=1).sum()
    out["precip_7d"] = out["precipitation_sum"].rolling(7, min_periods=1).sum()
    out["mes_do_ano"] = out["date"].dt.month
    return out


def collect_precipitation(db: Session, codigo_ibge: str, force: bool = False) -> pd.DataFrame:
    output = precip_parquet(codigo_ibge)
    if output.exists() and not force:
        return pd.read_parquet(output)

    lat, lon = _municipio_centroid(db, codigo_ibge)
    logger.info("Coletando precipitação OpenMeteo para %s (%.4f, %.4f)", codigo_ibge, lat, lon)
    df = fetch_daily_precipitation(lat, lon)
    df = enrich_precip_windows(df)
    df["codigo_ibge"] = codigo_ibge
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output, index=False)
    return df
