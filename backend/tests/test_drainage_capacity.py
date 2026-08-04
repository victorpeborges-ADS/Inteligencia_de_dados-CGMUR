"""Testes unitários — capacidade de drenagem 17g.1d."""

from app.services.drainage_capacity_service import (
    CAPACIDADE_MAX_MM_H,
    CAPACIDADE_MIN_MM_H,
    _clamp_cap,
    _proxy_from_density,
)


class _Muni:
    def __init__(self, pop: int, area: float):
        self.populacao = pop
        self.area_km2 = area
        self.codigo_ibge = "2611606"


def test_clamp_cap():
    assert _clamp_cap(1) == CAPACIDADE_MIN_MM_H
    assert _clamp_cap(999) == CAPACIDADE_MAX_MM_H
    assert _clamp_cap(20) == 20.0


def test_density_proxy_tiers():
    assert _proxy_from_density(_Muni(500_000, 100)) == 22.0  # 5000 hab/km²
    assert _proxy_from_density(_Muni(150_000, 100)) == 18.0
    assert _proxy_from_density(_Muni(30_000, 100)) == 15.0
    assert _proxy_from_density(_Muni(5_000, 100)) == 12.0


def test_hydro_version_bumped():
    from app.services.hydro_simulator import HYDRO_MODEL_VERSION

    assert HYDRO_MODEL_VERSION == "2.10"
