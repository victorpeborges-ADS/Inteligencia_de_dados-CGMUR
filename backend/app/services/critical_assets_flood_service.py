"""Ativos críticos (escolas INEP + saúde CNES + abrigos) × mancha de alagamento."""

from __future__ import annotations

import json
import logging
from typing import Any

from geoalchemy2.shape import to_shape
from shapely.geometry import mapping, shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ContingencyPlan, EscolaInep, EstabelecimentoSaude, Municipio
from app.services.impassable_roads_service import (
    DEFAULT_DEPTH_THRESHOLD_M,
    _flood_union_from_features,
)

logger = logging.getLogger(__name__)

MAX_HIT = 200
COLOR = {
    "escola": "#38bdf8",
    "saude": "#22c55e",
    "abrigo": "#fbbf24",
}
BAND_RANK = {"superficial": 1, "moderada": 2, "critica": 3}


def _point_xy(geom) -> tuple[float, float] | None:
    if geom is None:
        return None
    try:
        g = to_shape(geom)
        if g.geom_type == "Point":
            return float(g.x), float(g.y)
        c = g.centroid
        return float(c.x), float(c.y)
    except Exception:
        return None


def _band_for_point(lon: float, lat: float, flood_fc: dict[str, Any] | None) -> tuple[str | None, float | None]:
    """Pior faixa de profundidade que contém o ponto."""
    if not flood_fc or not flood_fc.get("features"):
        return None, None
    from shapely.geometry import Point

    pt = Point(lon, lat)
    best_band: str | None = None
    best_depth: float | None = None
    best_rank = 0
    for feat in flood_fc["features"]:
        props = feat.get("properties") or {}
        if props.get("layer_type") and props.get("layer_type") != "flood_band":
            continue
        band = props.get("depth_band")
        if band not in BAND_RANK:
            continue
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            g = shape(geom)
            if g.is_empty or not g.contains(pt):
                continue
        except Exception:
            continue
        rank = BAND_RANK[band]
        if rank >= best_rank:
            best_rank = rank
            best_band = band
            dmax = props.get("depth_max_m")
            dmin = props.get("depth_min_m")
            try:
                best_depth = float(dmax if dmax is not None else dmin)
            except (TypeError, ValueError):
                best_depth = None
    return best_band, best_depth


