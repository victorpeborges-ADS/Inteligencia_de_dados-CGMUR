"""Ativos críticos × mancha."""

from __future__ import annotations

from shapely.geometry import mapping, box

from app.services.critical_assets_flood_service import _band_for_point
from app.services.impassable_roads_service import _flood_union_from_features


def test_band_for_point_picks_worst():
    flood = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(box(0, 0, 2, 2)),
                "properties": {
                    "layer_type": "flood_band",
                    "depth_band": "moderada",
                    "depth_max_m": 0.5,
                },
            },
            {
                "type": "Feature",
                "geometry": mapping(box(0.5, 0.5, 1.5, 1.5)),
                "properties": {
                    "layer_type": "flood_band",
                    "depth_band": "critica",
                    "depth_max_m": 1.2,
                },
            },
        ],
    }
    band, depth = _band_for_point(1.0, 1.0, flood)
    assert band == "critica"
    assert depth == 1.2


def test_flood_union_empty():
    assert _flood_union_from_features({"type": "FeatureCollection", "features": []}) is None
