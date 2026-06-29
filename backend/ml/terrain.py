from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Bairro, CoberturaVegetalMapBiomas, Municipio
from app.services.analytical_engine import AnalyticalEngine
from ml.paths import terrain_parquet

logger = logging.getLogger(__name__)

OPENTOPOGRAPHY_URL = "https://portal.opentopography.org/API/globaldem"


def _estimate_slope_from_terrain_proxy(urban_pct: float, water_proximity: float) -> float:
    """Declividade estimada (%) quando DEM indisponível."""
    base = 2.5 + urban_pct * 0.08
    return round(min(max(base - water_proximity * 1.2, 0.5), 12.0), 2)


def _fetch_municipal_mean_slope(lat: float, lon: float, south: float, north: float, west: float, east: float) -> float | None:
    """Tenta SRTM 30m via OpenTopography (sem autenticação — pode falhar)."""
    params = {
        "demtype": "SRTMGL1",
        "south": south,
        "north": north,
        "west": west,
        "east": east,
        "outputFormat": "GTiff",
    }
    try:
        response = httpx.get(OPENTOPOGRAPHY_URL, params=params, timeout=60.0)
        if response.status_code != 200 or len(response.content) < 1000:
            return None
        try:
            import rasterio
            from io import BytesIO

            with rasterio.open(BytesIO(response.content)) as src:
                data = src.read(1).astype("float64")
                nodata = src.nodata
                if nodata is not None:
                    data[data == nodata] = np.nan
                dy, dx = src.res
                dz_dy, dz_dx = np.gradient(np.nan_to_num(data, nan=float(np.nanmean(data))))
                slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
                slope_pct = np.nanmean(np.tan(slope_rad) * 100.0)
                return round(float(slope_pct), 2)
        except ImportError:
            logger.warning("rasterio indisponível — usando proxy de declividade.")
            return None
    except Exception as exc:
        logger.warning("OpenTopography indisponível: %s", exc)
        return None


def extract_bairro_features(db: Session, codigo_ibge: str, force: bool = False) -> pd.DataFrame:
    output = terrain_parquet(codigo_ibge)
    if output.exists() and not force:
        return pd.read_parquet(output)

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        raise ValueError(f"Município {codigo_ibge} não encontrado.")

    from shapely.geometry import shape

    muni_geo = json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))
    bounds = shape(muni_geo).bounds  # minx, miny, maxx, maxy
    centroid = shape(muni_geo).centroid
    municipal_slope = _fetch_municipal_mean_slope(
        centroid.y, centroid.x, bounds[1], bounds[3], bounds[0], bounds[2]
    )

    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    rows: list[dict[str, Any]] = []

    for b in bairros:
        area_deg = db.scalar(func.ST_Area(b.geom)) or 0.0

        urban_cover = db.query(CoberturaVegetalMapBiomas).filter(
            CoberturaVegetalMapBiomas.municipio_id == muni.id,
            CoberturaVegetalMapBiomas.classe_uso == "Área Urbana",
            func.ST_Intersects(b.geom, CoberturaVegetalMapBiomas.geom),
        ).all()
        veg_cover = db.query(CoberturaVegetalMapBiomas).filter(
            CoberturaVegetalMapBiomas.municipio_id == muni.id,
            CoberturaVegetalMapBiomas.classe_uso == "Vegetação / Floresta",
            func.ST_Intersects(b.geom, CoberturaVegetalMapBiomas.geom),
        ).all()
        water_cover = db.query(CoberturaVegetalMapBiomas).filter(
            CoberturaVegetalMapBiomas.municipio_id == muni.id,
            CoberturaVegetalMapBiomas.classe_uso == "Corpo d'água",
            func.ST_Intersects(b.geom, CoberturaVegetalMapBiomas.geom),
        ).all()

        urban_area = AnalyticalEngine._covered_area_deg(db, b.geom, urban_cover)
        veg_area = AnalyticalEngine._covered_area_deg(db, b.geom, veg_cover)
        water_area = AnalyticalEngine._covered_area_deg(db, b.geom, water_cover)

        urban_pct = round((urban_area / area_deg) * 100, 2) if area_deg else 50.0
        veg_pct = round((veg_area / area_deg) * 100, 2) if area_deg else 10.0
        water_prox = min((water_area / area_deg) if area_deg else 0.0, 1.0)

        if municipal_slope is not None:
            slope = round(municipal_slope * (0.85 + water_prox * 0.3), 2)
        else:
            slope = _estimate_slope_from_terrain_proxy(urban_pct / 100.0, water_prox)

        rows.append({
            "bairro_id": b.id,
            "bairro_nome": b.nome,
            "codigo_ibge": codigo_ibge,
            "impermeabilizacao_pct": urban_pct,
            "cobertura_vegetal_pct": veg_pct,
            "declividade_media": slope,
            "water_proximity": round(water_prox, 3),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame([{
            "bairro_id": 0,
            "bairro_nome": "Municipio",
            "codigo_ibge": codigo_ibge,
            "impermeabilizacao_pct": 45.0,
            "cobertura_vegetal_pct": 15.0,
            "declividade_media": municipal_slope or 3.0,
            "water_proximity": 0.1,
        }])

    municipal_row = {
        "impermeabilizacao_pct": round(df["impermeabilizacao_pct"].mean(), 2),
        "cobertura_vegetal_pct": round(df["cobertura_vegetal_pct"].mean(), 2),
        "declividade_media": round(df["declividade_media"].mean(), 2),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output, index=False)

    meta_path = output.with_suffix(".municipal.json")
    import json as json_lib
    meta_path.write_text(json_lib.dumps(municipal_row, ensure_ascii=False), encoding="utf-8")
    return df
