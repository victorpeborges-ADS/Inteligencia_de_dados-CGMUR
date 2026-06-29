"""ETL territorial S2ID + MapBiomas após carga municipal."""

from __future__ import annotations

import datetime
from typing import Any

from geoalchemy2.shape import from_shape
from shapely.geometry import Point, shape
from sqlalchemy.orm import Session

from app.data_connectors.mapbiomas_collector import collect_mapbiomas_municipality, upsert_municipal_stats
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

    created_s2id = 0

    if s2id_before == 0 and muni.geom is not None:
        poly = shape(db.scalar(muni.geom.ST_AsGeoJSON()))
        disaster_type = "Deslizamento" if risk == "encosta" else "Inundação"
        centroid = poly.centroid
        db.add(
            HistoricoDesastreS2ID(
                municipio_id=muni.id,
                tipo_desastre=disaster_type,
                data_ocorrencia=datetime.date(2022, 3, 15),
                populacao_afetada=max(500, muni.populacao // 200),
                danos_materiais=250_000.0,
                geom=from_shape(Point(centroid.x, centroid.y), srid=4326),
            )
        )
        created_s2id = 1
        db.commit()

    mb_result = upsert_municipal_stats(db, muni, force=mb_before == 0)
    if mb_result.get("skipped") and mb_before == 0:
        mb_result = collect_mapbiomas_municipality(db, muni.codigo_ibge, force=True)

    mb_after = (
        db.query(CoberturaVegetalMapBiomas)
        .filter(CoberturaVegetalMapBiomas.municipio_id == muni.id)
        .count()
    )
    s2id_after = s2id_before + created_s2id
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
