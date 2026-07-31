"""Testes do geoportal municipal — Fase 16d.5."""

import json

import pytest

from app.services.geoportal_service import parse_upload_to_geojson


SAMPLE_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"nome": "Centro"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-35.0, -8.0], [-35.0, -8.1], [-34.9, -8.1], [-34.9, -8.0], [-35.0, -8.0]]],
            },
        }
    ],
}


def test_parse_geojson_upload():
    raw = json.dumps(SAMPLE_FC).encode("utf-8")
    out = parse_upload_to_geojson(raw, "malha.geojson")
    assert out["type"] == "FeatureCollection"
    assert len(out["features"]) == 1


def test_parse_json_upload():
    raw = json.dumps(SAMPLE_FC).encode("utf-8")
    out = parse_upload_to_geojson(raw, "malha.json")
    assert len(out["features"]) == 1


def test_parse_invalid_format():
    with pytest.raises(ValueError, match="Formato não suportado"):
        parse_upload_to_geojson(b"abc", "malha.txt")


def test_parse_invalid_geojson_type():
    with pytest.raises(ValueError, match="FeatureCollection"):
        parse_upload_to_geojson(json.dumps({"type": "Point"}).encode(), "x.geojson")
