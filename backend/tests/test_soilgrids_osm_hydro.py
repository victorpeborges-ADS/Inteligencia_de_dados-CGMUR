"""SoilGrids HSG + hidrografia OSM helpers."""

from __future__ import annotations

from shapely.geometry import LineString

from app.services.osm_hydrography_service import merge_river_shapes
from app.services.soilgrids_service import (
    SOIL_RUNOFF_SCALE,
    hydrologic_soil_group,
    texture_class,
)


def test_sandy_loam_maps_to_b():
    # Camutanga-like: sand 56, silt 20, clay 24
    assert texture_class(56, 20, 24) in ("sandy loam", "loam", "sandy clay loam")
    hsg = hydrologic_soil_group(56, 20, 24)
    assert hsg in "ABCD"
    assert SOIL_RUNOFF_SCALE[hsg] > 0


def test_high_clay_is_d():
    assert hydrologic_soil_group(20, 25, 55) == "D"
    assert SOIL_RUNOFF_SCALE["D"] > SOIL_RUNOFF_SCALE["A"]


def test_high_sand_is_a():
    assert hydrologic_soil_group(90, 5, 5) == "A"


def test_merge_river_shapes():
    a = [LineString([(0, 0), (1, 1)])]
    b = [LineString([(2, 2), (3, 3)])]
    m = merge_river_shapes(a, b)
    assert len(m) == 2
