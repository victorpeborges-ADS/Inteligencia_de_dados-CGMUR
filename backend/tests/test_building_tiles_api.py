"""Testes da API de tiles do gêmeo (17c.4)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.data_connectors.cache import cache_get_bytes, cache_set_bytes
from app.services.building_tiles_api_service import (
    get_cached_buildings_geojson,
    get_cached_tileset_json,
    invalidate_gemeo_tile_cache,
    mvt_cache_key,
    tile_api_status,
)


def test_cache_bytes_roundtrip():
    key = "gemeo:test:bytes:1"
    cache_set_bytes(key, b"\x1a\x2b\x3c", ttl=60)
    assert cache_get_bytes(key) == b"\x1a\x2b\x3c"


def test_mvt_cache_key():
    assert mvt_cache_key("2611606", 14, 1, 2) == "gemeo:mvt:2611606:14:1:2"


def test_get_cached_geojson_miss_then_hit():
    db = MagicMock()
    fc = {"type": "FeatureCollection", "features": [{"type": "Feature"}]}
    with patch(
        "app.data_connectors.building_footprints_collector.buildings_geojson",
        return_value=fc,
    ):
        invalidate_gemeo_tile_cache("2611606")
        first = get_cached_buildings_geojson(db, "2611606", limit=10, ensure=False, use_cache=True)
        assert first["_cache"] == "miss"
        second = get_cached_buildings_geojson(db, "2611606", limit=10, ensure=False, use_cache=True)
        assert second["_cache"] == "hit"
        assert second["type"] == "FeatureCollection"


def test_get_cached_tileset_json(tmp_path, monkeypatch):
    code = "2611606"
    muni_dir = tmp_path / code
    muni_dir.mkdir()
    tileset = {
        "asset": {"version": "1.0"},
        "root": {
            "content": {"uri": "content.glb"},
            "boundingVolume": {"region": [0, 0, 1, 1, 0, 10]},
        },
    }
    (muni_dir / "tileset.json").write_text(json.dumps(tileset), encoding="utf-8")

    monkeypatch.setattr(
        "app.services.building_tiles_api_service.tiles3d_muni_dir",
        lambda _c: muni_dir,
    )
    invalidate_gemeo_tile_cache(code)
    db = MagicMock()
    doc = get_cached_tileset_json(db, code, ensure_build=False, use_cache=True)
    assert doc["_cache"] == "miss"
    assert "root" in doc
    doc2 = get_cached_tileset_json(db, code, ensure_build=False, use_cache=True)
    assert doc2["_cache"] == "hit"


def test_tile_api_status_shape():
    db = MagicMock()
    muni = MagicMock()
    muni.id = 1
    db.query.return_value.filter.return_value.first.return_value = muni
    db.query.return_value.filter.return_value.count.return_value = 42
    with patch(
        "app.services.building_tiles_api_service.status_3dtiles",
        return_value={"disponivel": False},
    ):
        st = tile_api_status(db, "2611606")
    assert st["mvt"]["layer"] == "edificacoes"
    assert "{z}" in st["mvt"]["template"]
    assert st["tiles_3d"]["tileset_api_url"].endswith("tileset.json")
