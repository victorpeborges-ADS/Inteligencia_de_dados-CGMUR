"""Testes da malha territorial (bairros Voronoi + infraestrutura curada)."""

from shapely.geometry import Point, Polygon

from app.data_connectors.territorial_mesh_collector import (
    GENERIC_BAIRRO_NAMES,
    RECIFE_BAIRRO_SEEDS,
    _partition_voronoi,
    _seeds_for_municipio,
)


class _FakeMuni:
    def __init__(self, codigo_ibge: str):
        self.codigo_ibge = codigo_ibge


def test_recife_has_expanded_bairro_seeds():
    assert len(RECIFE_BAIRRO_SEEDS) >= 48
    assert "Pina" in RECIFE_BAIRRO_SEEDS
    assert "Tejipió" in RECIFE_BAIRRO_SEEDS
    assert "Brasília Teimosa" in RECIFE_BAIRRO_SEEDS


def test_generic_bairro_names_are_detected():
    assert "Zona Norte" in GENERIC_BAIRRO_NAMES
    assert len(GENERIC_BAIRRO_NAMES) == 6


def test_partition_voronoi_produces_multiple_regions():
    muni_poly = Polygon(
        [
            (-34.98, -8.18),
            (-34.84, -8.18),
            (-34.84, -7.98),
            (-34.98, -7.98),
            (-34.98, -8.18),
        ]
    )
    seeds = {
        "A": (-34.92, -8.10),
        "B": (-34.88, -8.06),
        "C": (-34.94, -8.04),
    }
    parts = _partition_voronoi(muni_poly, seeds)
    assert len(parts) >= 2
    for name, geom in parts.items():
        assert not geom.is_empty
        assert muni_poly.contains(geom.centroid) or muni_poly.intersects(geom)


def test_seeds_for_recife_pilot():
    muni_poly = Point(-34.90, -8.06).buffer(0.08)
    muni = _FakeMuni("2611606")
    seeds = _seeds_for_municipio(muni, muni_poly)
    assert len(seeds) >= 48
    assert seeds["Pina"][0] < -34.87


def test_seeds_for_non_pilot_uses_generic_grid():
    muni_poly = Point(-48.0, -15.0).buffer(0.1)
    muni = _FakeMuni("5300108")
    seeds = _seeds_for_municipio(muni, muni_poly)
    assert set(seeds.keys()) <= GENERIC_BAIRRO_NAMES
