"""Testes do registry de tiles raster externos (mosaicjson)."""

from app.services.external_raster_service import (
    EXTERNAL_RASTER_SOURCES,
    build_mosaicjson_tile_url,
    get_external_raster_config,
    list_external_rasters,
    probe_external_raster_server,
)


def test_registry_contains_lst():
    assert "lst_observada" in EXTERNAL_RASTER_SOURCES


def test_list_external_rasters_active_only():
    rows = list_external_rasters()
    assert len(rows) >= 1
    assert rows[0]["layer_id"] == "lst_observada"
    assert rows[0]["provider"] == "georedus_mosaicjson"


def test_build_mosaicjson_tile_url_placeholders():
    source = EXTERNAL_RASTER_SOURCES["lst_observada"]
    url = build_mosaicjson_tile_url(source, rescale_min=20, rescale_max=60)
    assert "{z}/{x}/{y}" in url
    assert "mosaicjson/tiles/WebMercatorQuad" in url
    assert "colormap_name=turbo" in url


def test_get_external_raster_config_defaults():
    cfg = get_external_raster_config("lst_observada")
    assert cfg["layer_id"] == "lst_observada"
    assert cfg["rescale_min"] == 20
    assert cfg["rescale_max"] == 60
    assert "{z}" in cfg["tile_url_template"]
    assert cfg["provider"] == "georedus_mosaicjson"


def test_get_external_raster_config_unknown():
    cfg = get_external_raster_config("raster_inexistente")
    assert "error" in cfg


def test_get_external_raster_config_clamps_invalid_range():
    cfg = get_external_raster_config("lst_observada", rescale_min=55, rescale_max=30)
    assert cfg["rescale_min"] == 20
    assert cfg["rescale_max"] == 60


def test_probe_external_raster_server_unknown():
    out = probe_external_raster_server("foo")
    assert out["ok"] is False
