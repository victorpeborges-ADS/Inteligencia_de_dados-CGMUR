"""Testes 17a.1–17a.2 — footprints e altura LOD1."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from shapely.geometry import box

from app.data_connectors.building_footprints_collector import (
    _seed_recife_centro,
    buildings_geojson,
    elements_to_records,
    estimate_height,
    parse_height_meters,
    upsert_edificacoes,
)


def test_parse_height_meters():
    assert parse_height_meters("12") == 12.0
    assert parse_height_meters("12.5 m") == 12.5
    assert parse_height_meters("15m") == 15.0
    assert parse_height_meters(None) is None
    assert parse_height_meters("abc") is None


def test_estimate_height_priority():
    h, fonte, q, pav = estimate_height({"height": "24", "building:levels": "3"})
    assert h == 24.0
    assert fonte == "osm_height"
    assert q == "Observado"

    h2, fonte2, q2, pav2 = estimate_height({"building:levels": "4"})
    assert h2 == 12.0
    assert fonte2 == "osm_levels"
    assert q2 == "Estimado"
    assert pav2 == 4

    h3, fonte3, q3, _ = estimate_height({"building": "office"})
    assert h3 == 24.0
    assert fonte3 == "heuristic"
    assert q3 == "Derivado"


def test_elements_to_records():
    elements = [
        {
            "type": "way",
            "id": 123,
            "tags": {"building": "apartments", "building:levels": "8", "name": "Torre A"},
            "geometry": [
                {"lat": -8.06, "lon": -34.87},
                {"lat": -8.06, "lon": -34.869},
                {"lat": -8.059, "lon": -34.869},
                {"lat": -8.059, "lon": -34.87},
                {"lat": -8.06, "lon": -34.87},
            ],
        }
    ]
    records = elements_to_records(elements, "2611606")
    assert len(records) == 1
    assert records[0]["altura_m"] == 24.0
    assert records[0]["fonte_altura"] == "osm_levels"
    assert records[0]["qualidade"] == "Estimado"
    assert records[0]["nome"] == "Torre A"


def test_seed_recife_has_polygons():
    seed = _seed_recife_centro()
    assert len(seed) == 36
    assert all(r["geom"].area > 0 for r in seed)


@patch("app.data_connectors.building_footprints_collector.collect_buildings_municipality")
def test_buildings_geojson_empty_triggers_collect(mock_collect):
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"

    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        name = getattr(model, "__name__", str(model))
        if "Municipio" in name and "Edific" not in name:
            q.filter.return_value.first.return_value = muni
        else:
            # count then all
            q.filter.return_value.count.return_value = 0
            q.filter.return_value.all.return_value = []
            q.filter.return_value.limit.return_value.all.return_value = []
        return q

    db.query.side_effect = query_side_effect
    mock_collect.return_value = {"count": 0, "status": "ok"}

    fc = buildings_geojson(db, "2611606", ensure=True)
    assert fc["type"] == "FeatureCollection"
    mock_collect.assert_called_once()


def test_upsert_uses_from_shape():
    muni = MagicMock()
    muni.id = 9
    muni.codigo_ibge = "2611606"
    db = MagicMock()
    records = [
        {
            "osm_id": "way/1",
            "nome": "A",
            "uso": "yes",
            "pavimentos": 2,
            "altura_m": 6.0,
            "fonte_altura": "heuristic",
            "qualidade": "Derivado",
            "fonte_footprint": "seed",
            "geom": box(-34.87, -8.06, -34.869, -8.059),
        }
    ]
    n = upsert_edificacoes(db, muni, records)
    assert n == 1
    assert db.add.called
    assert db.commit.called
