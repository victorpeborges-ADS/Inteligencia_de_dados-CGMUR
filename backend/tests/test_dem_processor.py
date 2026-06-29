"""Testes processamento DEM / análise de encostas."""
from __future__ import annotations

import numpy as np

from app.services.dem_processor import (
    SLOPE_CRITICAL_DEG,
    _compute_raster_stats,
    _compute_slope_degrees,
    _encode_terrarium,
)


def test_terrarium_roundtrip():
    elev = np.array([[100.0, 200.0], [50.0, 300.0]], dtype=np.float64)
    rgb = _encode_terrarium(elev)
    assert rgb.shape == (2, 2, 3)
    v = rgb[:, :, 0].astype(np.float64) * 256 + rgb[:, :, 1].astype(np.float64)
    decoded = v - 32768.0
    np.testing.assert_allclose(decoded, elev, atol=1.0)


def test_slope_stats_critical_area():
    rows, cols = 20, 20
    yy, xx = np.mgrid[0:rows, 0:cols]
    elev = (yy * 2 + xx * 0.5).astype(np.float64)
    slope = _compute_slope_degrees(elev, lat=-8.0, res_x=0.001, res_y=0.001)
    stats = _compute_raster_stats(elev, slope, lat=-8.0, res_x=0.001, res_y=0.001)
    assert stats["altitude_min_m"] <= stats["altitude_max_m"]
    assert stats["suscetibilidade_alta_pct"] >= 0
    assert SLOPE_CRITICAL_DEG == 30.0
