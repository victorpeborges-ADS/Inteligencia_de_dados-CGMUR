"""Testes de governança/qualidade 3D (17c.5)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.building_quality_service import (
    enrich_feature_properties,
    qualidade_from_fonte,
    resolve_building_seal,
    selo_from_fonte,
)


def test_selo_from_fonte_mapping():
    assert selo_from_fonte("ndsm_lidar") == "LiDAR"
    assert selo_from_fonte("osm_height") == "OSM"
    assert selo_from_fonte("osm_levels") == "OSM"
    assert selo_from_fonte("heuristic") == "Estimado"
    assert selo_from_fonte(None) == "Estimado"


def test_qualidade_from_fonte():
    assert qualidade_from_fonte("ndsm_lidar") == "Observado"
    assert qualidade_from_fonte("osm_height") == "Observado"
    assert qualidade_from_fonte("osm_levels") == "Estimado"
    assert qualidade_from_fonte("heuristic") == "Derivado"


def test_resolve_building_seal_lidar():
    seal = resolve_building_seal("ndsm_lidar")
    assert seal["selo_3d"] == "LiDAR"
    assert seal["qualidade"] == "Observado"
    assert seal["confianca"] == "alta"


def test_enrich_feature_properties():
    props = enrich_feature_properties({
        "id": 1,
        "fonte_altura": "osm_levels",
        "qualidade": "Estimado",
        "altura_m": 12,
    })
    assert props["selo_3d"] == "OSM"
    assert props["selo_label"]
    assert props["qualidade"] == "Estimado"
    assert props["_fill"].startswith("#")


def test_quality_summary_empty_muni():
    from app.services.building_quality_service import quality_summary

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    try:
        quality_summary(db, "9999999")
        assert False, "expected ValueError"
    except ValueError:
        pass
