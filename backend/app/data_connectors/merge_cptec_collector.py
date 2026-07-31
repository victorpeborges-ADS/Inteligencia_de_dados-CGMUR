"""Coletor MERGE / CPTEC-INPE (Fase 21b.4).

Grade diária de precipitação (~0,1°) do produto MERGE (GPM + pluviômetros).
FTP público: https://ftp.cptec.inpe.br/modelos/tempo/MERGE/GPM/DAILY/YYYY/MM/

Amostra a banda PREC (kg/m² ≡ mm) no centróide municipal e grava em
serie_pluviometrica_observada (fonte=merge, data_quality=reanalise).

Cache local em MERGE_CPTEC_DIR (default /data/merge_cptec).
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import Municipio
from app.services.pluvio_series_service import upsert_pluvio_rows
from app.timeutil import utc_now

logger = logging.getLogger(__name__)

MERGE_BASE = "https://ftp.cptec.inpe.br/modelos/tempo/MERGE/GPM/DAILY"
DEFAULT_DIR = Path(os.getenv("MERGE_CPTEC_DIR", "/data/merge_cptec"))
PREC_BAND = 1  # Surface Precipitation [kg/m^2]
NEST_BAND = 2  # Number of stations / grid point
PILOT_IBGE = (
    "2611606",
    "2800308",
    "2927408",
    "3304557",
    "3550308",
    "5300108",
)


def merge_grib_url(day: dt.date) -> str:
    yyyymmdd = day.strftime("%Y%m%d")
    return (
        f"{MERGE_BASE}/{day.year}/{day.month:02d}/"
        f"MERGE_CPTEC_{yyyymmdd}.grib2"
    )


def merge_grib_filename(day: dt.date) -> str:
    return f"MERGE_CPTEC_{day.strftime('%Y%m%d')}.grib2"


def _muni_centroid(muni: Municipio) -> tuple[float, float]:
    """Retorna (lat, lng) do centróide; fallback Recife se geom ausente."""
    if muni.geom is not None:
        from geoalchemy2.shape import to_shape

        c = to_shape(muni.geom).centroid
        return float(c.y), float(c.x)
    return -8.047, -34.877


def ensure_grib(
    day: dt.date,
    *,
    directory: Path | None = None,
    download: bool = True,
    timeout: float = 60.0,
) -> Path | None:
    """Garante GRIB2 no cache local; baixa do FTP CPTEC se necessário."""
    root = Path(directory or DEFAULT_DIR)
    root.mkdir(parents=True, exist_ok=True)
    path = root / merge_grib_filename(day)
    if path.exists() and path.stat().st_size > 0:
        return path
    if not download:
        return None
    url = merge_grib_url(day)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                logger.info("MERGE ausente para %s (%s)", day.isoformat(), url)
                return None
            resp.raise_for_status()
            path.write_bytes(resp.content)
            return path
    except Exception as exc:
        logger.warning("Falha ao baixar MERGE %s: %s", day.isoformat(), exc)
        return None


def sample_precip_mm(path: Path, lon: float, lat: float) -> tuple[float | None, float | None]:
    """Amostra PREC (mm) e NEST no ponto; None se nodata / fora da grade."""
    import numpy as np
    import rasterio

    with rasterio.open(path) as ds:
        vals = list(ds.sample([(lon, lat)], indexes=[PREC_BAND, NEST_BAND]))
        if not vals:
            return None, None
        arr = vals[0]
        precip = float(arr[0]) if len(arr) >= 1 else None
        nest = float(arr[1]) if len(arr) >= 2 else None
        if precip is not None and (np.isnan(precip) or precip < -1e20):
            precip = None
        if nest is not None and (np.isnan(nest) or nest < -1e20):
            nest = None
        return precip, nest


def build_merge_row(
    *,
    codigo_ibge: str,
    municipio_id: int | None,
    day: dt.date,
    lat: float,
    lng: float,
    precip_mm: float,
    nest: float | None,
    arquivo: str,
) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    return {
        "codigo_ibge": code,
        "municipio_id": municipio_id,
        "estacao_id": f"merge:{code}",
        "estacao_nome": f"MERGE/CPTEC centróide {code}",
        "lat": lat,
        "lng": lng,
        "observed_at": dt.datetime(day.year, day.month, day.day),
        "precip_mm": precip_mm,
        "granularidade": "diaria",
        "data_quality": "reanalise",
        "fonte": "merge",
        "ingestido_em": utc_now(),
        "raw_payload": {
            "produto": "MERGE_CPTEC_GPM_DAILY",
            "arquivo": arquivo,
            "nest": nest,
            "banda_prec": PREC_BAND,
        },
    }


def collect_merge_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    start: dt.date | None = None,
    end: dt.date | None = None,
    directory: Path | None = None,
    download: bool = True,
) -> dict[str, Any]:
    """Ingere MERGE diário no centróide do município para [start, end]."""
    code = str(codigo_ibge).zfill(7)[:7]
    end_d = end or (dt.date.today() - dt.timedelta(days=1))
    start_d = start or (end_d - dt.timedelta(days=29))
    if start_d > end_d:
        start_d, end_d = end_d, start_d

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {
            "codigo_ibge": code,
            "skipped": True,
            "records": 0,
            "hint": f"Município {code} não encontrado no banco.",
            "fonte": "merge",
        }

    lat, lng = _muni_centroid(muni)
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    days = (end_d - start_d).days + 1
    day = start_d
    while day <= end_d:
        path = ensure_grib(day, directory=directory, download=download)
        if path is None:
            missing.append(day.isoformat())
            day += dt.timedelta(days=1)
            continue
        precip, nest = sample_precip_mm(path, lng, lat)
        if precip is None:
            missing.append(day.isoformat())
            day += dt.timedelta(days=1)
            continue
        rows.append(
            build_merge_row(
                codigo_ibge=code,
                municipio_id=muni.id,
                day=day,
                lat=lat,
                lng=lng,
                precip_mm=precip,
                nest=nest,
                arquivo=path.name,
            )
        )
        day += dt.timedelta(days=1)

    written = upsert_pluvio_rows(db, rows) if rows else 0
    return {
        "codigo_ibge": code,
        "skipped": written == 0,
        "records": written,
        "dias_pedidos": days,
        "dias_faltantes": missing[:20],
        "lat": lat,
        "lng": lng,
        "periodo": {"start": start_d.isoformat(), "end": end_d.isoformat()},
        "data_quality": "reanalise" if written else None,
        "fonte": "merge",
        "hint": (
            None
            if written
            else (
                "Sem GRIB2 MERGE no cache/FTP para o período. "
                f"Deposite em {directory or DEFAULT_DIR} ou verifique rede."
            )
        ),
    }


def collect_merge_pilots(
    db: Session,
    *,
    start: dt.date | None = None,
    end: dt.date | None = None,
    download: bool = True,
) -> dict[str, Any]:
    results = [
        collect_merge_municipality(
            db, code, start=start, end=end, download=download
        )
        for code in PILOT_IBGE
    ]
    return {
        "pilotos": results,
        "records": sum(int(r.get("records") or 0) for r in results),
        "fonte": "merge",
    }
