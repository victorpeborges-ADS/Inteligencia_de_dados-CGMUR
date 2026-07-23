"""Sombra / insolação por edifício (17d.3) — MVP.

Posição solar (azimute/elevação) + proxy de sombreamento por densidade de
vizinhos mais altos → índice de insolação e conforto térmico relativo.
Não substitui ray-tracing / LOD2 com águas de telhado.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from shapely.geometry import shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Edificacao, Municipio

MAX_BUILDINGS = 3500
LEVEL_HEIGHT_M = 3.0


def solar_position(lat_deg: float, lon_deg: float, when: datetime) -> dict[str, float]:
    """Posição solar aproximada (algoritmo NOAA simplificado)."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    # dia do ano
    n = when.timetuple().tm_yday
    hour = when.hour + when.minute / 60.0 + when.second / 3600.0
    # UTC hour → lon local
    gamma = 2.0 * math.pi / 365.0 * (n - 1 + (hour - 12) / 24.0)
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
    )
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    time_offset = eqtime + 4.0 * lon_deg
    tst = hour * 60.0 + time_offset
    ha = math.radians((tst / 4.0) - 180.0)
    lat = math.radians(lat_deg)
    cos_zen = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    cos_zen = max(-1.0, min(1.0, cos_zen))
    zenith = math.acos(cos_zen)
    elev = 90.0 - math.degrees(zenith)
    # azimute
    sin_az = -math.sin(ha) * math.cos(decl) / max(1e-6, math.sin(zenith))
    cos_az = (
        (math.sin(decl) - math.sin(lat) * math.cos(zenith))
        / (math.cos(lat) * max(1e-6, math.sin(zenith)))
    )
    az = math.degrees(math.atan2(sin_az, cos_az))
    az = (az + 360.0) % 360.0
    return {
        "elevacao_graus": round(elev, 2),
        "azimute_graus": round(az, 2),
        "zenite_graus": round(math.degrees(zenith), 2),
    }


def _hsp_factor(elev_deg: float) -> float:
    if elev_deg <= 0:
        return 0.0
    return max(0.0, min(1.0, math.sin(math.radians(elev_deg))))


def _shade_from_neighbors(
    height_m: float,
    neighbor_heights: list[float],
    elev_deg: float,
) -> float:
    """Fração de sombra 0–1: vizinhos mais altos e sol baixo aumentam sombra."""
    if elev_deg <= 5:
        return 0.85
    taller = [h for h in neighbor_heights if h > height_m + 2]
    if not taller:
        return max(0.0, 0.15 * (1.0 - elev_deg / 90.0))
    excess = sum(min(40.0, h - height_m) for h in taller) / max(len(taller), 1)
    dens = min(1.0, len(taller) / 8.0)
    sun_low = max(0.0, 1.0 - elev_deg / 55.0)
    return round(min(0.9, 0.2 + 0.45 * dens + 0.25 * sun_low + 0.01 * excess), 3)


