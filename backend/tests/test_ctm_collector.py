"""Testes do pipeline CTM municipal."""

from unittest.mock import MagicMock, patch

from shapely.geometry import mapping, box

from app.data_connectors.ctm_collector import (
    collect_ctm_municipality,
    dissolve_by_name,
    fetch_ibge_setores_individuais_geojson,
    _prop,
)
from app.data_connectors.ctm_registry import CTM_BY_CODE, CTM_TARGET_CODES, CtmSource


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
    assert "3509502" in CTM_BY_CODE  # Campinas — UTB cache DIDT
    assert "2602902" in CTM_BY_CODE  # Cabo — IBGE WFS
    assert "2806701" in CTM_BY_CODE  # São Cristóvão — IBGE WFS
    assert "1721000" in CTM_BY_CODE  # Palmas — setores individuais
    assert len(CTM_TARGET_CODES) == 24
    assert all(code in CTM_BY_CODE for code in CTM_TARGET_CODES)


def test_fetch_ibge_setores_individuais_geojson(monkeypatch):
    source = CtmSource(
        codigo_ibge="1721000",
        nome="Palmas",
        uf="TO",
        kind="ibge_setores_individuais",
        url="ibge://setores/2022",
        name_fields=("NM_BAIRRO", "NM_DIST", "nome"),
        code_fields=("CD_SETOR",),
    )
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"CD_SETOR": "172100005000001", "NM_MUN": "Palmas", "NM_DIST": "Palmas"},
                "geometry": mapping(box(-48.0, -10.2, -47.9, -10.1)),
            },
            {
                "type": "Feature",
                "properties": {"CD_SETOR": "172100005000002", "NM_BAIRRO": "Taquaruçu", "NM_MUN": "Palmas"},
                "geometry": mapping(box(-48.1, -10.3, -48.0, -10.2)),
            },
        ],
    }
    monkeypatch.setattr(
        "app.data_connectors.official_bairros_collector.fetch_ibge_setores_geojson",
        lambda *_a, **_k: fc,
    )
    out = fetch_ibge_setores_individuais_geojson(source)
    assert len(out["features"]) == 2
    names = {f["properties"]["NM_BAIRRO"] for f in out["features"]}
    assert "Taquaruçu" in names
    assert any(n.startswith("Setor ") for n in names)


@patch("app.data_connectors.ctm_collector.fetch_ibge_setores_individuais_geojson")
@patch("app.data_connectors.ctm_collector.fetch_ctm_geojson")
@patch("app.data_connectors.ctm_collector.import_ctm_mesh")
def test_collect_ctm_fallback_setores_when_primary_fails(mock_import, mock_fetch, mock_fallback):
    source = CTM_BY_CODE["2924009"]
    db = MagicMock()
    muni = MagicMock()
    muni.id = 3
    muni.codigo_ibge = "2924009"
    db.query.return_value.filter.return_value.first.return_value = muni
    db.query.return_value.filter.return_value.count.return_value = 1
    mock_fetch.side_effect = RuntimeError("CONDER offline")
    mock_fallback.return_value = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {"nome": "S1"}, "geometry": mapping(box(0, 0, 1, 1))}] * 5,
    }
    mock_import.return_value = {"codigo_ibge": "2924009", "skipped": False, "bairros": 5}

    out = collect_ctm_municipality(db, "2924009", force=False)
    assert out["skipped"] is False
    mock_fallback.assert_called_once()
    assert "fallback setores IBGE" in out["fonte_registry"]
