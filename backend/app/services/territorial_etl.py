"""ETL territorial S2ID + MapBiomas após carga municipal."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.data_connectors.mapbiomas_collector import collect_mapbiomas_municipality, upsert_municipal_stats
from app.data_connectors.s2id_collector import collect_s2id_municipality, needs_s2id_refresh
from app.models import CoberturaVegetalMapBiomas, HistoricoDesastreS2ID, Municipio


def ensure_s2id_mapbiomas_layers(db: Session, muni: Municipio, risk: str = "inundacao") -> dict[str, Any]:
    """
    Garante registros S2ID mínimos e camadas MapBiomas (estatísticas + polígonos).
    """
    s2id_before = (
        db.query(HistoricoDesastreS2ID)
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .count()
    )
    mb_before = (
        db.query(CoberturaVegetalMapBiomas)
        .filter(CoberturaVegetalMapBiomas.municipio_id == muni.id)
        .count()
    )

    s2id_result = collect_s2id_municipality(
        db, muni.codigo_ibge, force=needs_s2id_refresh(db, muni), risk=risk
    )
    created_s2id = 0 if s2id_result.get("skipped") else s2id_result.get("records", 0)

    mb_result = upsert_municipal_stats(db, muni, force=mb_before == 0)
    if mb_result.get("skipped") and mb_before == 0:
        mb_result = collect_mapbiomas_municipality(db, muni.codigo_ibge, force=True)

    mb_after = (
        db.query(CoberturaVegetalMapBiomas)
        .filter(CoberturaVegetalMapBiomas.municipio_id == muni.id)
        .count()
    )
    s2id_after = (
        db.query(HistoricoDesastreS2ID)
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .count()
    )
    created_mb = mb_result.get("polygons", 0) if not mb_result.get("skipped") else max(0, mb_after - mb_before)

    return {
        "s2id_count": s2id_after,
        "mapbiomas_count": mb_after,
        "created_s2id": created_s2id,
        "created_mapbiomas": created_mb,
        "mapbiomas_quality": mb_result.get("data_quality", "derivado"),
        "mapbiomas_records": mb_result.get("records", 0),
        "ok": s2id_after > 0 and mb_after > 0,
    }
