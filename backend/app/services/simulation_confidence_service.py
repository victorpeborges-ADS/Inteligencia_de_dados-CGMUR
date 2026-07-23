"""Selo de confiança e validação S2ID das simulações (17g.2e / 17g.2a).

Expõe resolução do DEM, acurácia vertical, método e acerto espacial contra
eventos históricos oficiais — sem inventar precisão inexistente.
"""

from __future__ import annotations

import json
from typing import Any

from shapely.geometry import shape
from shapely.ops import unary_union
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Bairro, HistoricoDesastreS2ID, Municipio

FLOOD_TYPES = {
    "inundação",
    "inundacao",
    "alagamento",
    "alagamento urbano",
    "enchente",
    "enxurrada",
}

# Buffer ~50 m em graus (≈ equator; bom o suficiente para hit-test de pontos S2ID)
POINT_BUFFER_DEG = 0.00045


def _is_flood_type(tipo: str | None) -> bool:
    t = (tipo or "").strip().lower()
    if not t:
        return False
    if t in FLOOD_TYPES:
        return True
    return any(k in t for k in ("inund", "alag", "enchent", "enxurr"))


def _dem_quality_tier(dem_source: str | None, dem_available: bool) -> tuple[str, str]:
    """Retorna (selo_qualidade, nivel) a partir da fonte do DEM."""
    if not dem_available:
        return "Derivado", "baixa"
    src = (dem_source or "").lower()
    if "lidar" in src or "ndsm" in src or "local" in src:
        return "Observado", "alta"
    if "srtm" in src or "copernicus" in src or "merit" in src:
        return "Estimado", "media"
    if dem_source:
        return "Estimado", "media"
    return "Derivado", "baixa"


def _resolution_score(resolution_m: float | None) -> str:
    if resolution_m is None:
        return "baixa"
    if resolution_m <= 5:
        return "alta"
    if resolution_m <= 15:
        return "media"
    return "baixa"


def _worst(*niveis: str) -> str:
    order = {"alta": 0, "media": 1, "baixa": 2}
    return max(niveis, key=lambda n: order.get(n, 9))


def build_confidence_seal(simulation_meta: dict[str, Any] | None) -> dict[str, Any]:
    """Monta o selo de confiança a partir dos metadados da simulação."""
    meta = simulation_meta or {}
    dem_available = bool(meta.get("dem_available"))
    dem_source = meta.get("dem_source")
    method = meta.get("method") or ("dem" if dem_available else "heuristic")
    res_m = meta.get("dem_resolution_m")
    try:
        res_m_f = float(res_m) if res_m is not None else None
    except (TypeError, ValueError):
        res_m_f = None
    try:
        vert = float(meta["vertical_accuracy_m"]) if meta.get("vertical_accuracy_m") is not None else None
    except (TypeError, ValueError):
        vert = None

    selo, dem_nivel = _dem_quality_tier(dem_source, dem_available)
    res_nivel = _resolution_score(res_m_f) if dem_available else "baixa"
    method_nivel = "alta" if "dem" in str(method).lower() and dem_available else "baixa"
    if method == "heuristic":
        method_nivel = "baixa"

    nivel = _worst(dem_nivel, res_nivel, method_nivel)

    fatores = [
        f"DEM: {dem_source or 'indisponível'} ({selo})",
        f"Resolução: ~{res_m_f:.0f} m" if res_m_f is not None else "Resolução: desconhecida",
        f"Incerteza vertical: ±{vert:.0f} m" if vert is not None else "Incerteza vertical: n/d",
        f"Método: {method}",
    ]

    interpretacao = {
        "alta": "Base topográfica observada (ex.: LiDAR) e método físico — uso operacional com ressalvas locais.",
        "media": "DEM nacional (ex.: SRTM) ou resolução intermediária — adequado a priorização territorial.",
        "baixa": "Heurística ou DEM grosseiro — use para sensibilização; não como laudo de engenharia.",
    }[nivel]

    return {
        "selo_qualidade": selo,
        "nivel_confianca": nivel,
        "dem_source": dem_source,
        "dem_resolution_m": res_m_f,
        "vertical_accuracy_m": vert,
        "method": method,
        "model_version": meta.get("model_version"),
        "fatores": fatores,
        "interpretacao": interpretacao,
        "padrao": "Oficial | Observado | Estimado | Derivado",
    }


def _flood_union_from_geometry(geometry: dict[str, Any] | None):
    if not geometry:
        return None
    feats = geometry.get("features") if geometry.get("type") == "FeatureCollection" else None
    if feats is not None:
        shapes = []
        for f in feats:
            props = f.get("properties") or {}
            if props.get("layer_type") and props.get("layer_type") != "flood_band":
                continue
            try:
                g = shape(f["geometry"])
                if not g.is_empty:
                    shapes.append(g)
            except Exception:
                continue
        if not shapes:
            return None
        return unary_union(shapes)
    try:
        g = shape(geometry if "coordinates" in geometry else geometry.get("geometry") or geometry)
        return g if not g.is_empty else None
    except Exception:
        return None


