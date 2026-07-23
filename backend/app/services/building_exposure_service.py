"""Exposição climática por edifício (17b.1 / 17b.2) e painel do cenário (17b.5).

Cruza manchas de inundação (`flood_bands`) com footprints LOD1, escolas INEP
e unidades CNES — sem inventar polígonos oficiais de área afetada.

17b.2: distribui população do setor censitário pelos footprints (peso ≈ área × pavimentos).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Edificacao, EscolaInep, EstabelecimentoSaude, Municipio, SetorCensitario

logger = logging.getLogger(__name__)

BAND_RANK = {"superficial": 1, "moderada": 2, "critica": 3}
BAND_DEPTH_M = {"superficial": 0.2, "moderada": 0.55, "critica": 1.1}
BAND_COLOR = {
    "superficial": "#38bdf8",
    "moderada": "#0284c7",
    "critica": "#1e3a8a",
}
MAX_SAMPLE_FEATURES = 400
MAX_LIST = 25
LEVEL_HEIGHT_M = 3.0


def _flood_band_features(flood_geometry: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not flood_geometry:
        return []
    feats = flood_geometry.get("features") if flood_geometry.get("type") == "FeatureCollection" else None
    if not feats:
        return []
    out = []
    for f in feats:
        props = f.get("properties") or {}
        if props.get("layer_type") and props.get("layer_type") != "flood_band":
            continue
        band = props.get("depth_band") or "moderada"
        if band not in BAND_RANK:
            band = "moderada"
        try:
            g = shape(f["geometry"])
            if g.is_empty:
                continue
            out.append({"band": band, "geom": g, "props": props})
        except Exception:
            continue
    return out


def _flood_union(bands: list[dict[str, Any]]):
    shapes = [b["geom"] for b in bands]
    if not shapes:
        return None
    return unary_union(shapes)


def _worst_band_for_geom(building_geom, bands: list[dict[str, Any]]) -> tuple[str | None, float]:
    worst = None
    rank = 0
    depth = 0.0
    for b in bands:
        try:
            if not building_geom.intersects(b["geom"]):
                continue
        except Exception:
            continue
        r = BAND_RANK.get(b["band"], 0)
        if r > rank:
            rank = r
            worst = b["band"]
            props = b.get("props") or {}
            lo = props.get("depth_min_m")
            hi = props.get("depth_max_m")
            try:
                if lo is not None and hi is not None and float(hi) < 100:
                    depth = (float(lo) + float(hi)) / 2.0
                else:
                    depth = BAND_DEPTH_M.get(worst, 0.3)
            except (TypeError, ValueError):
                depth = BAND_DEPTH_M.get(worst, 0.3)
    return worst, depth


def building_population_weight(geom, pavimentos: int | None, altura_m: float | None) -> float:
    """Peso ≈ área do footprint × pavimentos (proxy de área construída)."""
    floors = int(pavimentos or 0) or max(1, int(round(float(altura_m or 6.0) / LEVEL_HEIGHT_M)))
    return max(float(geom.area), 1e-16) * float(floors)


def allocate_population_by_weight(
    members: list[dict[str, Any]],
    population: int,
) -> dict[int, int]:
    """Distribui `population` pelos membros com chave `id` e `weight` (método do resto maior)."""
    if not members or population <= 0:
        return {int(m["id"]): 0 for m in members}
    total_w = sum(float(m.get("weight") or 0) for m in members) or 1.0
    raw = [(int(m["id"]), population * float(m.get("weight") or 0) / total_w) for m in members]
    floors = {i: int(v) for i, v in raw}
    rem = int(population) - sum(floors.values())
    fracs = sorted(((v - int(v), i) for i, v in raw), reverse=True)
    for k in range(max(0, rem)):
        floors[fracs[k % len(fracs)][1]] += 1
    return floors


def _empty_exposure(n_buildings: int, affected_population: int, precipitacao_mm: float | None) -> dict[str, Any]:
    return {
        "disponivel": False,
        "motivo": "Sem mancha de inundação para cruzar com edificações.",
        "edificios_total": n_buildings,
        "edificios_expostos": 0,
        "por_faixa": {"superficial": 0, "moderada": 0, "critica": 0},
        "populacao_exposta": int(affected_population or 0),
        "populacao_edificios_estimada": 0,
        "escolas_expostas": {"n": 0, "matriculas": 0},
        "saude_exposta": {"n": 0, "ubs": 0, "hospital": 0},
        "amostra": [],
        "geojson": {"type": "FeatureCollection", "features": []},
        "precipitacao_mm": precipitacao_mm,
        "limitacao": "Requer geometria de flood_band na simulação pluvial.",
    }


def _population_via_setores(
    db: Session,
    muni: Municipio,
    exposed: list[dict[str, Any]],
) -> dict[int, int]:
    """Aloca pop. do setor a todos os footprints do setor; retorna só os expostos."""
    if not exposed:
        return {}

    setores = (
        db.query(SetorCensitario)
        .filter(
            SetorCensitario.municipio_id == muni.id,
            SetorCensitario.geom.isnot(None),
            SetorCensitario.populacao > 0,
        )
        .all()
    )
    if not isinstance(setores, (list, tuple)) or not setores:
        return {}

    # setor_id -> {pop, members: [{id, weight}], exposed_ids}
    buckets: dict[Any, dict[str, Any]] = {}
    for row in setores:
        try:
            pop = int(row.populacao or 0)
        except (TypeError, ValueError):
            pop = 0
        if pop <= 0:
            continue
        buckets[row.id] = {"pop": pop, "geom": row.geom, "codigo": row.codigo_setor}

    if not buckets:
        return {}

    # Mapear cada edifício exposto ao setor (centroid)
    exposed_by_setor: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for item in exposed:
        g = item["geom"]
        c = g.centroid
        cjson = json.dumps({"type": "Point", "coordinates": [c.x, c.y]})
        matched = None
        for sid, info in buckets.items():
            try:
                ok = db.scalar(
                    func.ST_Contains(
                        info["geom"],
                        func.ST_SetSRID(func.ST_GeomFromGeoJSON(cjson), 4326),
                    )
                )
                if ok:
                    matched = sid
                    break
            except Exception:
                continue
        if matched is None:
            # fallback: intersects footprint
            try:
                gjson = json.dumps(mapping(g))
                for sid, info in buckets.items():
                    ok = db.scalar(
                        func.ST_Intersects(
                            info["geom"],
                            func.ST_SetSRID(func.ST_GeomFromGeoJSON(gjson), 4326),
                        )
                    )
                    if ok:
                        matched = sid
                        break
            except Exception:
                matched = None
        if matched is not None:
            exposed_by_setor[matched].append(item)

    if not exposed_by_setor:
        return {}

    out: dict[int, int] = {}
    for sid, exp_list in exposed_by_setor.items():
        info = buckets[sid]
        # Todos os footprints do setor (denominador)
        try:
            all_rows = (
                db.query(Edificacao)
                .filter(
                    Edificacao.municipio_id == muni.id,
                    Edificacao.geom.isnot(None),
                    func.ST_Intersects(Edificacao.geom, info["geom"]),
                )
                .all()
            )
        except Exception:
            all_rows = []
        if not isinstance(all_rows, (list, tuple)) or not all_rows:
            # Só entre expostos
            members = [
                {"id": e["id"], "weight": e["weight"]} for e in exp_list
            ]
            alloc = allocate_population_by_weight(members, info["pop"])
            out.update(alloc)
            continue

        members = []
        for row in all_rows:
            try:
                gjson = db.scalar(row.geom.ST_AsGeoJSON())
                if not gjson:
                    continue
                g = shape(json.loads(gjson))
                w = building_population_weight(g, row.pavimentos, float(row.altura_m or 6.0))
                members.append({"id": row.id, "weight": w})
            except Exception:
                continue
        if not members:
            continue
        alloc = allocate_population_by_weight(members, info["pop"])
        for e in exp_list:
            out[e["id"]] = int(alloc.get(e["id"], 0))
    return out


def _population_fallback_exposed(
    exposed: list[dict[str, Any]],
    affected_population: int,
) -> dict[int, int]:
    """Sem setores: reparte a população territorial do cenário entre os expostos."""
    members = [{"id": e["id"], "weight": e["weight"]} for e in exposed]
    return allocate_population_by_weight(members, int(affected_population or 0))


def compute_flood_building_exposure(
    db: Session,
    muni: Municipio,
    flood_geometry: dict[str, Any] | None,
    *,
    affected_population: int = 0,
    precipitacao_mm: float | None = None,
    ensure_buildings: bool = False,
) -> dict[str, Any]:
    """Retorna resumo de exposição + amostra GeoJSON de edifícios atingidos."""
    bands = _flood_band_features(flood_geometry)
    flood_u = _flood_union(bands)

    n_buildings = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    if n_buildings == 0 and ensure_buildings:
        try:
            from app.data_connectors.building_footprints_collector import collect_buildings_municipality

            collect_buildings_municipality(db, muni.codigo_ibge, force=False)
            n_buildings = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
        except Exception as exc:
            logger.warning("Não foi possível ingerir edificações para exposição: %s", exc)

    if flood_u is None or flood_u.is_empty:
        return _empty_exposure(n_buildings, affected_population, precipitacao_mm)

    flood_geojson = json.dumps(mapping(flood_u))
    candidatos = (
        db.query(Edificacao)
        .filter(
            Edificacao.municipio_id == muni.id,
            Edificacao.geom.isnot(None),
            func.ST_Intersects(
                Edificacao.geom,
                func.ST_SetSRID(func.ST_GeomFromGeoJSON(flood_geojson), 4326),
            ),
        )
        .all()
    )

    por_faixa = {"superficial": 0, "moderada": 0, "critica": 0}
    exposed_entries: list[dict[str, Any]] = []

    for row in candidatos:
        try:
            gjson = db.scalar(row.geom.ST_AsGeoJSON())
            if not gjson:
                continue
            g = shape(json.loads(gjson))
        except Exception:
            continue
        band, depth = _worst_band_for_geom(g, bands)
        if not band:
            continue
        por_faixa[band] = por_faixa.get(band, 0) + 1
        altura = float(row.altura_m or 6.0)
        weight = building_population_weight(g, row.pavimentos, altura)
        exposed_entries.append({
            "id": row.id,
            "osm_id": row.osm_id,
            "nome": row.nome,
            "uso": row.uso,
            "altura_m": altura,
            "pavimentos": row.pavimentos,
            "fonte_altura": row.fonte_altura,
            "qualidade": row.qualidade,
            "depth_band": band,
            "depth_m": round(depth, 2),
            "geom": g,
            "gjson": gjson,
            "weight": weight,
        })

    # 17b.2 — população por edifício
    pop_map: dict[int, int] = {}
    metodo_pop = "indisponivel"
    try:
        pop_map = _population_via_setores(db, muni, exposed_entries)
        if pop_map:
            metodo_pop = "setor_censitario_area_x_pavimentos"
    except Exception as exc:
        logger.debug("Alocação por setor falhou: %s", exc)
        pop_map = {}
    if not pop_map and exposed_entries and affected_population:
        pop_map = _population_fallback_exposed(exposed_entries, affected_population)
        metodo_pop = "cenario_territorial_repartido"

    pop_edificios = int(sum(pop_map.get(e["id"], 0) for e in exposed_entries))

    amostra: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    for entry in exposed_entries:
        pop_est = int(pop_map.get(entry["id"], 0))
        item = {
            "id": entry["id"],
            "osm_id": entry["osm_id"],
            "nome": entry["nome"],
            "uso": entry["uso"],
            "altura_m": entry["altura_m"],
            "pavimentos": entry["pavimentos"],
            "fonte_altura": entry["fonte_altura"],
            "qualidade": entry["qualidade"],
            "depth_band": entry["depth_band"],
            "depth_m": entry["depth_m"],
            "populacao_estimada": pop_est,
        }
        if len(amostra) < MAX_LIST:
            amostra.append(item)
        if len(features) < MAX_SAMPLE_FEATURES:
            features.append({
                "type": "Feature",
                "geometry": (
                    json.loads(entry["gjson"])
                    if isinstance(entry["gjson"], str)
                    else mapping(entry["geom"])
                ),
                "properties": {
                    **item,
                    "_extrusionHeightM": entry["altura_m"],
                    "_fill": BAND_COLOR.get(entry["depth_band"], "#0284c7"),
                    "layer_type": "building_flood_exposure",
                    "fill_color": BAND_COLOR.get(entry["depth_band"], "#0284c7"),
                },
            })

    amostra.sort(key=lambda x: BAND_RANK.get(x["depth_band"], 0), reverse=True)

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
        .all()
    )
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
        .all()
    )
    ubs = sum(1 for s in saude if (s.tipo or "").lower() in {"ubs", "posto", "centro de saude", "centro de saúde"})
    hosp = sum(1 for s in saude if "hospital" in (s.tipo or "").lower())

    expostos = sum(por_faixa.values())
    return {
        "disponivel": True,
        "edificios_total": n_buildings,
        "edificios_expostos": expostos,
        "por_faixa": por_faixa,
        "populacao_exposta": int(affected_population or 0),
        "populacao_edificios_estimada": pop_edificios,
        "populacao_metodo": metodo_pop,
        "escolas_expostas": {
            "n": len(escolas),
            "matriculas": int(sum(int(e.matriculas_total or 0) for e in escolas)),
            "nomes": [e.nome for e in escolas[:8]],
        },
        "saude_exposta": {
            "n": len(saude),
            "ubs": ubs,
            "hospital": hosp,
            "nomes": [s.nome for s in saude[:8]],
        },
        "amostra": amostra[:MAX_LIST],
        "geojson": {"type": "FeatureCollection", "features": features},
        "precipitacao_mm": precipitacao_mm,
        "limitacao": (
            "Cruzamento footprint×mancha simulada. "
            "População por edifício (17b.2): setor censitário × área construída (área×pavimentos); "
            f"método={metodo_pop}."
        ),
    }


def enrich_simulation_building_exposure(
    db: Session,
    muni: Municipio,
    simulation_meta: dict[str, Any] | None,
    *,
    flood_geometry: dict[str, Any] | None,
    affected_population: int = 0,
    precipitacao_mm: float | None = None,
) -> dict[str, Any]:
    meta = dict(simulation_meta or {})
    try:
        expo = compute_flood_building_exposure(
            db,
            muni,
            flood_geometry,
            affected_population=affected_population,
            precipitacao_mm=precipitacao_mm,
            ensure_buildings=False,
        )
    except Exception as exc:
        logger.warning("Exposição edifícios falhou: %s", exc)
        expo = {
            "disponivel": False,
            "motivo": str(exc),
            "edificios_expostos": 0,
            "edificios_total": 0,
            "por_faixa": {"superficial": 0, "moderada": 0, "critica": 0},
            "populacao_exposta": int(affected_population or 0),
            "populacao_edificios_estimada": 0,
            "escolas_expostas": {"n": 0, "matriculas": 0},
            "saude_exposta": {"n": 0, "ubs": 0, "hospital": 0},
            "amostra": [],
            "geojson": {"type": "FeatureCollection", "features": []},
        }
    meta["exposicao_cenario"] = {k: v for k, v in expo.items() if k != "geojson"}
    meta["buildings_exposed"] = expo.get("geojson")

    # 17b.4 — deslizamento × edifício (mesmo FC da chuva extrema)
    try:
        slide = compute_landslide_building_exposure(
            db,
            muni,
            flood_geometry,
            affected_population=affected_population,
            precipitacao_mm=precipitacao_mm,
        )
        meta["exposicao_deslizamento"] = {k: v for k, v in slide.items() if k != "geojson"}
        meta["buildings_landslide"] = slide.get("geojson")
    except Exception as exc:
        logger.warning("Exposição deslizamento×edifício falhou: %s", exc)

    return meta


# ---------------------------------------------------------------------------
# 17b.3 / 17b.4 — calor e deslizamento × footprint
# ---------------------------------------------------------------------------

HEAT_BAND_RANK = {"leve": 1, "moderada": 2, "severa": 3}
HEAT_BAND_COLOR = {"leve": "#fbbf24", "moderada": "#f97316", "severa": "#ef4444"}
LANDSLIDE_COLOR = "#dc2626"
SLOPE_BANDS = (
    ("moderada", 12.0, 30.0),
    ("alta", 30.0, 45.0),
    ("critica", 45.0, 90.0),
)


def _features_by_layer(
    geometry: dict[str, Any] | None,
    layer_type: str,
) -> list[dict[str, Any]]:
    if not geometry:
        return []
    feats = geometry.get("features") if geometry.get("type") == "FeatureCollection" else None
    if not feats:
        return []
    out = []
    for f in feats:
        props = f.get("properties") or {}
        if props.get("layer_type") != layer_type:
            continue
        try:
            g = shape(f["geometry"])
            if g.is_empty:
                continue
            out.append({"geom": g, "props": props})
        except Exception:
            continue
    return out


def _count_buildings(db: Session, muni: Municipio) -> int:
    return db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()


def _candidates_intersecting(
    db: Session,
    muni: Municipio,
    union_geom,
) -> list:
    if union_geom is None or union_geom.is_empty:
        return []
    geojson = json.dumps(mapping(union_geom))
    return (
        db.query(Edificacao)
        .filter(
            Edificacao.municipio_id == muni.id,
            Edificacao.geom.isnot(None),
            func.ST_Intersects(
                Edificacao.geom,
                func.ST_SetSRID(func.ST_GeomFromGeoJSON(geojson), 4326),
            ),
        )
        .all()
    )


def _attach_population(
    db: Session,
    muni: Municipio,
    exposed_entries: list[dict[str, Any]],
    affected_population: int,
) -> tuple[dict[int, int], str]:
    pop_map: dict[int, int] = {}
    metodo = "indisponivel"
    try:
        pop_map = _population_via_setores(db, muni, exposed_entries)
        if pop_map:
            metodo = "setor_censitario_area_x_pavimentos"
    except Exception as exc:
        logger.debug("Alocação pop. falhou: %s", exc)
        pop_map = {}
    if not pop_map and exposed_entries and affected_population:
        pop_map = _population_fallback_exposed(exposed_entries, affected_population)
        metodo = "cenario_territorial_repartido"
    return pop_map, metodo


def _slope_band(mean_slope: float) -> str:
    for name, lo, hi in SLOPE_BANDS:
        if lo <= mean_slope < hi:
            return name
    return "alta" if mean_slope >= 30 else "moderada"


def compute_landslide_building_exposure(
    db: Session,
    muni: Municipio,
    hazard_geometry: dict[str, Any] | None,
    *,
    affected_population: int = 0,
    precipitacao_mm: float | None = None,
) -> dict[str, Any]:
    """17b.4 — footprints em zonas de deslizamento (layer_type=landslide)."""
    zones = _features_by_layer(hazard_geometry, "landslide")
    n_buildings = _count_buildings(db, muni)
    if not zones:
        return {
            "disponivel": False,
            "motivo": "Sem zonas de deslizamento neste cenário.",
            "edificios_total": n_buildings,
            "edificios_expostos": 0,
            "por_faixa": {"moderada": 0, "alta": 0, "critica": 0},
            "populacao_edificios_estimada": 0,
            "slope_threshold_deg": None,
            "amostra": [],
            "geojson": {"type": "FeatureCollection", "features": []},
            "precipitacao_mm": precipitacao_mm,
        }

    union = unary_union([z["geom"] for z in zones])
    threshold = None
    for z in zones:
        t = z["props"].get("slope_threshold_deg")
        if t is not None:
            threshold = float(t)
            break

    candidatos = _candidates_intersecting(db, muni, union)
    por_faixa = {"moderada": 0, "alta": 0, "critica": 0}
    exposed: list[dict[str, Any]] = []

    for row in candidatos:
        try:
            gjson = db.scalar(row.geom.ST_AsGeoJSON())
            if not gjson:
                continue
            g = shape(json.loads(gjson))
        except Exception:
            continue
        # pior zona que intersecta
        mean_slope = 0.0
        hit = False
        for z in zones:
            try:
                if not g.intersects(z["geom"]):
                    continue
            except Exception:
                continue
            hit = True
            try:
                mean_slope = max(mean_slope, float(z["props"].get("mean_slope_deg") or threshold or 30))
            except (TypeError, ValueError):
                mean_slope = max(mean_slope, float(threshold or 30))
        if not hit:
            continue
        faixa = _slope_band(mean_slope)
        por_faixa[faixa] = por_faixa.get(faixa, 0) + 1
        altura = float(row.altura_m or 6.0)
        exposed.append({
            "id": row.id,
            "osm_id": row.osm_id,
            "nome": row.nome,
            "uso": row.uso,
            "altura_m": altura,
            "pavimentos": row.pavimentos,
            "fonte_altura": row.fonte_altura,
            "qualidade": row.qualidade,
            "slope_band": faixa,
            "mean_slope_deg": round(mean_slope, 1),
            "slope_threshold_deg": threshold,
            "geom": g,
            "gjson": gjson,
            "weight": building_population_weight(g, row.pavimentos, altura),
        })

    pop_map, metodo = _attach_population(db, muni, exposed, affected_population)
    pop_edif = int(sum(pop_map.get(e["id"], 0) for e in exposed))

    amostra: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    exposed.sort(key=lambda x: {"critica": 3, "alta": 2, "moderada": 1}.get(x["slope_band"], 0), reverse=True)
    for entry in exposed:
        pop_est = int(pop_map.get(entry["id"], 0))
        item = {
            "id": entry["id"],
            "nome": entry["nome"],
            "uso": entry["uso"],
            "altura_m": entry["altura_m"],
            "slope_band": entry["slope_band"],
            "mean_slope_deg": entry["mean_slope_deg"],
            "populacao_estimada": pop_est,
        }
        if len(amostra) < MAX_LIST:
            amostra.append(item)
        if len(features) < MAX_SAMPLE_FEATURES:
            features.append({
                "type": "Feature",
                "geometry": json.loads(entry["gjson"]) if isinstance(entry["gjson"], str) else mapping(entry["geom"]),
                "properties": {
                    **item,
                    "_extrusionHeightM": entry["altura_m"],
                    "_fill": LANDSLIDE_COLOR,
                    "layer_type": "building_landslide_exposure",
                    "fill_color": LANDSLIDE_COLOR,
                },
            })

    return {
        "disponivel": True,
        "edificios_total": n_buildings,
        "edificios_expostos": len(exposed),
        "por_faixa": por_faixa,
        "populacao_edificios_estimada": pop_edif,
        "populacao_metodo": metodo,
        "slope_threshold_deg": threshold,
        "amostra": amostra,
        "geojson": {"type": "FeatureCollection", "features": features},
        "precipitacao_mm": precipitacao_mm,
        "limitacao": (
            "Cruzamento footprint × zonas dem_slope (limiar dinâmico por chuva). "
            f"População método={metodo}."
        ),
    }


def compute_heat_building_exposure(
    db: Session,
    muni: Municipio,
    heat_geometry: dict[str, Any] | None,
    *,
    affected_population: int = 0,
    temperatura_pico_c: float | None = None,
) -> dict[str, Any]:
    """17b.3 — footprints sob polígonos heat_band (ΔT do bairro)."""
    bands = _features_by_layer(heat_geometry, "heat_band")
    n_buildings = _count_buildings(db, muni)
    if not bands:
        return {
            "disponivel": False,
            "motivo": "Sem manchas de calor (heat_band) neste cenário.",
            "edificios_total": n_buildings,
            "edificios_expostos": 0,
            "por_faixa": {"leve": 0, "moderada": 0, "critica": 0},
            "populacao_edificios_estimada": 0,
            "amostra": [],
            "geojson": {"type": "FeatureCollection", "features": []},
            "temperatura_pico_c": temperatura_pico_c,
        }

    # Alias critica ← severa para UI alinhada
    por_faixa = {"leve": 0, "moderada": 0, "severa": 0}
    union = unary_union([b["geom"] for b in bands])
    candidatos = _candidates_intersecting(db, muni, union)
    exposed: list[dict[str, Any]] = []

    for row in candidatos:
        try:
            gjson = db.scalar(row.geom.ST_AsGeoJSON())
            if not gjson:
                continue
            g = shape(json.loads(gjson))
        except Exception:
            continue
        worst = None
        rank = 0
        delta = 0.0
        temp_local = None
        for b in bands:
            try:
                if not g.intersects(b["geom"]):
                    continue
            except Exception:
                continue
            faixa = (b["props"].get("heat_band") or "moderada").lower()
            if faixa == "critica":
                faixa = "severa"
            if faixa not in HEAT_BAND_RANK:
                faixa = "moderada"
            r = HEAT_BAND_RANK[faixa]
            if r > rank:
                rank = r
                worst = faixa
                try:
                    delta = float(b["props"].get("temp_increase_celsius") or 0)
                except (TypeError, ValueError):
                    delta = 0.0
                try:
                    tl = b["props"].get("temp_local_celsius")
                    temp_local = float(tl) if tl is not None else None
                except (TypeError, ValueError):
                    temp_local = None
        if not worst:
            continue
        por_faixa[worst] = por_faixa.get(worst, 0) + 1
        altura = float(row.altura_m or 6.0)
        exposed.append({
            "id": row.id,
            "osm_id": row.osm_id,
            "nome": row.nome,
            "uso": row.uso,
            "altura_m": altura,
            "pavimentos": row.pavimentos,
            "fonte_altura": row.fonte_altura,
            "qualidade": row.qualidade,
            "heat_band": worst,
            "delta_t_c": round(delta, 2),
            "temp_local_c": round(temp_local, 1) if temp_local is not None else None,
            "geom": g,
            "gjson": gjson,
            "weight": building_population_weight(g, row.pavimentos, altura),
        })

    pop_map, metodo = _attach_population(db, muni, exposed, affected_population)
    pop_edif = int(sum(pop_map.get(e["id"], 0) for e in exposed))

    amostra: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    exposed.sort(key=lambda x: HEAT_BAND_RANK.get(x["heat_band"], 0), reverse=True)
    for entry in exposed:
        pop_est = int(pop_map.get(entry["id"], 0))
        item = {
            "id": entry["id"],
            "nome": entry["nome"],
            "uso": entry["uso"],
            "altura_m": entry["altura_m"],
            "heat_band": entry["heat_band"],
            "delta_t_c": entry["delta_t_c"],
            "temp_local_c": entry["temp_local_c"],
            "populacao_estimada": pop_est,
            # aliases para o card genérico do painel
            "depth_band": entry["heat_band"],
            "depth_m": entry["delta_t_c"],
        }
        if len(amostra) < MAX_LIST:
            amostra.append(item)
        if len(features) < MAX_SAMPLE_FEATURES:
            color = HEAT_BAND_COLOR.get(entry["heat_band"], "#f97316")
            features.append({
                "type": "Feature",
                "geometry": json.loads(entry["gjson"]) if isinstance(entry["gjson"], str) else mapping(entry["geom"]),
                "properties": {
                    **item,
                    "_extrusionHeightM": entry["altura_m"],
                    "_fill": color,
                    "layer_type": "building_heat_exposure",
                    "fill_color": color,
                },
            })

    return {
        "disponivel": True,
        "edificios_total": n_buildings,
        "edificios_expostos": len(exposed),
        "por_faixa": {
            "leve": por_faixa.get("leve", 0),
            "moderada": por_faixa.get("moderada", 0),
            "severa": por_faixa.get("severa", 0),
            # chave critica espelha severa para UI compartilhada
            "critica": por_faixa.get("severa", 0),
            "superficial": por_faixa.get("leve", 0),
        },
        "populacao_exposta": int(affected_population or 0),
        "populacao_edificios_estimada": pop_edif,
        "populacao_metodo": metodo,
        "escolas_expostas": {"n": 0, "matriculas": 0},
        "saude_exposta": {"n": 0, "ubs": 0, "hospital": 0},
        "amostra": amostra,
        "geojson": {"type": "FeatureCollection", "features": features},
        "temperatura_pico_c": temperatura_pico_c,
        "limitacao": (
            "Cruzamento footprint × heat_band territorial (ΔT do bairro). "
            "LST pontual por edifício fica para refinamento futuro. "
            f"População método={metodo}."
        ),
    }


def enrich_simulation_heat_building_exposure(
    db: Session,
    muni: Municipio,
    simulation_meta: dict[str, Any] | None,
    *,
    heat_geometry: dict[str, Any] | None,
    affected_population: int = 0,
    temperatura_pico_c: float | None = None,
) -> dict[str, Any]:
    meta = dict(simulation_meta or {})
    try:
        expo = compute_heat_building_exposure(
            db,
            muni,
            heat_geometry,
            affected_population=affected_population,
            temperatura_pico_c=temperatura_pico_c,
        )
    except Exception as exc:
        logger.warning("Exposição calor×edifício falhou: %s", exc)
        expo = {
            "disponivel": False,
            "motivo": str(exc),
            "edificios_expostos": 0,
            "edificios_total": 0,
            "por_faixa": {"leve": 0, "moderada": 0, "severa": 0, "critica": 0, "superficial": 0},
            "populacao_exposta": int(affected_population or 0),
            "populacao_edificios_estimada": 0,
            "amostra": [],
            "geojson": {"type": "FeatureCollection", "features": []},
        }
    meta["exposicao_cenario"] = {k: v for k, v in expo.items() if k != "geojson"}
    meta["buildings_exposed"] = expo.get("geojson")
    return meta
