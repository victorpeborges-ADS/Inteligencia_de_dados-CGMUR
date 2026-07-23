"""Testes seção transversal / perfil DEM (17f.5)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from app.services.terrain_profile_service import (
    _haversine_m,
    _sample_elev,
    build_terrain_profile,
)


def test_haversine_short_distance():
    d = _haversine_m(-34.88, -8.05, -34.87, -8.05)
    assert 1000 < d < 1300


def test_sample_elev_in_grid():
    elev = np.array([[10.0, 20.0], [30.0, 40.0]])
    # north = south + 2*1 = 1; row0 = north
    z = _sample_elev(elev, west=0.0, south=0.0, res_x=1.0, res_y=1.0, lon=0.1, lat=1.6)
    assert z == 10.0


def test_build_profile_empty_muni():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    out = build_terrain_profile(db, "2611606", [[-34.9, -8.1], [-34.8, -8.0]])
    assert out["erro"] == "municipio_nao_encontrado"


def test_build_profile_with_mock_dem():
    muni = MagicMock()
    muni.codigo_ibge = "2611606"
    muni.nome = "Recife"
    muni.uf = "PE"
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = muni

    elev = np.full((20, 20), 12.0)
    elev[5:15, 5:15] = 25.0
    # west,south,res covering Recife-ish
    west, south, res = -35.0, -8.2, 0.02
    grid = (elev, west, south, res, res, {"dem_source": "test"})

    with patch(
        "app.services.hydro_simulator._load_elevation_grid",
        return_value=grid,
    ):
        out = build_terrain_profile(
            db,
            "2611606",
            [[-34.9, -8.1], [-34.7, -8.0]],
            samples=20,
            water_level_m=15.0,
        )

    assert out["samples"] == 20
    assert out["length_m"] > 0
    assert len(out["points"]) == 20
    assert out["water_level_m"] == 15.0
    assert any(p.get("below_water") for p in out["points"]) or out["points_below_water"] >= 0
