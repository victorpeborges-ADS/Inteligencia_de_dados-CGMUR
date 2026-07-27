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

    # Capacidade de drenagem espacializada por bairro (21d.4)
    from app.services.drainage_capacity_service import (
        bairro_drainage_capacity_mm_h,
        municipal_drainage_features,
    )
    from app.services.scs_cn_service import bairro_cn_proxy, municipal_cn_features

    drain_muni = municipal_drainage_features(db, codigo_ibge)
    cap_muni = float(drain_muni["capacidade_drenagem_mm_h"])
    df["capacidade_drenagem_mm_h"] = [
        bairro_drainage_capacity_mm_h(
            cap_muni,
            impermeabilizacao_pct=float(r.impermeabilizacao_pct),
            water_proximity=float(r.water_proximity),
        )
        for r in df.itertuples()
    ]
    df["curve_number"] = [
        bairro_cn_proxy(
            float(r.impermeabilizacao_pct),
            float(r.cobertura_vegetal_pct),
            float(r.water_proximity),
        )
        for r in df.itertuples()
    ]

    # HAND municipal (DEM) — custo alto; cache no municipal.json
    hand = {
        "hand_media_m": 12.0,
        "pct_hand_lt_5m": 15.0,
        "twi_media": 8.0,
        "suscetibilidade_hand": 0.35,
    }
    try:
        from app.services.hand_service import municipal_hand_features

        hand = municipal_hand_features(db, codigo_ibge)
    except Exception as exc:
        logger.warning("HAND %s: %s — defaults", codigo_ibge, exc)

    from ml.susceptibility import bairro_suscetibilidade

    df["suscetibilidade_local"] = [
        bairro_suscetibilidade(
            float(r.impermeabilizacao_pct),
            float(r.water_proximity),
            float(r.declividade_media),
            hand_media_m=float(hand["hand_media_m"]),
            pct_hand_lt_5m=float(hand["pct_hand_lt_5m"]),
        )
        for r in df.itertuples()
    ]

    cn_muni = municipal_cn_features(db, codigo_ibge)
    tendencia = _impermeabilizacao_trend_pp_a(db, muni.id, codigo_ibge)

    municipal_row = {
        "impermeabilizacao_pct": round(float(df["impermeabilizacao_pct"].mean()), 2),
        "cobertura_vegetal_pct": round(float(df["cobertura_vegetal_pct"].mean()), 2),
        "declividade_media": round(float(df["declividade_media"].mean()), 2),
        "water_proximity": round(float(df["water_proximity"].mean()), 3),
        "hand_media_m": float(hand["hand_media_m"]),
        "pct_hand_lt_5m": float(hand["pct_hand_lt_5m"]),
        "twi_media": float(hand.get("twi_media", 8.0)),
        "suscetibilidade_hand": float(hand.get("suscetibilidade_hand", 0.35)),
        "curve_number": float(cn_muni["curve_number"]),
        "capacidade_drenagem_mm_h": float(drain_muni["capacidade_drenagem_mm_h"]),
        "saturacao_drenagem_40mm": float(drain_muni["saturacao_drenagem_40mm"]),
        "tendencia_impermeabilizacao_pp_a": float(tendencia),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output, index=False)

    meta_path = output.with_suffix(".municipal.json")
    import json as json_lib
    meta_path.write_text(json_lib.dumps(municipal_row, ensure_ascii=False), encoding="utf-8")
    return df


def _impermeabilizacao_trend_pp_a(db: Session, municipio_id: int, codigo_ibge: str) -> float:
    """Tendência de impermeabilização em pp/ano (MapBiomas stats ou cobertura)."""
    try:
        from app.models import MapBiomasMunicipalStat

        rows = (
            db.query(MapBiomasMunicipalStat.ano, MapBiomasMunicipalStat.area_ha)
            .filter(
                MapBiomasMunicipalStat.codigo_ibge == codigo_ibge,
                MapBiomasMunicipalStat.classe_uso.in_(["Área Urbana", "Area Urbana", "Infraestrutura Urbana"]),
            )
            .order_by(MapBiomasMunicipalStat.ano)
            .all()
        )
        by_year: dict[int, float] = {}
        for ano, area in rows:
            by_year[int(ano)] = by_year.get(int(ano), 0.0) + float(area or 0)
        if len(by_year) >= 2:
            years = sorted(by_year)
            y0, y1 = years[0], years[-1]
            span = max(1, y1 - y0)
            # Converte ha → pp relativo à área do primeiro ano (proxy de tendência)
            a0 = max(by_year[y0], 1.0)
            delta_pp = 100.0 * (by_year[y1] - by_year[y0]) / a0
            return round(delta_pp / span, 3)
    except Exception as exc:
        logger.debug("MapBiomas trend stats %s: %s", codigo_ibge, exc)

    try:
        from app.models import CoberturaVegetalMapBiomas

        years = [
            int(y)
            for (y,) in db.query(CoberturaVegetalMapBiomas.ano)
            .filter(CoberturaVegetalMapBiomas.municipio_id == municipio_id)
            .distinct()
            .all()
            if y is not None
        ]
        if len(years) < 2:
            return 0.0
        y0, y1 = min(years), max(years)
        span = max(1, y1 - y0)

        def _urban_frac(ano: int) -> float:
            urban = db.query(func.sum(func.ST_Area(CoberturaVegetalMapBiomas.geom))).filter(
                CoberturaVegetalMapBiomas.municipio_id == municipio_id,
                CoberturaVegetalMapBiomas.ano == ano,
                CoberturaVegetalMapBiomas.classe_uso == "Área Urbana",
            ).scalar()
            total = db.query(func.sum(func.ST_Area(CoberturaVegetalMapBiomas.geom))).filter(
                CoberturaVegetalMapBiomas.municipio_id == municipio_id,
                CoberturaVegetalMapBiomas.ano == ano,
            ).scalar()
            if not total:
                return 0.0
            return 100.0 * float(urban or 0) / float(total)

        return round((_urban_frac(y1) - _urban_frac(y0)) / span, 3)
    except Exception as exc:
        logger.debug("MapBiomas trend geom %s: %s", codigo_ibge, exc)
        return 0.0
