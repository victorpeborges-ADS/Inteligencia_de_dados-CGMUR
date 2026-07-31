"""Testes de exportação de simulação."""

import zipfile
from types import SimpleNamespace

from app.services.simulation_export import (
    build_simulation_geojson,
    build_simulation_kml,
    save_simulation_kmz,
)


def _sample_simulation() -> dict:
    return {
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


def test_build_simulation_geojson_merges_layers():
    muni = SimpleNamespace(codigo_ibge="2611606", nome="Recife", uf="PE")
    fc = build_simulation_geojson(_sample_simulation(), muni)
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 3
    assert fc["properties"]["codigo_ibge"] == "2611606"
    assert fc["properties"]["simulation_meta"]["model_version"] == "2.3"


def test_build_simulation_kml_has_placemarks():
    muni = SimpleNamespace(codigo_ibge="2611606", nome="Recife", uf="PE")
    kml = build_simulation_kml(_sample_simulation(), muni)
    assert kml.startswith("<?xml")
    assert "<kml" in kml
    assert "<Placemark>" in kml
    assert "<Folder>" in kml
    assert "<name>mancha</name>" in kml or "<name>escoamento</name>" in kml
    assert "<Polygon>" in kml
    assert "<LineString>" in kml
    assert "2611606" in kml


def test_kmz_package_includes_contingency_points():
    muni = SimpleNamespace(codigo_ibge="2611606", nome="Recife", uf="PE")
    extra = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-34.88, -8.05]},
            "properties": {
                "layer_type": "ponto_contingencia",
                "folder": "pontos_contingencia",
                "nome": "Abrigo Central",
            },
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-34.9, -8.1], [-34.8, -8.1], [-34.8, -8.0], [-34.9, -8.1]]],
            },
            "properties": {
                "layer_type": "bairro_afetado",
                "folder": "bairros_afetados",
                "nome": "Boa Viagem",
            },
        },
    ]
    fc = build_simulation_geojson(_sample_simulation(), muni, extra_features=extra)
    assert fc["properties"]["package"] == "20e2_kmz_completo"
    assert len(fc["features"]) == 5
    kml = build_simulation_kml(_sample_simulation(), muni, extra_features=extra)
    assert "pontos_contingencia" in kml
    assert "bairros_afetados" in kml
    assert "Abrigo Central" in kml
    assert "<Point>" in kml


def test_save_simulation_kmz_is_zip_with_doc_kml(tmp_path, monkeypatch):
    muni = SimpleNamespace(codigo_ibge="2611606", nome="Recife", uf="PE")
    monkeypatch.setattr(
        "app.services.simulation_export.simulation_export_dir",
        lambda: tmp_path,
    )
    path = save_simulation_kmz(_sample_simulation(), muni)
    assert path.exists()
    assert path.suffix == ".kmz"
    assert path.stat().st_size > 0
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        assert "doc.kml" in names
        content = zf.read("doc.kml").decode("utf-8")
        assert "<Placemark>" in content
        assert "Recife" in content
