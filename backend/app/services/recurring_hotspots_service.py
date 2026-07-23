"""Hotspots recorrentes: histórico S2ID ∩ IRI elevado (17h.2d)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Bairro, HistoricoDesastreS2ID, Municipio
from app.services.analytical_engine import AnalyticalEngine
from app.services.simulation_confidence_service import _is_flood_type
from app.services.simulation_cache import SIMULATION_CACHE_ENABLED, _rainfall_key
from app.data_connectors.cache import cache_get_json

IRI_HOTSPOT_MIN = 0.45
MIN_EVENTOS_S2ID = 2
REF_PRECIP_MM = 120.0


def _count_flood_events_in_bairro(db: Session, muni_id: int, bairro: Bairro) -> int:
    if bairro.geom is None:
        return 0
    try:
        rows = (
            db.query(HistoricoDesastreS2ID)
            .filter(
                HistoricoDesastreS2ID.municipio_id == muni_id,
                HistoricoDesastreS2ID.geom.isnot(None),
                func.ST_Intersects(bairro.geom, HistoricoDesastreS2ID.geom),
            )
            .all()
        )
    except Exception:
        return 0
    return sum(1 for e in rows if _is_flood_type(e.tipo_desastre))


def _affected_bairros_from_cache(codigo_ibge: str) -> set[str]:
    if not SIMULATION_CACHE_ENABLED:
        return set()
    try:
        cached = cache_get_json(_rainfall_key(codigo_ibge, REF_PRECIP_MM))
    except Exception:
        return set()
    if not isinstance(cached, dict):
        return set()
    return {str(b) for b in (cached.get("affected_bairros") or []) if b}


def compute_recurring_hotspots(
    db: Session,
    codigo_ibge: str,
    *,
    min_eventos: int = MIN_EVENTOS_S2ID,
    iri_min: float = IRI_HOTSPOT_MIN,
    limit: int = 10,
) -> dict[str, Any]:
    """Bairros com inundação recorrente no S2ID e IRI/simulação elevados."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    floods = AnalyticalEngine.calculate_flood_risk(db, muni.id)
    flood_by_id = {item["id"]: item for item in floods}
    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    sim_bairros = _affected_bairros_from_cache(code)

    items: list[dict[str, Any]] = []
    for b in bairros:
        flood = flood_by_id.get(b.id) or {}
        iri = float(flood.get("indice_risco_inundacao") or 0.0)
        eventos = _count_flood_events_in_bairro(db, muni.id, b)
        na_mancha = b.nome in sim_bairros if b.nome else False

        if eventos < min_eventos:
            continue
        if iri < iri_min and not na_mancha:
            continue

        # Prioridade: eventos × IRI (+ boost se na mancha de simulação em cache)
        prioridade = round(eventos * 10 + iri * 40 + (15 if na_mancha else 0), 1)
        items.append(
            {
                "bairro": b.nome,
                "bairro_id": b.id,
                "eventos_s2id": eventos,
                "iri": round(iri, 3),
                "s2id_historico_score": flood.get("s2id_historico_score"),
                "na_mancha_sim_120mm": na_mancha,
                "prioridade": prioridade,
                "motivo": (
                    f"{eventos} eventos S2ID de inundação"
                    + (f" · IRI {iri:.2f}" if iri >= iri_min else "")
                    + (" · na mancha simulada 120 mm" if na_mancha else "")
                ),
            }
        )

    items.sort(key=lambda x: (-x["prioridade"], -x["eventos_s2id"], x["bairro"] or ""))
    top = items[: max(1, limit)] if items else []

    return {
        "codigo_ibge": code,
        "criterio": {
            "min_eventos_s2id": min_eventos,
            "iri_min": iri_min,
            "ou_na_mancha_sim_mm": REF_PRECIP_MM,
        },
        "total": len(items),
        "hotspots": top,
        "nota": (
            "Hotspot recorrente = histórico S2ID de inundação (≥2 eventos no bairro) "
            "e IRI elevado ou presença na mancha de simulação 120 mm (se em cache)."
        ),
    }
