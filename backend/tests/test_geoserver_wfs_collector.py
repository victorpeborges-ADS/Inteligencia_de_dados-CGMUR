"""Testes do coletor GeoServer WFS municipal."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.data_connectors.ctm_collector import fetch_ctm_geojson, fetch_geoserver_wfs_geojson
from app.data_connectors.ctm_registry import CTM_BY_CODE, CTM_SOURCES

ARACAJU_WFS = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"id": 1, "bairro": "Centro", "area": 1000},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-37.05, -10.92], [-37.05, -10.93], [-37.04, -10.93], [-37.04, -10.92], [-37.05, -10.92]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"id": 2, "bairro": "Atalaia", "area": 2000},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-37.06, -10.94], [-37.06, -10.95], [-37.05, -10.95], [-37.05, -10.94], [-37.06, -10.94]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"id": 3, "bairro": "Salgado", "area": 1500},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-37.07, -10.96], [-37.07, -10.97], [-37.06, -10.97], [-37.06, -10.96], [-37.07, -10.96]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"id": 4, "bairro": "Grageru", "area": 1800},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-37.08, -10.98], [-37.08, -10.99], [-37.07, -10.99], [-37.07, -10.98], [-37.08, -10.98]]],
            },
        },
    ],
}


def test_aracaju_registered_in_ctm_registry():
    source = CTM_BY_CODE.get("2800308")
    assert source is not None
    assert source.kind == "geoserver_wfs"
    assert source.where == "Limites_Municipais:bairros_2023"
    assert "aracaju" in source.url.lower()


@patch("app.data_connectors.ctm_collector.requests.get")
def test_fetch_geoserver_wfs_geojson_builds_params(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = ARACAJU_WFS
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    source = CTM_BY_CODE["2800308"]
    out = fetch_geoserver_wfs_geojson(source)
    assert out["type"] == "FeatureCollection"
    assert len(out["features"]) == 4

    mock_get.assert_called_once()
    url, kwargs = mock_get.call_args
    params = kwargs["params"]
    assert params["service"] == "WFS"
    assert params["typeName"] == "Limites_Municipais:bairros_2023"
    assert params["outputFormat"] == "application/json"
    assert params["srsName"] == "EPSG:4326"
    assert str(url[0]).endswith("/geoserver/wfs")


@patch("app.data_connectors.ctm_collector.fetch_geoserver_wfs_geojson")
def test_fetch_ctm_geojson_dissolves_geoserver_bairros(mock_fetch):
    mock_fetch.return_value = ARACAJU_WFS
    source = CTM_BY_CODE["2800308"]
    out = fetch_ctm_geojson(source)
    names = {f["properties"]["nome"] for f in out["features"]}
    assert names == {"Centro", "Atalaia", "Salgado", "Grageru"}


def test_fetch_geoserver_wfs_requires_type_name():
    source = CTM_SOURCES[-1]
    bad = type(source)(
        codigo_ibge=source.codigo_ibge,
        nome=source.nome,
        uf=source.uf,
        kind=source.kind,
        url=source.url,
        name_fields=source.name_fields,
        where="1=1",
        nota=source.nota,
    )
    with pytest.raises(ValueError, match="typeName"):
        fetch_geoserver_wfs_geojson(bad)
