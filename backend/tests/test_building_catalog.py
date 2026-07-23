"""Testes do catálogo do gêmeo digital 3D (17c.3)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.building_catalog_service import (
    catalog_meta_gemeo_digital,
    catalog_status_gemeo_digital,
    maturity_3d_pct,
)
from app.services.catalog_coverage import BASE_CATALOG
from app.services.catalog_source_registry import FONTE_REGISTRY, RADAR_AXES
from app.services.data_catalog_engine import resolve_catalog_status


def test_gemeo_in_base_catalog_and_registry():
    ids = {b["id"] for b in BASE_CATALOG}
    assert "gemeo_digital_3d" in ids
    assert "gemeo_digital_3d" in FONTE_REGISTRY
    assert "gemeo_digital_3d" in RADAR_AXES["Geoespacial"]


def test_maturity_3d_pct_ranges():
    assert maturity_3d_pct(0, {}, tiles=False, city=False) == 0
    low = maturity_3d_pct(100, {"heuristic": 100}, tiles=False, city=False)
    mid = maturity_3d_pct(100, {"heuristic": 70, "osm_levels": 30}, tiles=True, city=False)
    high = maturity_3d_pct(100, {"ndsm_lidar": 80, "heuristic": 20}, tiles=True, city=True)
    assert 0 < low < mid < high <= 100


def test_status_ausente_sem_municipio():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert catalog_status_gemeo_digital(db, "9999999", muni=None) == "Ausente"


def test_status_estimado_com_footprints():
    muni = MagicMock()
    muni.id = 1
    db = MagicMock()

    def _query(model):
        q = MagicMock()
        # count de edificações
        q.filter.return_value.count.return_value = 80
        # breakdown fonte_altura
        q.filter.return_value.all.return_value = [("heuristic",)] * 80
        return q

    db.query.side_effect = _query

    with patch("app.services.building_catalog_service.status_3dtiles", return_value={"disponivel": False}):
        with patch("app.services.building_catalog_service.status_citymodel", return_value={"disponivel": False}):
            assert catalog_status_gemeo_digital(db, "2611606", muni=muni) == "Estimado"


def test_status_integrado_com_altura_e_export():
    muni = MagicMock()
    muni.id = 1
    db = MagicMock()

    def _query(model):
        q = MagicMock()
        q.filter.return_value.count.return_value = 100
        q.filter.return_value.all.return_value = [("ndsm_lidar",)] * 40 + [("heuristic",)] * 60
        return q

    db.query.side_effect = _query

    with patch("app.services.building_catalog_service.status_3dtiles", return_value={"disponivel": True}):
        with patch("app.services.building_catalog_service.status_citymodel", return_value={"disponivel": False}):
            assert catalog_status_gemeo_digital(db, "2611606", muni=muni) == "Integrado"


def test_resolve_catalog_status_wires_gemeo():
    muni = MagicMock()
    muni.id = 7
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with patch(
        "app.services.data_catalog_engine.catalog_status_gemeo_digital",
        return_value="Estimado",
    ) as mocked:
        out = resolve_catalog_status(db, "2611606", "gemeo_digital_3d", muni=muni, seed=None)
        assert out == "Estimado"
        mocked.assert_called_once()


def test_catalog_meta_includes_export_urls():
    muni = MagicMock()
    muni.id = 1
    db = MagicMock()
    q = db.query.return_value.filter.return_value
    q.count.return_value = 10
    q.all.return_value = [("osm_levels",)] * 10
    q.order_by.return_value.first.return_value = (None,)
    db.query.return_value.filter.return_value.first.return_value = muni

    with patch(
        "app.services.building_catalog_service.status_3dtiles",
        return_value={"disponivel": True, "tileset_url": "/static/3dtiles/2611606/tileset.json"},
    ):
        with patch(
            "app.services.building_catalog_service.status_citymodel",
            return_value={
                "disponivel": True,
                "cityjson_url": "/static/citymodels/2611606/model.city.json",
                "citygml_url": "/static/citymodels/2611606/model.gml",
            },
        ):
            # force muni path without re-query confusion
            meta = catalog_meta_gemeo_digital(db, "2611606", muni=muni)
            assert meta["registros"] == 10
            assert meta["lod"] == "LOD1"
            assert meta["tiles_3d"]["tileset_url"].endswith("tileset.json")
            assert meta["citymodel"]["cityjson_url"].endswith("model.city.json")
            assert meta["maturidade_3d_pct"] > 0
