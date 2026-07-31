"""Roteamento via OSRM (Docker local) com fallback geodésico."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OSRM_BASE_URL = os.getenv("OSRM_URL", "http://osrm:5000")
OSRM_REGION = os.getenv("OSRM_REGION", "pe-se")

_REGION_DEFAULT_UFS: dict[str, str] = {
    "pernambuco": "PE",
    "pe-se": "PE,SE",
    "nordeste": "PE,AL,SE,PB,RN,CE,PI,MA",
    "sudeste": "SP,RJ,MG,ES",
    "sul": "PR,RS,SC",
    "centro-oeste": "GO,MT,MS,DF",
    "norte": "AM,PA,RO,RR,AC,AP,TO",
    "brazil": "AC,AL,AM,AP,BA,CE,DF,ES,GO,MA,MG,MS,MT,PA,PB,PE,PI,PR,RJ,RN,RO,RR,RS,SC,SE,SP,TO",
}

_env_covered = os.getenv("OSRM_COVERED_UFS")
if _env_covered:
    OSRM_COVERED_UFS = {uf.strip().upper() for uf in _env_covered.split(",") if uf.strip()}
else:
    OSRM_COVERED_UFS = {
        uf.strip().upper()
        for uf in _REGION_DEFAULT_UFS.get(OSRM_REGION, _REGION_DEFAULT_UFS["pe-se"]).split(",")
        if uf.strip()
    }

SUPPORTED_OSRM_REGIONS = list(_REGION_DEFAULT_UFS.keys())


def route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    profile: str = "driving",
    uf: str | None = None,
) -> dict[str, Any] | None:
    """Calcula rota [lng, lat] → LineString GeoJSON."""
    lng1, lat1 = origin
    lng2, lat2 = destination
    if uf and uf.upper() not in OSRM_COVERED_UFS:
        return _fallback_route(origin, destination, sem_malha_viaria=True)
    url = f"{OSRM_BASE_URL}/route/v1/{profile}/{lng1},{lat1};{lng2},{lat2}"
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code != 200:
                return _fallback_route(origin, destination, sem_malha_viaria=uf.upper() not in OSRM_COVERED_UFS if uf else True)
            data = resp.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                return _fallback_route(origin, destination, sem_malha_viaria=uf.upper() not in OSRM_COVERED_UFS if uf else True)
            route0 = data["routes"][0]
            return {
                "type": "Feature",
                "geometry": route0["geometry"],
                "properties": {
                    "distancia_m": route0.get("distance", 0),
                    "duracao_s": route0.get("duration", 0),
                    "fonte": "osrm",
                    "malha_viaria": True,
                    "aproximada": False,
                },
            }
    except Exception as exc:
        logger.warning("OSRM indisponível (%s); usando fallback.", exc)
        return _fallback_route(origin, destination, sem_malha_viaria=True)


def _fallback_route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    sem_malha_viaria: bool = True,
) -> dict[str, Any]:
    lng1, lat1 = origin
    lng2, lat2 = destination
    dist = _haversine(lat1, lng1, lat2, lng2)
    # Evacuação urbana ~40 km/h média
    duracao_s = dist / (40_000 / 3600) if dist > 0 else 0
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [list(origin), list(destination)],
        },
        "properties": {
            "distancia_m": round(dist, 1),
            "duracao_s": round(duracao_s, 1),
            "fonte": "fallback",
            "malha_viaria": not sem_malha_viaria,
            "aproximada": True,
        },
    }


def osrm_status() -> dict[str, Any]:
    """Saúde do serviço OSRM e UFs cobertas pela malha processada."""
    available = False
    detail = "indisponível"
    try:
        with httpx.Client(timeout=4.0) as client:
            # Coordenadas em Recife — teste leve de conectividade
            resp = client.get(
                f"{OSRM_BASE_URL}/route/v1/driving/-34.88,-8.05;-34.87,-8.06",
                params={"overview": "false"},
            )
            if resp.status_code == 200:
                payload = resp.json()
                available = payload.get("code") in ("Ok", "NoRoute")
                detail = payload.get("code", "Ok")
            else:
                detail = f"HTTP {resp.status_code}"
    except Exception as exc:
        detail = str(exc)[:120]

    setup_hint = (
        f"OSRM_REGION={OSRM_REGION} bash docker/osrm/setup-osrm.sh && docker compose up -d osrm"
        if not available
        else None
    )

    return {
        "available": available,
        "region": OSRM_REGION,
        "covered_ufs": sorted(OSRM_COVERED_UFS),
        "supported_regions": SUPPORTED_OSRM_REGIONS,
        "url": OSRM_BASE_URL,
        "detail": detail,
        "setup_hint": setup_hint,
        "fallback_active": not available,
    }


def routes_from_zones_to_support_points(
    zones: list[dict],
    support_points: list[dict],
    max_routes: int = 20,
    uf: str | None = None,
) -> list[dict]:
    """Gera rotas de fuga da zona (centroide) para pontos de apoio mais próximos."""
    if not zones or not support_points:
        return []

    routes: list[dict] = []
    for zi, zone in enumerate(zones[:10]):
        centroid = zone.get("centroid") or _centroid_from_geojson(zone.get("geometry"))
        if not centroid:
            continue
        best_sp = None
        best_dist = float("inf")
        for sp in support_points:
            pt = sp.get("coordinates") or sp.get("geom")
            if isinstance(pt, dict) and pt.get("type") == "Point":
                coords = pt["coordinates"]
            elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
                coords = pt
            else:
                continue
            dist = _haversine(centroid[1], centroid[0], coords[1], coords[0])
            if dist < best_dist:
                best_dist = dist
                best_sp = sp

        if not best_sp:
            continue
        sp_coords = best_sp.get("coordinates") or best_sp.get("geom", {}).get("coordinates")
        if isinstance(sp_coords, dict):
            sp_coords = sp_coords.get("coordinates")
        feat = route((centroid[0], centroid[1]), (sp_coords[0], sp_coords[1]), uf=uf)
        if feat:
            props = feat.get("properties") or {}
            routes.append({
                "nome": f"Rota {zi + 1} → {best_sp.get('nome', 'Ponto de apoio')}",
                "prioridade": zone.get("prioridade", zi + 1),
                "sentido": "saida",
                "zona_origem": zone.get("nome"),
                "ponto_destino": best_sp.get("nome"),
                "geojson": feat,
                "aproximada": bool(props.get("aproximada")),
                "malha_viaria": bool(props.get("malha_viaria")),
                "fonte_rota": props.get("fonte", "fallback"),
            })
        if len(routes) >= max_routes:
            break
    return routes


def _centroid_from_geojson(geom: dict | None) -> list[float] | None:
    if not geom:
        return None
    try:
        from shapely.geometry import shape
        c = shape(geom).centroid
        return [c.x, c.y]
    except Exception:
        return None


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
