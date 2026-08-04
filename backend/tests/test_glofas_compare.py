"""Comparativo GloFAS — helpers de união."""

from __future__ import annotations

from shapely.geometry import mapping, box

from app.services.glofas_compare_service import _area_km2, _union_flood_bands


def test_union_flood_bands():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(box(0, 0, 1, 1)),
                "properties": {"layer_type": "flood_band", "depth_band": "moderada"},
            },
            {
                "type": "Feature",
                "geometry": mapping(box(0.5, 0.5, 1.5, 1.5)),
                "properties": {"layer_type": "flood_band", "depth_band": "critica"},
            },
        ],
    }
    u = _union_flood_bands(fc)
    assert u is not None and not u.is_empty
    assert _area_km2(u, 0.0) > 0
