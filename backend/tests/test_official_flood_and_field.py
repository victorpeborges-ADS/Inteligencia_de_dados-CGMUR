"""Testes 20h.5 / 21c.4 — mancha oficial + registro em campo."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.official_flood_map_service import (
    evaluate_against_official_polygons,
    load_official_flood_geojson,
)


def test_load_official_flood_recife_fixture():
    geo = load_official_flood_geojson("2611606")
    assert geo is not None
    assert geo["type"] == "FeatureCollection"
    assert len(geo["features"]) >= 1


def test_iou_identical_polygons():
    poly = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-34.88, -8.05], [-34.87, -8.05],
                    [-34.87, -8.04], [-34.88, -8.04], [-34.88, -8.05],
                ]],
            },
            "properties": {},
        }],
    }
    result = evaluate_against_official_polygons(poly, poly)
    assert result["disponivel"] is True
    assert result["iou"] == 1.0
    assert result["coverage_sim_in_official"] == 1.0


def test_create_field_event_point():
    from app.services.evento_alagamento_service import create_field_event

    db = MagicMock()
    muni = SimpleNamespace(id=1, codigo_ibge="2611606")
    db.query.return_value.filter.return_value.first.return_value = muni

    added = []

    def _add(obj):
        obj.id = 99
        added.append(obj)

    db.add.side_effect = _add
    db.refresh.side_effect = lambda obj: None

    out = create_field_event(
        db,
        codigo_ibge="2611606",
        tipo="Alagamento Urbano",
        inicio_em=dt.datetime(2024, 5, 28, 10, 0),
        severidade="alta",
        fenomeno="pluvial",
        lat=-8.05,
        lng=-34.88,
        referencia="teste",
    )
    assert out["id"] == 99
    assert out["fonte"] == "defesa_civil"
    assert out["fenomeno"] == "pluvial"
    assert added[0].data_quality == "oficial"
