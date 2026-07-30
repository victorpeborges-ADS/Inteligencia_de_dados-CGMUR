"""Testes do serviço LST observada (GeoReDUS / TiTiler)."""

from unittest.mock import patch

from app.services.georedus_lst_service import (
    LST_DEFAULT_MAX_C,
    LST_DEFAULT_MIN_C,
    LST_MAX_ZOOM,
    LST_MIN_ZOOM,
    build_lst_tile_url,
    get_lst_observada_config,
)


def test_build_lst_tile_url_contains_leaflet_placeholders():
    url = build_lst_tile_url(20, 60)
    assert "{z}/{x}/{y}" in url
    assert "rescale=20%2C60" in url or "rescale=20,60" in url
    assert "colormap_name=turbo" in url
    assert "mosaicjson/tiles/WebMercatorQuad" in url


def test_get_lst_observada_config_defaults():
    cfg = get_lst_observada_config()
    assert cfg["layer_id"] == "lst_observada"
    assert cfg["quality"] == "Observado"
    assert cfg["rescale_min_c"] == LST_DEFAULT_MIN_C
    assert cfg["rescale_max_c"] == LST_DEFAULT_MAX_C
    assert cfg["min_zoom"] == LST_MIN_ZOOM
    assert cfg["max_zoom"] == LST_MAX_ZOOM
    assert "{z}" in cfg["tile_url_template"]


def test_get_lst_observada_config_clamps_invalid_range():
    cfg = get_lst_observada_config(rescale_min=55, rescale_max=30)
    assert cfg["rescale_min_c"] == LST_DEFAULT_MIN_C
    assert cfg["rescale_max_c"] == LST_DEFAULT_MAX_C


def test_get_lst_observada_config_custom_rescale():
    cfg = get_lst_observada_config(rescale_min=25, rescale_max=50)
    assert cfg["rescale_min_c"] == 25
    assert cfg["rescale_max_c"] == 50
    assert "rescale=25" in cfg["tile_url_template"]


def test_parse_lst_point_payload_round():
    from app.services.georedus_lst_service import _parse_lst_point_payload

    assert _parse_lst_point_payload({"values": [["b1", [41.26]]]}) == 41.3
    assert _parse_lst_point_payload({"values": []}) is None


@patch("app.api.map.fetch_lst_point", return_value=43.7)
def test_external_raster_point_handler(mock_fetch):
    from unittest.mock import MagicMock

    from app.api.map import external_raster_point

    body = external_raster_point(
        "lst_observada",
        request=MagicMock(),
        lon=-34.8811,
        lat=-8.0539,
        codigo_ibge=None,
        db=MagicMock(),
    )
    assert body["temperatura_c"] == 43.7
    assert body["disponivel"] is True
    assert body["unit"] == "°C"
    assert "GeoReDUS" in body["fonte"]
    mock_fetch.assert_called_once_with(-34.8811, -8.0539)
