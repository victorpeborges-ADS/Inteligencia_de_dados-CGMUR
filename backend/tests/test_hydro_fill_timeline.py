"""17g.2d fill sinks + 17g.1b flood timeline."""

from __future__ import annotations

import numpy as np
from shapely.geometry import box

from app.services.hydro_simulator import (
    HYDROGRAPH_FACTORS,
    _fill_sinks,
    build_flood_timeline,
    flood_bands_geojson,
)


def test_fill_sinks_raises_interior_pit():
    """Poço interior com borda mais baixa (exutório) deve ser preenchido."""
    elev = np.array(
        [
            [10.0, 10.0, 10.0, 10.0, 10.0],
            [10.0, 8.0, 8.0, 8.0, 10.0],
            [10.0, 8.0, 3.0, 8.0, 9.0],  # poço 3; saída pela direita (9)
            [10.0, 8.0, 8.0, 8.0, 10.0],
            [10.0, 10.0, 10.0, 10.0, 10.0],
        ],
        dtype=np.float64,
    )
    mask = np.ones_like(elev, dtype=bool)
    filled, meta = _fill_sinks(elev, mask)
    assert meta["dem_hydro_conditioned"] is True
    assert meta["cells_filled"] >= 1
    # o fundo do poço sobe até pelo menos a cota de transbordamento (~8–9)
    assert float(filled[2, 2]) >= 8.0 - 1e-6
    assert float(filled[2, 2]) > float(elev[2, 2])


def test_fill_sinks_preserves_sloping_surface():
    """Plano inclinado sem depressão quase não preenche células."""
    yy, xx = np.mgrid[0:24, 0:24]
    elev = 50.0 - 0.5 * xx.astype(np.float64)  # drena para a esquerda
    mask = np.ones_like(elev, dtype=bool)
    filled, meta = _fill_sinks(elev, mask)
    assert meta["dem_hydro_conditioned"] is True
    # volume de preenchimento residual pequeno vs. amplitude do DEM
    assert meta["fill_volume_cell_m"] < 50.0
    assert np.allclose(filled[:, -1], elev[:, -1], atol=1e-6)


def test_flood_timeline_peak_matches_and_has_rise_recession():
    rasterio = __import__("pytest").importorskip("rasterio")
    del rasterio

    size = 48
    yy, xx = np.mgrid[0:size, 0:size]
    elev = 20.0 + 0.08 * ((xx - 24) ** 2 + (yy - 24) ** 2)
    muni = box(-0.01, -0.01, 0.01, 0.01)
    west, south = -0.01, -0.01
    res = 0.02 / size
    fc, depth = flood_bands_geojson(
        elev, muni, 120.0, [], west, south, res, res,
    )
    assert fc["features"]
    mask = np.ones_like(elev, dtype=bool)
    timeline = build_flood_timeline(
        depth, muni, mask, west, south, res, res, precip_mm=120.0,
    )
    assert timeline["n_steps"] == len(HYDROGRAPH_FACTORS)
    assert timeline["peak_index"] == list(HYDROGRAPH_FACTORS).index(1.0)
    assert timeline["steps"][0]["fase"] == "subida"
    assert timeline["steps"][timeline["peak_index"]]["fase"] == "pico"
    assert timeline["steps"][-1]["fase"] == "recessao"
    # pico deve ter profundidade >= início
    assert (
        timeline["steps"][timeline["peak_index"]]["max_depth_m"]
        >= timeline["steps"][0]["max_depth_m"]
    )
    assert len(timeline["features_by_step"]) == timeline["n_steps"]
