"""Perfil / seção transversal de elevação ao longo de uma linha (17f.5)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.models import Municipio


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _sample_elev(
    elev: np.ndarray,
    west: float,
    south: float,
    res_x: float,
    res_y: float,
    lon: float,
    lat: float,
) -> float | None:
    rows, cols = elev.shape
    if res_x == 0 or res_y == 0:
        return None
    # hydro_simulator._lat_grid: linha 0 = norte
    north = south + rows * res_y
    c = int((lon - west) / res_x)
    r = int((north - lat) / res_y)
    if r < 0 or c < 0 or r >= rows or c >= cols:
        return None
    val = float(elev[r, c])
    if not np.isfinite(val):
        return None
    return val


def build_terrain_profile(
    db: Session,
    codigo_ibge: str,
    coordinates: list[list[float]],
    *,
    samples: int = 80,
    water_level_m: float | None = None,
) -> dict[str, Any]:
    """
    coordinates: [[lon, lat], ...] LineString (mín. 2 pontos).
    Retorna série distância×elevação (+ nível d'água opcional).
    """
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {"erro": "municipio_nao_encontrado", "points": []}

    coords = [c for c in coordinates if isinstance(c, (list, tuple)) and len(c) >= 2]
    if len(coords) < 2:
        return {"erro": "linha_invalida", "points": [], "mensagem": "Informe ao menos 2 pontos [lon, lat]."}

    from app.services.hydro_simulator import _load_elevation_grid

    grid = _load_elevation_grid(db, code, muni)
    if grid is None:
        return {
            "erro": "dem_indisponivel",
            "points": [],
            "mensagem": "DEM não processado para este município.",
        }

    elev, west, south, res_x, res_y, meta = grid
    n = max(10, min(200, int(samples)))

    # densificar a polilinha em n amostras por comprimento acumulado
    seg_lens: list[float] = []
    total = 0.0
    for i in range(len(coords) - 1):
        d = _haversine_m(float(coords[i][0]), float(coords[i][1]), float(coords[i + 1][0]), float(coords[i + 1][1]))
        seg_lens.append(d)
        total += d
    if total <= 0:
        return {"erro": "linha_degenerada", "points": []}

    points: list[dict[str, Any]] = []
    for i in range(n):
        target = (i / (n - 1)) * total if n > 1 else 0.0
        acc = 0.0
        lon, lat = float(coords[0][0]), float(coords[0][1])
        for sidx, slen in enumerate(seg_lens):
            if acc + slen >= target or sidx == len(seg_lens) - 1:
                t = 0.0 if slen <= 0 else (target - acc) / slen
                t = max(0.0, min(1.0, t))
                a, b = coords[sidx], coords[sidx + 1]
                lon = float(a[0]) + (float(b[0]) - float(a[0])) * t
                lat = float(a[1]) + (float(b[1]) - float(a[1])) * t
                break
            acc += slen
        z = _sample_elev(elev, west, south, res_x, res_y, lon, lat)
        points.append({
            "distance_m": round(target, 1),
            "lon": round(lon, 6),
            "lat": round(lat, 6),
            "elevation_m": round(z, 2) if z is not None else None,
        })

    zs = [p["elevation_m"] for p in points if p["elevation_m"] is not None]
    water = None
    if water_level_m is not None and zs:
        water = float(water_level_m)
    elif zs:
        # proxy: cota média - 1 m (útil para demo sem simulação)
        water = None

    flooded = 0
    if water is not None:
        for p in points:
            z = p["elevation_m"]
            p["below_water"] = z is not None and z < water
            if p["below_water"]:
                flooded += 1

    return {
        "codigo_ibge": code,
        "municipio": muni.nome,
        "uf": muni.uf,
        "length_m": round(total, 1),
        "samples": len(points),
        "elevation_min_m": round(min(zs), 2) if zs else None,
        "elevation_max_m": round(max(zs), 2) if zs else None,
        "water_level_m": water,
        "points_below_water": flooded,
        "dem_source": (meta or {}).get("dem_source"),
        "points": points,
        "geometry": {"type": "LineString", "coordinates": coords},
    }