def compute_shadow_insolation(
    db: Session,
    codigo_ibge: str,
    *,
    when: datetime | None = None,
    hora_local: int | None = None,
    limit: int = MAX_BUILDINGS,
    ensure_buildings: bool = True,
) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    n = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    if n == 0 and ensure_buildings:
        from app.data_connectors.building_footprints_collector import collect_buildings_municipality

        collect_buildings_municipality(db, code, force=False)

    # centro
    lat, lon = -8.05, -34.88
    try:
        cj = db.scalar(func.ST_AsGeoJSON(func.ST_Centroid(muni.geom)))
        if cj:
            c = shape(json.loads(cj))
            lon, lat = float(c.x), float(c.y)
    except Exception:
        pass

    now = when or datetime.now(timezone.utc)
    if hora_local is not None:
        # interpreta como horário local UTC-3 (Brasil)
        now = now.replace(hour=int(hora_local) % 24, minute=0, second=0, microsecond=0)
        # approx: treat as UTC-3 for solar
        from datetime import timedelta

        now = now + timedelta(hours=3)  # local BRT → UTC for algorithm using lon

    sun = solar_position(lat, lon, now)
    elev = sun["elevacao_graus"]
    beam = _hsp_factor(elev)

    rows = (
        db.query(Edificacao)
        .filter(Edificacao.municipio_id == muni.id, Edificacao.geom.isnot(None))
        .limit(max(1, min(int(limit), MAX_BUILDINGS)))
        .all()
    )

    # sample centroids + heights for neighbor lookup (grid hash)
    samples: list[tuple[float, float, float, Any]] = []
    for row in rows:
        try:
            cj = db.scalar(func.ST_AsGeoJSON(func.ST_Centroid(row.geom)))
            if not cj:
                continue
            c = shape(json.loads(cj))
            h = float(row.altura_m or LEVEL_HEIGHT_M)
            samples.append((float(c.x), float(c.y), h, row))
        except Exception:
            continue

    # spatial hash ~50 m cells
    cell = 0.0005
    buckets: dict[tuple[int, int], list[float]] = {}
    for x, y, h, _ in samples:
        key = (int(x / cell), int(y / cell))
        buckets.setdefault(key, []).append(h)

    features: list[dict[str, Any]] = []
    sum_ins = 0.0
    sum_shade = 0.0
    band_counts = {"sombra": 0, "parcial": 0, "sol": 0}

    for x, y, h, row in samples:
        key = (int(x / cell), int(y / cell))
        neighbors: list[float] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                neighbors.extend(buckets.get((key[0] + dx, key[1] + dy), []))
        shade = _shade_from_neighbors(h, neighbors, elev)
        insol = round(beam * (1.0 - shade), 3)
        if insol < 0.25:
            faixa = "sombra"
            fill = "#334155"
        elif insol < 0.55:
            faixa = "parcial"
            fill = "#f59e0b"
        else:
            faixa = "sol"
            fill = "#fbbf24"
        band_counts[faixa] = band_counts.get(faixa, 0) + 1
        sum_ins += insol
        sum_shade += shade

        # conforto: sombra em hora quente (elev alta) é positivo
        conforto = round(shade * max(0.0, elev / 70.0), 3)

        try:
            geo = json.loads(db.scalar(row.geom.ST_AsGeoJSON()))
        except Exception:
            continue

        features.append({
            "type": "Feature",
            "geometry": geo,
            "properties": {
                "id": row.id,
                "nome": row.nome,
                "altura_m": h,
                "insolacao_indice": insol,
                "sombra_fracao": shade,
                "conforto_sombra": conforto,
                "faixa_insolacao": faixa,
                "elevacao_solar_graus": elev,
                "layer_type": "shadow_insolation",
                "_extrusionHeightM": h,
                "_fill": fill,
            },
        })

    n_f = len(features) or 1
    return {
        "scenario_type": "sombra_insolacao",
        "codigo_ibge": code,
        "municipio": muni.nome,
        "uf": muni.uf,
        "input_value": float(hora_local if hora_local is not None else now.hour),
        "metric_impact": "Índice médio de insolação (0–1)",
        "impact_value": round(sum_ins / n_f, 3),
        "affected_area_km2": 0,
        "affected_population": 0,
        "affected_bairros": [],
        "geometry": {"type": "FeatureCollection", "features": features},
        "sol": sun,
        "resumo": {
            "edificios": len(features),
            "insolacao_media": round(sum_ins / n_f, 3),
            "sombra_media": round(sum_shade / n_f, 3),
            "faixas": band_counts,
            "hora_utc": now.isoformat(),
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
        },
        "parametros": {
            "qualidade": "Estimado",
            "nota": (
                "Proxy: elevação solar × sombra por vizinhos mais altos. "
                "LOD1 plano — sem orientação de águas; refinar com LOD2/ray-tracing."
            ),
        },
        "simulation_meta": {
            "method": "solar_position_neighbor_shade",
            "model_version": "17d.3",
            "sol": sun,
            "faixas": band_counts,
        },
    }
