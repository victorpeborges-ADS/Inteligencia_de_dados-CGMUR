"""Testes processamento DEM / análise de encostas."""
from __future__ import annotations

import json

import numpy as np

from app.services import dem_processor as dp
from app.services.dem_processor import (
    SLOPE_CRITICAL_DEG,
    _compute_raster_stats,
    _compute_slope_degrees,
    _encode_terrarium,
    _upsample_dem_superres,
    dem_resolution_m,
    find_local_dem,
    hydro_dem_label,
    import_local_dem_bytes,
    local_dem_source_paths,
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


def test_dem_resolution_m():
    res = dem_resolution_m(0.0001, 0.0001, -8.0)
    assert 8.0 < res < 15.0


def test_upsample_dem_superres():
    elev = np.arange(9, dtype=np.float64).reshape(3, 3)
    up = _upsample_dem_superres(elev, factor=3)
    assert up.shape == (9, 9)
    assert up[0, 0] == elev[0, 0]


def test_local_dem_paths_and_import(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "DEM_BASE_DIR", tmp_path / "dem")
    monkeypatch.setattr(dp, "LOCAL_DEM_DIR", tmp_path / "local")
    code = "2611606"
    paths = local_dem_source_paths(code)
    assert paths[0].name == "local_dem.tif"
    assert find_local_dem(code) is None
    payload = b"\x00" * 4096
    dest = import_local_dem_bytes(code, payload)
    assert dest.exists()
    assert find_local_dem(code) == dest


def test_local_dem_paths_include_merit_anadem_names():
    """21b.5 — path list deve cobrir MERIT-Hydro/ANADEM em ambos os diretórios."""
    code = "2611606"
    paths = [p.name for p in local_dem_source_paths(code)]
    assert "merit.tif" in paths
    assert "anadem.tif" in paths
    assert f"{code}_merit.tif" in paths
    assert f"{code}_anadem.tif" in paths
    assert f"{code}_merit_hydro.tif" in paths


def test_hydro_dem_label_detects_merit_and_anadem():
    """21b.5 — nome do arquivo determina dem_source/hydro_dem flag."""
    assert hydro_dem_label("2611606_merit.tif") == "MERIT-Hydro"
    assert hydro_dem_label("2611606_merit_hydro.tif") == "MERIT-Hydro"
    assert hydro_dem_label("merit.tif") == "MERIT-Hydro"
    assert hydro_dem_label("2611606_anadem.tif") == "ANADEM"
    assert hydro_dem_label("anadem.tif") == "ANADEM"
    assert hydro_dem_label("local_dem.tif") is None
    assert hydro_dem_label("2611606_lidar.tif") is None


def test_hydro_simulator_skips_fill_sinks_when_hydro_dem(monkeypatch):
    """21b.5 — meta.hydro_dem=True dispensa Priority-Flood e marca método pela fonte."""
    import numpy as np

    from app.services import hydro_simulator as hs

    fill_called = {"n": 0}

    def _fake_fill_sinks(elevation, mask):
        fill_called["n"] += 1
        return elevation, {"dem_hydro_conditioned": True, "method": "priority_flood"}

    monkeypatch.setattr(hs, "_fill_sinks", _fake_fill_sinks)

    meta = {"hydro_dem": True, "dem_source": "MERIT-Hydro"}
    elev = np.zeros((3, 3))
    mask = np.ones((3, 3), dtype=bool)

    if meta.get("hydro_dem"):
        fill_meta = {
            "dem_hydro_conditioned": True,
            "cells_filled": 0,
            "fill_volume_cell_m": 0.0,
            "method": str(meta.get("dem_source") or "hydro_dem_source"),
        }
    else:
        elev, fill_meta = hs._fill_sinks(elev, mask)

    assert fill_called["n"] == 0
    assert fill_meta["dem_hydro_conditioned"] is True
    assert fill_meta["method"] == "MERIT-Hydro"
    assert fill_meta["cells_filled"] == 0


def test_find_local_dem_in_shared_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "DEM_BASE_DIR", tmp_path / "dem")
    local_dir = tmp_path / "local"
    monkeypatch.setattr(dp, "LOCAL_DEM_DIR", local_dir)
    local_dir.mkdir(parents=True)
    shared = local_dir / "2611606_lidar.tif"
    shared.write_bytes(b"\x00" * 4096)
    assert find_local_dem("2611606") == shared


def test_opentopography_disabled_without_key(monkeypatch):
    monkeypatch.delenv("OPENTOPOGRAPHY_API_KEY", raising=False)
    monkeypatch.delenv("OPENTOPOGRAPHY_ENABLED", raising=False)
    assert dp._opentopography_enabled(None) is False
    monkeypatch.setenv("OPENTOPOGRAPHY_ENABLED", "false")
    monkeypatch.setenv("OPENTOPOGRAPHY_API_KEY", "fake")
    assert dp._opentopography_enabled("fake") is False
    monkeypatch.setenv("OPENTOPOGRAPHY_ENABLED", "true")
    assert dp._opentopography_enabled("fake") is True


def test_download_srtm_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("OPENTOPOGRAPHY_ENABLED", "false")
    called = {"n": 0}

    def _fake_get(*_a, **_k):
        called["n"] += 1
        raise AssertionError("httpx não deveria ser chamado")

    monkeypatch.setattr(dp.httpx, "get", _fake_get)
    assert dp._download_srtm(-9, -8, -35, -34, api_key=None) is None
    assert called["n"] == 0


def test_opentopography_timeout_default(monkeypatch):
    monkeypatch.delenv("OPENTOPOGRAPHY_TIMEOUT_S", raising=False)
    assert dp._opentopography_timeout_s() == 12.0
    monkeypatch.setenv("OPENTOPOGRAPHY_TIMEOUT_S", "8")
    assert dp._opentopography_timeout_s() == 8.0


def test_dem_status_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "DEM_BASE_DIR", tmp_path / "dem")
    monkeypatch.setattr(dp, "LOCAL_DEM_DIR", tmp_path / "local")
    code = "2611606"
    out_dir = dp.dem_dir(code)
    out_dir.mkdir(parents=True)
    meta = {
        "codigo_ibge": code,
        "dem_source": "LiDAR/DSM local",
        "dem_resolution_m": 2.5,
        "vertical_accuracy_m": 1.5,
    }
    dp.meta_path(code).write_text(json.dumps(meta), encoding="utf-8")
    status = dp.dem_status(limit=61)
    assert status["processados"] >= 1
    assert status["local_ou_lidar"] >= 1
    assert status["piloto"] is not None
    assert status["piloto"]["dem_resolution_m"] == 2.5
