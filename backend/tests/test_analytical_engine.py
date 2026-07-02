"""Testes do motor analítico — risco de inundação."""

from shapely.geometry import box, LineString

from app.services.analytical_engine import AnalyticalEngine


class _FakeGeom:
    def __init__(self, shape):
        self._shape = shape


class _FakeRow:
    def __init__(self, shape):
        self.geom = _FakeGeom(shape)


def _shape_stub(_db, geom):
    if hasattr(geom, "centroid"):
        return geom
    if hasattr(geom, "_shape"):
        return geom._shape
    return geom


def test_water_proximity_intersects(monkeypatch):
    monkeypatch.setattr(AnalyticalEngine, "_shape_from_db_geometry", _shape_stub)
    muni = box(-35.0, -8.2, -34.8, -7.9)
    river = LineString([(-34.95, -8.1), (-34.90, -8.05)])
    water_rows = [_FakeRow(river)]
    unit_near = box(-34.93, -8.08, -34.91, -8.06)
    score = AnalyticalEngine._water_proximity_score(None, unit_near, water_rows, muni)
    assert score == 1.0


def test_water_proximity_decreases_with_distance(monkeypatch):
    monkeypatch.setattr(AnalyticalEngine, "_shape_from_db_geometry", _shape_stub)
    muni = box(-35.0, -8.2, -34.8, -7.9)
    river = LineString([(-34.95, -8.1), (-34.90, -8.05)])
    water_rows = [_FakeRow(river)]
    unit_far = box(-34.85, -7.95, -34.82, -7.92)
    score = AnalyticalEngine._water_proximity_score(None, unit_far, water_rows, muni)
    assert 0.2 <= score < 1.0


def test_water_proximity_empty_water(monkeypatch):
    monkeypatch.setattr(AnalyticalEngine, "_shape_from_db_geometry", _shape_stub)
    muni = box(-35.0, -8.2, -34.8, -7.9)
    unit = box(-34.93, -8.08, -34.91, -8.06)
    score = AnalyticalEngine._water_proximity_score(None, unit, [], muni)
    assert score == 0.25


def test_safe_unary_union_invalid_geometries():
    from shapely.geometry import Polygon

    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    assert not bowtie.is_valid
    merged = AnalyticalEngine._safe_unary_union([bowtie, box(3, 3, 4, 4)])
    assert merged is not None
    assert merged.area > 0
