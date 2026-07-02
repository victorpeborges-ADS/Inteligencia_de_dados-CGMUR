"""Testes do pipeline CTM municipal."""

from shapely.geometry import mapping, box

from app.data_connectors.ctm_collector import dissolve_by_name, _prop
from app.data_connectors.ctm_registry import CTM_BY_CODE, CTM_TARGET_CODES


def test_dissolve_by_name_merges_duplicates():
    poly = box(-48.0, -16.0, -47.9, -15.9)
    fc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"nm_bai": "Centro"}, "geometry": mapping(poly)},
            {"type": "Feature", "properties": {"nm_bai": "Centro"}, "geometry": mapping(box(-48.05, -16.05, -47.95, -15.95))},
            {"type": "Feature", "properties": {"nm_bai": "Setor Sul"}, "geometry": mapping(box(-48.1, -16.1, -48.0, -16.0))},
        ],
    }
    out = dissolve_by_name(fc, ("nm_bai",))
    assert len(out["features"]) == 2
    names = {f["properties"]["nome"] for f in out["features"]}
    assert names == {"Centro", "Setor Sul"}


def test_prop_fallback():
    assert _prop({"nome": " X "}, ("nome",)) == "X"
    assert _prop({}, ("nome",)) is None


def test_registry_covers_priority_cities():
    assert "5208707" in CTM_BY_CODE  # Goiânia
    assert "5300108" in CTM_BY_CODE  # Brasília
    assert len(CTM_TARGET_CODES) == 24
    assert "3509502" in CTM_TARGET_CODES  # Campinas — pendente CTM poligonal
