"""Testes de exportação de simulação."""

from types import SimpleNamespace

from app.services.simulation_export import build_simulation_geojson


def test_build_simulation_geojson_merges_layers():
    muni = SimpleNamespace(codigo_ibge="2611606", nome="Recife", uf="PE")
    simulation = {
        "scenario_type": "ExtremeRainfall",
        "input_value": 120.0,
        "geometry": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                    "properties": {"layer_type": "flood_band", "depth_band": "superficial"},
                }
            ],
        },
        "contours": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                    "properties": {"elevation_m": 10.0, "index_contour": True},
                }
            ],
        },
        "flow_paths": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [0.5, 0.5]]},
                    "properties": {},
                }
            ],
        },
        "simulation_meta": {"model_version": "2.3", "dem_resolution_m": 30.0},
    }
    fc = build_simulation_geojson(simulation, muni)
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 3
    assert fc["properties"]["codigo_ibge"] == "2611606"
    assert fc["properties"]["simulation_meta"]["model_version"] == "2.3"
