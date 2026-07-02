"""Testes da malha oficial IBGE (bairros + setores censitários)."""

from app.data_connectors.official_bairros_collector import (
    _dissolve_setores_to_bairros,
    _prop,
    _uf_for_municipio,
)


def test_uf_lookup():
    assert _uf_for_municipio("2611606") == "PE"
    assert _uf_for_municipio("3550308") == "SP"


def test_prop_reads_ibge_fields():
    props = {"NM_BAIRRO": "Centro", "CD_BAIRRO": "2611606001001"}
    assert _prop(props, ("NM_BAIRRO",)) == "Centro"
    assert _prop(props, ("CD_BAIRRO",)) == "2611606001001"


def test_dissolve_setores_groups_by_bairro_name():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NM_BAIRRO": "Centro", "CD_SETOR": "140002705000001"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-40.0, -8.0], [-39.9, -8.0], [-39.9, -7.9], [-40.0, -7.9], [-40.0, -8.0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"NM_BAIRRO": "Centro", "CD_SETOR": "140002705000002"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-39.9, -8.0], [-39.8, -8.0], [-39.8, -7.9], [-39.9, -7.9], [-39.9, -8.0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"NM_DIST": "Zona Rural", "CD_SETOR": "140002705000003"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-40.1, -8.1], [-40.0, -8.1], [-40.0, -8.0], [-40.1, -8.0], [-40.1, -8.1]]],
                },
            },
        ],
    }
    out = _dissolve_setores_to_bairros(fc)
    names = {f["properties"]["NM_BAIRRO"] for f in out["features"]}
    assert "Centro" in names
    assert "Zona Rural" in names
    assert len(out["features"]) == 2
