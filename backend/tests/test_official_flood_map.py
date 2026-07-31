"""Testes da camada de validação com manchas oficiais (20h.5)."""

from app.services.official_flood_map_service import (
    evaluate_against_official_polygons,
    load_official_flood_geojson,
    official_flood_map_path,
)


def _square_geojson(x0: float, y0: float, x1: float, y1: float) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
                    ],
                },
            }
        ],
    }


def test_load_official_flood_geojson_recife_fixture():
    geojson = load_official_flood_geojson("2611606")
    assert geojson is not None
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) >= 1
    props = geojson["features"][0]["properties"]
    assert props.get("categoria") == "estudo_piloto"


def test_official_flood_map_path_resolves_for_recife():
    path = official_flood_map_path("2611606")
    assert path is not None
    assert path.name == "2611606.geojson"


def test_load_official_flood_geojson_missing_municipio_returns_none():
    assert load_official_flood_geojson("9999999") is None


def test_evaluate_against_official_polygons_full_overlap():
    square = _square_geojson(0, 0, 1, 1)
    result = evaluate_against_official_polygons(square, square)
    assert result["disponivel"] is True
    assert result["iou"] == 1.0
    assert result["coverage_sim_in_official"] == 1.0
    assert result["coverage_official_in_sim"] == 1.0


def test_evaluate_against_official_polygons_partial_overlap():
    official = _square_geojson(0, 0, 1, 1)
    sim = _square_geojson(0.5, 0, 1.5, 1)
    result = evaluate_against_official_polygons(sim, official)
    assert result["disponivel"] is True
    # interseção = 0.5 (área), união = 1.5 -> IoU = 1/3
    assert abs(result["iou"] - (1 / 3)) < 1e-3
    assert result["coverage_sim_in_official"] == 0.5
    assert result["coverage_official_in_sim"] == 0.5


def test_evaluate_against_official_polygons_no_overlap():
    official = _square_geojson(0, 0, 1, 1)
    sim = _square_geojson(10, 10, 11, 11)
    result = evaluate_against_official_polygons(sim, official)
    assert result["disponivel"] is True
    assert result["iou"] == 0.0
    assert result["coverage_sim_in_official"] == 0.0
    assert result["coverage_official_in_sim"] == 0.0


def test_evaluate_against_official_polygons_missing_official():
    sim = _square_geojson(0, 0, 1, 1)
    result = evaluate_against_official_polygons(sim, None)
    assert result["disponivel"] is False
    assert result["iou"] is None


def test_evaluate_against_official_polygons_missing_sim():
    official = _square_geojson(0, 0, 1, 1)
    result = evaluate_against_official_polygons(None, official)
    assert result["disponivel"] is False
    assert result["iou"] is None


def test_evaluate_against_real_recife_fixture_self_overlap():
    official = load_official_flood_geojson("2611606")
    result = evaluate_against_official_polygons(official, official)
    assert result["disponivel"] is True
    assert result["iou"] == 1.0
