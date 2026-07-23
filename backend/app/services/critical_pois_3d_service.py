"""POIs de equipamentos críticos para o gêmeo 3D (17f.3).

Consolida escolas (INEP), saúde (CNES), abrigos/pontos de apoio da
contingência e equipamentos OSM relevantes em GeoJSON de pontos com rótulos.
"""

from __future__ import annotations

from typing import Any

from geoalchemy2.shape import to_shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ContingencyPlan,
    EscolaInep,
    EstabelecimentoSaude,
    InfraestruturaUrbana,
    Municipio,
)

COLOR_BY_CATEGORY = {
    "escola": "#38bdf8",
    "saude": "#22c55e",
    "abrigo": "#fbbf24",
    "equipamento": "#a78bfa",
}

MAX_ESCOLAS = 80
MAX_SAUDE = 60
MAX_INFRA = 40


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


def _feature(
    *,
    lon: float,
    lat: float,
    categoria: str,
    nome: str,
    subtipo: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    color = COLOR_BY_CATEGORY.get(categoria, "#a78bfa")
    label = (nome or categoria).strip()
    if len(label) > 42:
        label = label[:39] + "…"
    props: dict[str, Any] = {
        "categoria": categoria,
        "nome": nome,
        "subtipo": subtipo,
        "label": label,
        "fonte_referencia": {
            "escola": "INEP Censo Escolar",
            "saude": "CNES / DataSUS",
            "abrigo": "Plano de contingência",
            "equipamento": "OSM / bases locais",
        }.get(categoria, "Sinidu+Clima"),
        "_fill": color,
        "_fillOpacity": 0.95,
        "_radius": 7 if categoria != "abrigo" else 8,
        "_stroke": "#0f172a",
    }
    if extra:
        props.update(extra)
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def build_critical_pois_geojson(
    db: Session,
    codigo_ibge: str,
    *,
    include_escolas: bool = True,
    include_saude: bool = True,
    include_abrigos: bool = True,
    include_equipamentos: bool = True,
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
    counts = {"escola": 0, "saude": 0, "abrigo": 0, "equipamento": 0}

    if include_escolas:
        escolas = (
            db.query(EscolaInep)
            .filter(EscolaInep.municipio_id == muni.id, EscolaInep.geom.isnot(None))
            .order_by(func.coalesce(EscolaInep.matriculas_total, 0).desc())
            .limit(MAX_ESCOLAS)
            .all()
        )
        for esc in escolas:
            xy = _point_xy(esc.geom)
            if not xy:
                continue
            features.append(
                _feature(
                    lon=xy[0],
                    lat=xy[1],
                    categoria="escola",
                    nome=esc.nome or f"Escola {esc.codigo_inep}",
                    subtipo=esc.dependencia,
                    extra={
                        "codigo_inep": esc.codigo_inep,
                        "matriculas_total": int(esc.matriculas_total or 0),
                        "qualidade_dado": "Oficial",
                    },
                )
            )
            counts["escola"] += 1

    if include_saude:
        estabelecimentos = (
            db.query(EstabelecimentoSaude)
            .filter(
                EstabelecimentoSaude.municipio_id == muni.id,
                EstabelecimentoSaude.geom.isnot(None),
            )
            .order_by(func.coalesce(EstabelecimentoSaude.leitos_sus, 0).desc())
            .limit(MAX_SAUDE)
            .all()
        )
        for est in estabelecimentos:
            xy = _point_xy(est.geom)
            if not xy:
                continue
            features.append(
                _feature(
                    lon=xy[0],
                    lat=xy[1],
                    categoria="saude",
                    nome=est.nome,
                    subtipo=est.tipo,
                    extra={
                        "cnes_codigo": est.cnes_codigo,
                        "leitos_sus": int(est.leitos_sus or 0),
                        "esf": bool(est.esf),
                        "qualidade_dado": "Oficial",
                    },
                )
            )
            counts["saude"] += 1

    if include_abrigos:
        plan = (
            db.query(ContingencyPlan)
            .filter(
                ContingencyPlan.municipio_id == muni.id,
                ContingencyPlan.status == "ATIVO",
            )
            .order_by(ContingencyPlan.updated_at.desc())
            .first()
        )
        pontos = (plan.pontos_apoio or []) if plan else []
        for i, p in enumerate(pontos):
            if not isinstance(p, dict):
                continue
            coords = p.get("coordinates")
            geom = p.get("geometry") or p.get("geojson")
            lon = lat = None
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                lon, lat = float(coords[0]), float(coords[1])
            elif isinstance(geom, dict):
                g = geom.get("geometry") if geom.get("type") == "Feature" else geom
                c = (g or {}).get("coordinates") if isinstance(g, dict) else None
                if isinstance(c, (list, tuple)) and len(c) >= 2:
                    lon, lat = float(c[0]), float(c[1])
            if lon is None or lat is None:
                continue
            features.append(
                _feature(
                    lon=lon,
                    lat=lat,
                    categoria="abrigo",
                    nome=str(p.get("nome") or f"Ponto de apoio {i + 1}"),
                    subtipo=str(p.get("tipo") or "apoio"),
                    extra={
                        "plan_id": plan.id if plan else None,
                        "qualidade_dado": "Derivado",
                    },
                )
            )
            counts["abrigo"] += 1

    if include_equipamentos:
        # Complemento OSM: abrigos/defesa civil; saúde/escolas só se bases oficiais vazias
        tipos_ok = ["ginasio", "abrigo", "defesa_civil"]
        if counts["saude"] == 0:
            tipos_ok.extend(["hospital", "ubs"])
        if counts["escola"] == 0:
            tipos_ok.append("escola")
        items = (
            db.query(InfraestruturaUrbana)
            .filter(
                InfraestruturaUrbana.municipio_id == muni.id,
                InfraestruturaUrbana.tipo.in_(tipos_ok),
                InfraestruturaUrbana.geom.isnot(None),
            )
            .limit(MAX_INFRA)
            .all()
        )
        for item in items:
            xy = _point_xy(item.geom)
            if not xy:
                continue
            tipo = str(item.tipo or "").lower()
            if tipo in ("hospital", "ubs"):
                cat = "saude"
            elif tipo in ("ginasio", "abrigo"):
                cat = "abrigo"
            elif tipo == "escola":
                cat = "escola"
            else:
                cat = "equipamento"
            features.append(
                _feature(
                    lon=xy[0],
                    lat=xy[1],
                    categoria=cat,
                    nome=item.nome,
                    subtipo=item.tipo,
                    extra={
                        "subgrupo": item.subgrupo,
                        "qualidade_dado": "Estimado",
                        "fonte_referencia": "OSM / bases locais",
                    },
                )
            )
            counts[cat] += 1

    return {
        "type": "FeatureCollection",
        "features": features,
        "meta": {
            "codigo_ibge": code,
            "municipio": muni.nome,
            "uf": muni.uf,
            "count": len(features),
            "por_categoria": counts,
        },
    }
