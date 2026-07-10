"""Testes do serviço LST observada (GeoReDUS / TiTiler)."""

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
