"""Testes do coletor MapBiomas."""

from __future__ import annotations

import pytest

from app.data_connectors.mapbiomas_collector import build_landcover_series, _normalize_class


def test_build_landcover_series_recife_reference():
    series = build_landcover_series("2611606", area_km2=218.0, populacao=1_600_000)
    urban_2024 = next(r for r in series if r["ano"] == 2024 and r["classe_uso"] == "Área Urbana")
    assert urban_2024["area_ha"] == pytest.approx(21840.0, rel=0.01)
    assert urban_2024["data_quality"] == "referencia_mapbiomas"


def test_build_landcover_series_other_city_derivado():
    series = build_landcover_series("3550308", area_km2=1521.0, populacao=11_000_000)
    urban = [r for r in series if r["classe_uso"] == "Área Urbana"]
    assert len(urban) == 6
    assert all(r["data_quality"] == "derivado" for r in urban)
    assert urban[-1]["area_ha"] > urban[0]["area_ha"]


def test_normalize_class_labels():
    assert _normalize_class("Area Urbanizada") == "Área Urbana"
    assert _normalize_class("Floresta") == "Vegetação / Floresta"
    assert _normalize_class("Corpos d agua") == "Corpo d'água"