def _feat(
    *,
    lon: float,
    lat: float,
    categoria: str,
    nome: str,
    subtipo: str | None,
    depth_band: str | None,
    depth_m: float | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    color = COLOR.get(categoria, "#a78bfa")
    props: dict[str, Any] = {
        "layer_type": "ativo_critico_atingido",
        "categoria": categoria,
        "nome": nome,
        "subtipo": subtipo,
        "depth_band": depth_band,
        "depth_m": depth_m,
        "fill_color": color,
        "_fill": color,
        "_fillOpacity": 0.95,
        "_radius": 8,
        "_stroke": "#7f1d1d" if depth_band == "critica" else "#9a3412",
        "fonte_referencia": {
            "escola": "INEP Censo Escolar × mancha pluvial",
            "saude": "CNES/DataSUS × mancha pluvial",
            "abrigo": "Plano de contingência × mancha pluvial",
        }.get(categoria, "Sinidu+Clima"),
        "qualidade_dado": "Derivado Sinidu+Clima",
    }
    if extra:
        props.update(extra)
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def build_critical_assets_hit_geojson(
    db: Session,
    muni: Municipio,
    flood_fc: dict[str, Any] | None,
    *,
    min_depth_m: float = DEFAULT_DEPTH_THRESHOLD_M,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Pontos de escola/saúde/abrigo sob alagamento ≥ limiar (moderada/crítica)."""
    empty = {"type": "FeatureCollection", "features": []}
    flood = _flood_union_from_features(flood_fc, min_depth_m=min_depth_m)
    if flood is None or flood.is_empty:
        return empty, {
            "ok": False,
            "reason": "sem_mancha_moderada_critica",
            "escolas": 0,
            "saude": 0,
            "abrigos": 0,
            "total": 0,
            "matriculas_expostas": 0,
            "leitos_sus_expostos": 0,
        }

    flood_geojson = json.dumps(mapping(flood))
    features: list[dict[str, Any]] = []
    counts = {"escola": 0, "saude": 0, "abrigo": 0}
    matriculas = 0
    leitos = 0

    # Auto-heal: sem INEP seed/microdados, tenta OSM (amenity=school)
    if db.query(EscolaInep).filter(EscolaInep.municipio_id == muni.id).count() == 0:
        try:
            from app.data_connectors.inep_educacao_collector import sync_educacao_municipio

            sync_educacao_municipio(db, muni)
            db.commit()
        except Exception as exc:
            logger.info("sync escolas %s: %s", muni.codigo_ibge, exc)

    escolas = (
        db.query(EscolaInep)
        .filter(
            EscolaInep.municipio_id == muni.id,
            EscolaInep.geom.isnot(None),
            func.ST_Intersects(
                EscolaInep.geom,
                func.ST_SetSRID(func.ST_GeomFromGeoJSON(flood_geojson), 4326),
            ),
        )
        .order_by(func.coalesce(EscolaInep.matriculas_total, 0).desc())
        .limit(MAX_HIT)
        .all()
    )
    for esc in escolas:
        xy = _point_xy(esc.geom)
        if not xy:
            continue
        band, depth = _band_for_point(xy[0], xy[1], flood_fc)
        if band not in ("moderada", "critica") and band is not None:
            # ST_Intersects usou união moderada+crítica; superficial sozinha não entra
            pass
        mat = int(esc.matriculas_total or 0)
        matriculas += mat
        features.append(
            _feat(
                lon=xy[0],
                lat=xy[1],
                categoria="escola",
                nome=esc.nome or f"Escola {esc.codigo_inep}",
                subtipo=esc.dependencia,
                depth_band=band or "moderada",
                depth_m=depth,
                extra={
                    "codigo_inep": esc.codigo_inep,
                    "matriculas_total": mat,
                },
            )
        )
        counts["escola"] += 1

    saude = (
        db.query(EstabelecimentoSaude)
        .filter(
            EstabelecimentoSaude.municipio_id == muni.id,
            EstabelecimentoSaude.geom.isnot(None),
            func.ST_Intersects(
                EstabelecimentoSaude.geom,
                func.ST_SetSRID(func.ST_GeomFromGeoJSON(flood_geojson), 4326),
            ),
        )
        .order_by(func.coalesce(EstabelecimentoSaude.leitos_sus, 0).desc())
        .limit(MAX_HIT)
        .all()
    )
    for est in saude:
        xy = _point_xy(est.geom)
        if not xy:
            continue
        band, depth = _band_for_point(xy[0], xy[1], flood_fc)
        beds = int(est.leitos_sus or 0)
        leitos += beds
        features.append(
            _feat(
                lon=xy[0],
                lat=xy[1],
                categoria="saude",
                nome=est.nome,
                subtipo=est.tipo,
                depth_band=band or "moderada",
                depth_m=depth,
                extra={
                    "cnes_codigo": est.cnes_codigo,
                    "leitos_sus": beds,
                    "esf": bool(est.esf),
                },
            )
        )
        counts["saude"] += 1

    plan = (
        db.query(ContingencyPlan)
        .filter(
            ContingencyPlan.municipio_id == muni.id,
            ContingencyPlan.status == "ATIVO",
        )
        .order_by(ContingencyPlan.updated_at.desc())
        .first()
    )
    for i, p in enumerate((plan.pontos_apoio or []) if plan else []):
        if not isinstance(p, dict):
            continue
        lon = lat = None
        coords = p.get("coordinates")
        geom = p.get("geometry") or p.get("geojson")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            lon, lat = float(coords[0]), float(coords[1])
        elif isinstance(geom, dict):
            g = geom.get("geometry") if geom.get("type") == "Feature" else geom
            c = (g or {}).get("coordinates") if isinstance(g, dict) else None
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                lon, lat = float(c[0]), float(c[1])
        if lon is None or lat is None:
            continue
        from shapely.geometry import Point

        if not flood.contains(Point(lon, lat)):
            continue
        band, depth = _band_for_point(lon, lat, flood_fc)
        features.append(
            _feat(
                lon=lon,
                lat=lat,
                categoria="abrigo",
                nome=str(p.get("nome") or f"Ponto de apoio {i + 1}"),
                subtipo=str(p.get("tipo") or "apoio"),
                depth_band=band or "moderada",
                depth_m=depth,
            )
        )
        counts["abrigo"] += 1

    # Crítica primeiro na lista
    features.sort(
        key=lambda f: (
            -BAND_RANK.get((f.get("properties") or {}).get("depth_band"), 0),
            (f.get("properties") or {}).get("categoria") or "",
        )
    )
    features = features[:MAX_HIT]

    meta = {
        "ok": True,
        "escolas": counts["escola"],
        "saude": counts["saude"],
        "abrigos": counts["abrigo"],
        "total": len(features),
        "matriculas_expostas": matriculas,
        "leitos_sus_expostos": leitos,
        "depth_threshold_m": min_depth_m,
    }
    return {"type": "FeatureCollection", "features": features}, meta
