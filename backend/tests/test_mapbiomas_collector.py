"""Testes do coletor MapBiomas."""

from __future__ import annotations

import pytest

from app.data_connectors.mapbiomas_collector import (
    _build_landcover_partition,
    _classify_xlsx_row,
    _geometry_is_horizontal_band,
    _parse_area,
    build_landcover_series,
    _normalize_class,
)
from shapely.geometry import Polygon


def test_build_landcover_partition_disjoint():
    poly = Polygon([
        (-34.95, -8.12), (-34.88, -8.12), (-34.88, -8.05), (-34.95, -8.05), (-34.95, -8.12),
    ])
    parts = _build_landcover_partition(poly, {
        "Área Urbana": 18000.0,
        "Vegetação / Floresta": 3000.0,
        "Corpo d'água": 800.0,
    })
    assert len(parts) >= 2
    names = list(parts.keys())
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            inter = parts[a].intersection(parts[b])
            assert inter.is_empty or inter.area < poly.area * 0.01


def test_recife_landcover_not_horizontal_bands():
    poly = Polygon([
        (-34.95, -8.12), (-34.88, -8.12), (-34.88, -8.05), (-34.95, -8.05), (-34.95, -8.12),
    ])
    parts = _build_landcover_partition(poly, {
        "Área Urbana": 21840.0,
        "Vegetação / Floresta": 1750.0,
        "Corpo d'água": 900.0,
    }, codigo_ibge="2611606")
    assert len(parts) >= 2
    for geom in parts.values():
        assert not _geometry_is_horizontal_band(geom, poly)
    # Água não pode dominar o município (mancha Voronoi antiga)
    water = parts.get("Corpo d'água")
    if water is not None and not water.is_empty:
        assert water.area / poly.area < 0.12


def test_recife_osm_landcover_loader():
    from app.data_connectors.osm_landcover_collector import GEOJSON_PATH, build_recife_osm_landcover
    from shapely.geometry import box

    if not GEOJSON_PATH.exists():
        pytest.skip("cobertura_recife_osm.geojson ausente")
    poly = box(-34.98, -8.12, -34.88, -8.02)
    parts = build_recife_osm_landcover(poly)
    assert parts is not None
    assert "Área Urbana" in parts
    assert "Corpo d'água" in parts or "Vegetação / Floresta" in parts
    water = parts.get("Corpo d'água")
    if water is not None:
        assert water.area / poly.area < 0.25


def test_recife_habitable_mask_excludes_ucn():
    """UCN Beberibe (Guabiraba) não deve permanecer como área de renda."""
    from app.data_connectors.osm_landcover_collector import (
        UCN_GEOJSON_PATH,
        get_recife_habitable_mask,
        load_recife_ucn_geom,
    )
    from shapely.geometry import box

    if not UCN_GEOJSON_PATH.exists():
        pytest.skip("recife_ucn.geojson ausente")
    ucn = load_recife_ucn_geom()
    assert ucn is not None and not ucn.is_empty
    # envelope municipal aproximado
    poly = box(-35.02, -8.16, -34.85, -7.93)
    hab = get_recife_habitable_mask(poly)
    assert hab is not None and not hab.is_empty
    # habitável não deve cobrir o núcleo da UCN
    overlap = hab.intersection(ucn).area / max(ucn.area, 1e-12)
    assert overlap < 0.05


def test_build_landcover_series_recife_reference(monkeypatch):
    import app.data_connectors.mapbiomas_collector as mc

    monkeypatch.setattr(mc, "csv_index", lambda: {})
    series = build_landcover_series("2611606", area_km2=218.0, populacao=1_600_000)
    urban_2024 = next(r for r in series if r["ano"] == 2024 and r["classe_uso"] == "Área Urbana")
    veg_2024 = next(r for r in series if r["ano"] == 2024 and r["classe_uso"] == "Vegetação / Floresta")
    assert urban_2024["area_ha"] == pytest.approx(21840.0, rel=0.01)
    assert urban_2024["data_quality"] == "referencia_mapbiomas"
    assert veg_2024["area_ha"] == pytest.approx(1750.0, rel=0.01)
    assert veg_2024["data_quality"] == "referencia_mapbiomas"
    assert veg_2024["area_ha"] / (218.0 * 100) * 100 == pytest.approx(8.0, rel=0.05)


def test_build_landcover_series_other_city_derivado(monkeypatch):
    import app.data_connectors.mapbiomas_collector as mc

    monkeypatch.setattr(mc, "csv_index", lambda: {})
    series = build_landcover_series("3550308", area_km2=1521.0, populacao=11_000_000)
    urban = [r for r in series if r["classe_uso"] == "Área Urbana"]
    assert len(urban) == 6
    assert all(r["data_quality"] == "derivado" for r in urban)
    assert urban[-1]["area_ha"] > urban[0]["area_ha"]


def test_build_landcover_series_from_official_csv(monkeypatch, tmp_path):
    import app.data_connectors.mapbiomas_collector as mc

    csv_path = tmp_path / "municipios_cobertura.csv"
    csv_path.write_text(
        "codigo_ibge,ano,classe_uso,area_ha\n"
        "3550308,2024,Área Urbana,90518.606\n"
        "3550308,2024,Vegetação / Floresta,41061.595\n"
        "3550308,2024,Corpo d'água,6822.377\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MAPBIOMAS_STATS_DIR", str(tmp_path))
    monkeypatch.setattr(mc, "_bundled_pilot_csv", lambda: None)
    mc._CSV_INDEX = None
    series = build_landcover_series("3550308", area_km2=1521.0, populacao=11_000_000)
    urban = next(r for r in series if r["ano"] == 2024 and r["classe_uso"] == "Área Urbana")
    water = next(r for r in series if r["ano"] == 2024 and r["classe_uso"] == "Corpo d'água")
    assert urban["data_quality"] == "oficial"
    assert urban["area_ha"] == pytest.approx(90518.606)
    assert water["data_quality"] == "oficial"
    assert water["area_ha"] == pytest.approx(6822.377)
    mc._CSV_INDEX = None


def test_normalize_class_labels():
    assert _normalize_class("Area Urbanizada") == "Área Urbana"
    assert _normalize_class("Floresta") == "Vegetação / Floresta"
    assert _normalize_class("Corpos d agua") == "Corpo d'água"


def test_classify_xlsx_row_mapbiomas_col10():
    assert _classify_xlsx_row("4. Non vegetated area", "4.2. Urban Area") == "Área Urbana"
    assert _classify_xlsx_row("1. Forest", "1.1. Forest Formation") == "Vegetação / Floresta"
    assert _classify_xlsx_row("5. Water and Marine Environment", "5.1. River, Lake and Ocean") == "Corpo d'água"
    assert _classify_xlsx_row("3. Farming", "3.1. Pasture") is None


def test_parse_area_float_from_xlsx():
    assert _parse_area(2858.596846) == pytest.approx(2858.596846)
    assert _parse_area("1.234,56") == pytest.approx(1234.56)
    assert _parse_area("2858.59") == pytest.approx(2858.59)
