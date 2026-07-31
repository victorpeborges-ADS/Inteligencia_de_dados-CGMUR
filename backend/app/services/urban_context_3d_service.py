"""Camadas de contexto urbano para o gêmeo 3D (17f.6).

Hidrografia (MapBiomas água + rios seed), vias (infraestrutura OSM/local)
e curvas de nível (DEM SRTM/LiDAR via hydro_simulator.contours_geojson).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CoberturaVegetalMapBiomas, InfraestruturaUrbana, Municipio

logger = logging.getLogger(__name__)

MAX_VIAS = 120
MAX_AGUA = 80
MAX_CURVAS = 100

# Fallback hidrografia Recife (aprox.) quando não há água no MapBiomas local
_RECIFE_RIVERS = [
    {
        "nome": "Rio Capibaribe",
        "coords": [
            [-34.96, -8.04],
            [-34.94, -8.045],
            [-34.92, -8.05],
            [-34.90, -8.053],
            [-34.885, -8.055],
            [-34.87, -8.058],
        ],
    },
    {
        "nome": "Rio Beberibe",
        "coords": [
            [-34.92, -8.01],
            [-34.905, -8.02],
            [-34.89, -8.035],
            [-34.88, -8.05],
            [-34.875, -8.055],
        ],
    },
]


def _line_feature(
    coords: list[list[float]],
    *,
    contexto: str,
    nome: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stroke = {
        "hidrografia": "#38bdf8",
        "via": "#f8fafc",
        "curva": "#a8a29e",
    }.get(contexto, "#94a3b8")
    width = {"hidrografia": 2.4, "via": 1.8, "curva": 0.9}.get(contexto, 1.2)
    props: dict[str, Any] = {
        "contexto": contexto,
        "nome": nome,
        "fonte_referencia": {
            "hidrografia": "MapBiomas / hidrografia de referência",
            "via": "OSM / bases locais",
            "curva": "DEM SRTM/LiDAR (isolinhas)",
        }.get(contexto, "Sinidu+Clima"),
        "_stroke": stroke,
        "_strokeWidth": width,
        "_fill": stroke,
        "_fillOpacity": 0.25 if contexto == "hidrografia" else 0,
    }
    if extra:
        props.update(extra)
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": props,
    }


def _polygon_feature(
    geom_json: dict,
    *,
    contexto: str,
    nome: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stroke = "#0ea5e9"
    props: dict[str, Any] = {
        "contexto": contexto,
        "nome": nome,
        "fonte_referencia": "MapBiomas água",
        "_stroke": stroke,
        "_strokeWidth": 1.2,
        "_fill": "#0284c7",
        "_fillOpacity": 0.35,
    }
    if extra:
        props.update(extra)
    return {
        "type": "Feature",
        "geometry": geom_json,
        "properties": props,
    }


def _vias_features(db: Session, muni: Municipio) -> list[dict[str, Any]]:
    rows = (
        db.query(
            InfraestruturaUrbana.nome,
            InfraestruturaUrbana.tipo,
            InfraestruturaUrbana.subgrupo,
            func.ST_AsGeoJSON(InfraestruturaUrbana.geom).label("geojson"),
        )
        .filter(
            InfraestruturaUrbana.municipio_id == muni.id,
            InfraestruturaUrbana.tipo.in_(("via", "rodovia", "highway")),
        )
        .limit(MAX_VIAS)
        .all()
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            g = json.loads(r.geojson)
        except Exception:
            continue
        if g.get("type") not in ("LineString", "MultiLineString"):
            # ponto → ignora
            continue
        if g["type"] == "MultiLineString":
            for part in g.get("coordinates") or []:
                if len(part) >= 2:
                    out.append(
                        _line_feature(
                            part,
                            contexto="via",
                            nome=r.nome or "Via",
                            extra={"subtipo": r.subgrupo or r.tipo},
                        )
                    )
        elif len(g.get("coordinates") or []) >= 2:
            out.append(
                _line_feature(
                    g["coordinates"],
                    contexto="via",
                    nome=r.nome or "Via",
                    extra={"subtipo": r.subgrupo or r.tipo},
                )
            )
    return out


def _hidrografia_features(db: Session, muni: Municipio) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    # MapBiomas água
    rows = (
        db.query(
            CoberturaVegetalMapBiomas.classe_uso,
            CoberturaVegetalMapBiomas.ano,
            func.ST_AsGeoJSON(CoberturaVegetalMapBiomas.geom).label("geojson"),
        )
        .filter(
            CoberturaVegetalMapBiomas.municipio_id == muni.id,
            CoberturaVegetalMapBiomas.classe_uso.ilike("%gua%"),
        )
        .limit(MAX_AGUA)
        .all()
    )
    for r in rows:
        try:
            g = json.loads(r.geojson)
        except Exception:
            continue
        if g.get("type") in ("Polygon", "MultiPolygon"):
            out.append(
                _polygon_feature(
                    g,
                    contexto="hidrografia",
                    nome=str(r.classe_uso or "Água"),
                    extra={"ano": r.ano},
                )
            )
        elif g.get("type") == "LineString" and len(g.get("coordinates") or []) >= 2:
            out.append(
                _line_feature(
                    g["coordinates"],
                    contexto="hidrografia",
                    nome=str(r.classe_uso or "Curso d'água"),
                    extra={"ano": r.ano},
                )
            )

    # Fallback Recife
    if not out and muni.codigo_ibge == "2611606":
        for river in _RECIFE_RIVERS:
            out.append(
                _line_feature(
                    river["coords"],
                    contexto="hidrografia",
                    nome=river["nome"],
                    extra={"qualidade_dado": "Referencia", "fonte_referencia": "Hidrografia de referência Recife"},
                )
            )
    return out


def _curvas_features(db: Session, muni: Municipio) -> list[dict[str, Any]]:
    try:
        from app.services.hydro_simulator import _load_elevation_grid, contours_geojson
    except Exception as exc:
        logger.debug("hydro_simulator indisponível: %s", exc)
        return []

    grid = _load_elevation_grid(db, muni.codigo_ibge, muni)
    if grid is None:
        return []
    elev, west, south, res_x, res_y, _meta = grid
    try:
        fc = contours_geojson(
            elev,
            west,
            south,
            res_x,
            res_y,
            interval_m=None,
            max_levels=10,
            max_features=MAX_CURVAS,
        )
    except Exception as exc:
        logger.warning("Curvas de nível falharam para %s: %s", muni.codigo_ibge, exc)
        return []

    out: list[dict[str, Any]] = []
    for f in fc.get("features") or []:
        geom = f.get("geometry") or {}
        if geom.get("type") != "LineString":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        props = f.get("properties") or {}
        elev_m = props.get("elevation_m") or props.get("elevacao_m") or props.get("level")
        nome = f"Cota {elev_m} m" if elev_m is not None else "Curva de nível"
        indexed = bool(props.get("index_contour"))
        out.append(
            _line_feature(
                coords,
                contexto="curva",
                nome=nome,
                extra={
                    "elevacao_m": elev_m,
                    "index_contour": indexed,
                    "_stroke": "#d6d3d1" if indexed else "#78716c",
                    "_strokeWidth": 1.4 if indexed else 0.7,
                },
            )
        )
    return out


def build_urban_context_geojson(
    db: Session,
    codigo_ibge: str,
    *,
    include_hidrografia: bool = True,
    include_vias: bool = True,
    include_curvas: bool = True,
) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {
            "type": "FeatureCollection",
            "features": [],
            "meta": {"codigo_ibge": code, "erro": "municipio_nao_encontrado"},
        }

    features: list[dict[str, Any]] = []
    counts = {"hidrografia": 0, "via": 0, "curva": 0}

    if include_hidrografia:
        hydro = _hidrografia_features(db, muni)
        features.extend(hydro)
        counts["hidrografia"] = len(hydro)

    if include_vias:
        vias = _vias_features(db, muni)
        features.extend(vias)
        counts["via"] = len(vias)

    if include_curvas:
        curvas = _curvas_features(db, muni)
        features.extend(curvas)
        counts["curva"] = len(curvas)

    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "codigo_ibge": code,
            "municipio": muni.nome,
            "uf": muni.uf,
            "count": len(features),
            "por_contexto": counts,
        },
    }
