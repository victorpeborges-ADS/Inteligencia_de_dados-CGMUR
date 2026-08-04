"""Testes do simulador pluvial territorial."""

import numpy as np
from shapely.geometry import Polygon, box

from app.services.hydro_simulator import (
    _adaptive_contour_interval,
    _compute_d8_accumulation,
    _downsample_elevation_grid,
    _hydro_grid_limit_for,
    _lat_grid,
    _local_valley_floor,
    _smooth_dem,
    contours_geojson,
    flood_bands_geojson,
)


def _bowl_dem(size: int = 48) -> tuple[np.ndarray, Polygon]:
    yy, xx = np.mgrid[0:size, 0:size]
    cx, cy = size // 2, size // 2
    elev = 20.0 + 0.08 * ((xx - cx) ** 2 + (yy - cy) ** 2)
    muni = box(-0.01, -0.01, 0.01, 0.01)
    return elev, muni


def test_d8_accumulation_peaks_at_valley():
    elev, _ = _bowl_dem()
    mask = np.ones_like(elev, dtype=bool)
    acc = _compute_d8_accumulation(elev, mask)
    cr, cc = acc.shape[0] // 2, acc.shape[1] // 2
    assert acc[cr, cc] > acc[0, 0]
    assert acc[cr, cc] >= 10


def test_flood_bands_produce_depth_with_rasterio():
    pytest = __import__("pytest")
    pytest.importorskip("rasterio")
    elev, muni = _bowl_dem(64)
    rows, cols = elev.shape
    west, south = -0.01, -0.01
    res_x = 0.02 / cols
    res_y = 0.02 / rows
    imperm = np.full_like(elev, 0.75)
    slope = np.zeros_like(elev)
    acc = _compute_d8_accumulation(elev, np.ones_like(elev, dtype=bool))

    fc, depth = flood_bands_geojson(
        elev,
        muni,
        precip_mm=120.0,
        river_shapes=[],
        west=west,
        south=south,
        res_x=res_x,
        res_y=res_y,
        impermeability_raster=imperm,
        slope_deg=slope,
        accumulation=acc,
    )
    features = fc.get("features", [])
    assert len(features) >= 1
    assert float(np.max(depth)) > 0.05
    bands = {f["properties"]["depth_band"] for f in features}
    assert "superficial" in bands or "moderada" in bands


def test_adaptive_contour_interval_low_relief():
    assert _adaptive_contour_interval(2.0, 12.0, 30.0) == 2.0
    assert _adaptive_contour_interval(5.0, 45.0, 30.0) == 10.0


def test_smooth_dem_preserves_shape_and_mask():
    elev = np.arange(100, dtype=np.float64).reshape(10, 10)
    mask = np.ones_like(elev, dtype=bool)
    mask[0, :] = False
    out = _smooth_dem(elev, mask, passes=2)
    assert out.shape == elev.shape
    assert np.isnan(out[0, 0])
    assert np.isfinite(out[5, 5])


def test_downsample_elevation_grid_caps_dim():
    elev = np.arange(120 * 120, dtype=np.float64).reshape(120, 120)
    down, west, south, rx, ry = _downsample_elevation_grid(
        elev, -1.0, -2.0, 0.001, 0.001, max_dim=40,
    )
    assert max(down.shape) <= 40
    assert west == -1.0 and south == -2.0
    assert rx > 0.001 and ry > 0.001
    # Sem necessidade de downsample
    same, *_ = _downsample_elevation_grid(elev[:20, :20], 0, 0, 0.01, 0.01, max_dim=40)
    assert same.shape == (20, 20)


def test_hydro_grid_limit_fine_vs_medium(monkeypatch):
    monkeypatch.delenv("HYDRO_MAX_GRID_DIM", raising=False)
    monkeypatch.delenv("HYDRO_LIDAR_MAX_GRID_DIM", raising=False)
    fine = np.zeros((4000, 4000), dtype=np.float32)
    assert _hydro_grid_limit_for({"dem_resolution_m": 2.0}, fine, 2e-5, 2e-5, -8.0) >= 1024
    # ~20 m — não forçar grade fina só por rótulo LiDAR
    med = np.zeros((1152, 1152), dtype=np.float32)
    lim = _hydro_grid_limit_for(
        {"dem_source": "LiDAR/DSM local", "dem_resolution_m": 20.0},
        med, 1.5e-4, 2e-4, -8.0,
    )
    assert lim == 512


def test_local_valley_floor_follows_two_basins():
    elev = np.full((40, 40), 50.0)
    elev[5:15, 5:15] = 10.0   # vale A
    elev[25:35, 25:35] = 20.0  # vale B (mais alto)
    elev[8:12, 8:12] = 8.0
    elev[28:32, 28:32] = 18.0
    mask = np.ones_like(elev, dtype=bool)
    floor = _local_valley_floor(elev, mask, res_m=10.0, window_m=80.0)
    assert floor[10, 10] < floor[30, 30]
    assert floor[10, 10] <= 10.0 + 1e-6


def test_contours_respect_north_up_orientation():
    rows, cols = 48, 48
    west, south = -0.02, -0.02
    res = 0.04 / cols
    yy, xx = np.mgrid[0:rows, 0:cols]
    elev = 10.0 + 25.0 * (1.0 - yy / max(rows - 1, 1)) + 3.0 * np.sin(xx / 6.0)
    mask = np.ones_like(elev, dtype=bool)
    fc = contours_geojson(elev, west, south, res, res, muni_mask=mask, interval_m=5.0)
    assert len(fc["features"]) >= 1
    lats = _lat_grid(rows, south, res)
    assert lats[0] > lats[-1]
    # Curvas devem estar dentro do envelope municipal
    for feat in fc["features"]:
        for lon, lat in feat["geometry"]["coordinates"]:
            assert west <= lon <= west + cols * res
            assert south <= lat <= south + rows * res


def test_contours_include_resolution_metadata():
    elev = np.full((24, 24), 15.0)
    elev[12:, :] = 8.0
    mask = np.ones_like(elev, dtype=bool)
    fc = contours_geojson(elev, -0.01, -0.01, 0.001, 0.001, muni_mask=mask)
    assert fc.get("properties", {}).get("dem_resolution_m", 0) > 0
    if fc["features"]:
        assert "dem_resolution_m" in fc["features"][0]["properties"]

    pytest = __import__("pytest")
    pytest.importorskip("rasterio")
    elev, muni = _bowl_dem(48)
    rows, cols = elev.shape
    west, south = -0.01, -0.01
    res_x = 0.02 / cols
    res_y = 0.02 / rows
    kwargs = dict(
        river_shapes=[],
        west=west,
        south=south,
        res_x=res_x,
        res_y=res_y,
        impermeability_raster=np.full_like(elev, 0.7),
        slope_deg=np.zeros_like(elev),
        accumulation=_compute_d8_accumulation(elev, np.ones_like(elev, dtype=bool)),
    )
    _, depth_low = flood_bands_geojson(elev, muni, 60.0, **kwargs)
    _, depth_high = flood_bands_geojson(elev, muni, 180.0, **kwargs)
    assert float(np.max(depth_high)) > float(np.max(depth_low))
