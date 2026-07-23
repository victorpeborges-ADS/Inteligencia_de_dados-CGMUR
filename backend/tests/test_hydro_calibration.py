"""17g.2b — calibração de coeficientes."""

from __future__ import annotations

import numpy as np
from shapely.geometry import box

from app.services.hydro_calibration_service import (
    apply_manual_scales,
    calibration_cache_stamp,
    default_calibration,
    load_calibration,
)
from app.services.hydro_simulator import flood_bands_geojson


def test_default_calibration_pe_proxy():
    c = default_calibration("2611606", "PE")
    assert c["source"] == "uf_biome_proxy"
    assert c["rise_scale"] >= 1.0


def test_manual_scales_persist_and_stamp_changes(tmp_path, monkeypatch):
    from app.services import hydro_calibration_service as svc

    monkeypatch.setattr(svc, "CALIB_DIR", tmp_path)
    before = calibration_cache_stamp("2611606", "PE")
    out = apply_manual_scales(
        "2611606",
        {"rise_scale": 1.25, "runoff_scale": 1.1},
        uf="PE",
        nota="teste",
    )
    assert out["rise_scale"] == 1.25
    assert out["source"] == "manual"
    loaded = load_calibration("2611606", "PE")
    assert loaded["rise_scale"] == 1.25
    after = calibration_cache_stamp("2611606", "PE")
    assert after != before


def test_calib_scales_change_max_depth():
    rasterio = __import__("pytest").importorskip("rasterio")
    del rasterio

    size = 40
    yy, xx = np.mgrid[0:size, 0:size]
    elev = 20.0 + 0.1 * ((xx - 20) ** 2 + (yy - 20) ** 2)
    muni = box(-0.01, -0.01, 0.01, 0.01)
    west, south, res = -0.01, -0.01, 0.02 / size

    _, depth_lo = flood_bands_geojson(
        elev, muni, 120.0, [], west, south, res, res,
        calib={"runoff_scale": 0.8, "rise_scale": 0.8, "river_boost_scale": 0.8, "iri_scale": 1.0},
    )
    _, depth_hi = flood_bands_geojson(
        elev, muni, 120.0, [], west, south, res, res,
        calib={"runoff_scale": 1.3, "rise_scale": 1.3, "river_boost_scale": 1.3, "iri_scale": 1.0},
    )
    assert float(np.max(depth_hi)) > float(np.max(depth_lo))