def validate_against_s2id(
    db: Session,
    muni: Municipio,
    *,
    flood_geometry: dict[str, Any] | None,
    affected_bairros: list[str] | None = None,
) -> dict[str, Any]:
    """Compara mancha simulada com pontos/bairros de eventos S2ID de inundação."""
    events = (
        db.query(HistoricoDesastreS2ID)
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .all()
    )
    flood_events = [e for e in events if _is_flood_type(e.tipo_desastre)]

    flood_union = _flood_union_from_geometry(flood_geometry)
    points_with_geom = 0
    points_hit = 0
    hit_ids: list[int] = []

    for ev in flood_events:
        if ev.geom is None:
            continue
        try:
            geojson = db.scalar(ev.geom.ST_AsGeoJSON())
            if not geojson:
                continue
            pt = shape(json.loads(geojson))
            if pt.is_empty:
                continue
            points_with_geom += 1
            if flood_union is None:
                continue
            # buffer para tolerar geocodificação grosseira do S2ID
            if flood_union.buffer(POINT_BUFFER_DEG).intersects(pt):
                points_hit += 1
                hit_ids.append(ev.id)
        except Exception:
            continue

    hit_rate = round(points_hit / points_with_geom, 3) if points_with_geom else None

    # Bairros com histórico S2ID (interseção ponto×bairro)
    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    historicos: set[str] = set()
    for b in bairros:
        if b.geom is None:
            continue
        try:
            n = (
                db.query(HistoricoDesastreS2ID)
                .filter(
                    HistoricoDesastreS2ID.municipio_id == muni.id,
                    HistoricoDesastreS2ID.geom.isnot(None),
                    func.ST_Intersects(b.geom, HistoricoDesastreS2ID.geom),
                )
                .all()
            )
            if any(_is_flood_type(e.tipo_desastre) for e in n):
                historicos.add(b.nome)
        except Exception:
            continue

    simulados = {str(x) for x in (affected_bairros or []) if x}
    inter = historicos & simulados
    union = historicos | simulados
    jaccard = round(len(inter) / len(union), 3) if union else None

    if points_with_geom == 0 and not historicos:
        acordo = "insuficiente"
        narrativa = "Sem eventos S2ID de inundação georreferenciados neste município para validar a mancha."
    elif hit_rate is not None and hit_rate >= 0.6:
        acordo = "alta"
        narrativa = (
            f"{points_hit}/{points_with_geom} eventos S2ID caem na mancha simulada "
            f"(hit rate {hit_rate:.0%})."
        )
    elif hit_rate is not None and hit_rate >= 0.3:
        acordo = "media"
        narrativa = (
            f"{points_hit}/{points_with_geom} eventos S2ID na mancha (hit rate {hit_rate:.0%}) — "
            "parcialmente alinhado ao histórico."
        )
    elif hit_rate is not None:
        acordo = "baixa"
        narrativa = (
            f"Poucos eventos S2ID na mancha ({points_hit}/{points_with_geom}). "
            "Revise precipitação do cenário ou DEM local."
        )
    elif jaccard is not None and jaccard >= 0.4:
        acordo = "media"
        narrativa = f"Sobreposição de bairros histórico×simulado (Jaccard {jaccard:.0%})."
    else:
        acordo = "baixa"
        narrativa = "Validação espacial limitada — poucos pontos S2ID na mancha ou sem geometria de inundação."

    return {
        "disponivel": points_with_geom > 0 or bool(historicos),
        "fonte": "S2ID / CENAD",
        "qualidade": "Oficial",
        "eventos_inundacao_total": len(flood_events),
        "eventos_com_geometria": points_with_geom,
        "eventos_na_mancha": points_hit,
        "hit_rate": hit_rate,
        "bairros_historicos": sorted(historicos)[:20],
        "bairros_simulados": sorted(simulados)[:20],
        "bairros_em_comum": sorted(inter)[:20],
        "jaccard_bairros": jaccard,
        "acordo": acordo,
        "narrativa": narrativa,
        "limitacao": (
            "S2ID registra pontos/eventos, não polígonos oficiais de área afetada. "
            "O hit rate mede se o histórico cai dentro da mancha simulada (±50 m)."
        ),
    }


def enrich_simulation_confidence(
    db: Session,
    muni: Municipio,
    simulation_meta: dict[str, Any] | None,
    *,
    flood_geometry: dict[str, Any] | None = None,
    affected_bairros: list[str] | None = None,
) -> dict[str, Any]:
    """Anexa `selo_confianca` e `validacao_s2id` ao simulation_meta."""
    meta = dict(simulation_meta or {})
    seal = build_confidence_seal(meta)
    validation = validate_against_s2id(
        db,
        muni,
        flood_geometry=flood_geometry,
        affected_bairros=affected_bairros,
    )
    # Confiança final: piora se validação S2ID disponível e acordo baixo
    nivel = seal["nivel_confianca"]
    if validation.get("disponivel") and validation.get("acordo") == "baixa":
        nivel = _worst(nivel, "baixa")
    elif validation.get("disponivel") and validation.get("acordo") == "media":
        nivel = _worst(nivel, "media")
    seal = {**seal, "nivel_confianca": nivel}
    meta["selo_confianca"] = seal
    meta["validacao_s2id"] = validation
    try:
        from app.services.method_note_service import attach_method_note

        meta = attach_method_note(
            meta,
            tipo="chuva",
            municipio={
                "codigo_ibge": muni.codigo_ibge,
                "nome": muni.nome,
                "uf": muni.uf,
            },
        )
    except Exception:
        pass
    return meta
