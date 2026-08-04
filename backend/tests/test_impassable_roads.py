"""Cruzamento vias × mancha de alagamento."""

from __future__ import annotations

from shapely.geometry import LineString, mapping, box

from app.services.impassable_roads_service import (
    _flood_union_from_features,
    _length_km,
    build_impassable_roads_geojson,
)


def test_flood_union_picks_moderada_and_critica():
    flood = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(box(0, 0, 1, 1)),
                "properties": {"layer_type": "flood_band", "depth_band": "superficial"},
            },
            {
                "type": "Feature",
                "geometry": mapping(box(0.4, 0.4, 0.6, 0.6)),
                "properties": {"layer_type": "flood_band", "depth_band": "critica"},
            },
        ],
    }
    u = _flood_union_from_features(flood)
    assert u is not None and not u.is_empty
    # só a mancha crítica (não a superficial)
    assert u.bounds[0] >= 0.39


def test_length_km_positive():
    # ~1 km east-west near equator
    line = LineString([(0.0, 0.0), (0.009, 0.0)])
    km = _length_km(line)
    assert 0.8 < km < 1.2


def test_build_impassable_empty_without_flood():
    class _Muni:
        id = 1
        codigo_ibge = "0000000"
        geom = None

    # Sem DB real — flood vazio
    fc, meta = build_impassable_roads_geojson(
        db=None,  # type: ignore[arg-type]
        muni=_Muni(),  # type: ignore[arg-type]
        flood_fc={"type": "FeatureCollection", "features": []},
        allow_overpass=False,
    )
    assert fc["features"] == []
    assert meta["ok"] is False
