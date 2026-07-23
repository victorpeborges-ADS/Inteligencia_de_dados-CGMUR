"""Regressão numérica do motor pluvial (17g.2f).

- Sem rasterio: golden de D8/acumulação (sempre roda no host).
- Com rasterio: golden de flood_bands (CI/Docker).
Regenerar: UPDATE_GOLDEN=1 pytest tests/test_hydro_regression.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from app.services.hydro_simulator import (
    HYDRO_MODEL_VERSION,
    _compute_d8_accumulation,
    flood_bands_geojson,
)

FIXTURES = Path(__file__).parent / "fixtures"
D8_GOLDEN = FIXTURES / "hydro_d8_bowl_golden.json"
FLOOD_GOLDEN = FIXTURES / "hydro_bowl_120_golden.json"


def _bowl_elev(size: int = 48) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size]
    cx, cy = size // 2, size // 2
    return 20.0 + 0.08 * ((xx - cx) ** 2 + (yy - cy) ** 2)


def _d8_snapshot() -> dict:
    elev = _bowl_elev(48)
    acc = _compute_d8_accumulation(elev, np.ones_like(elev, dtype=bool))
    cr = cc = 24
    return {
        "model_version": HYDRO_MODEL_VERSION,
        "size": 48,
        "acc_max": round(float(np.max(acc)), 4),
        "acc_center": round(float(acc[cr, cc]), 4),
        "acc_sum": round(float(np.sum(acc)), 2),
        "acc_corner": round(float(acc[0, 0]), 4),
    }


def _assert_or_write_golden(path: Path, snap: dict, *, rtol_keys: dict[str, float] | None = None):
    FIXTURES.mkdir(parents=True, exist_ok=True)
    if os.getenv("UPDATE_GOLDEN") == "1" or not path.exists():
        path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if os.getenv("UPDATE_GOLDEN") == "1":
            pytest.skip("Golden atualizado — rode novamente sem UPDATE_GOLDEN")
        # primeira criação: valida ranges e segue
        return

    golden = json.loads(path.read_text(encoding="utf-8"))
    assert snap["model_version"] == golden["model_version"], (
        f"model_version mudou ({golden['model_version']} → {snap['model_version']}); "
        "atualize o golden com UPDATE_GOLDEN=1 se intencional"
    )
    rtol_keys = rtol_keys or {}
    for key, value in snap.items():
        if key == "model_version":
            continue
        if key in rtol_keys:
            assert abs(float(value) - float(golden[key])) <= rtol_keys[key], (
                f"{key}: {value} vs golden {golden[key]}"
            )
        else:
            assert value == golden[key], f"{key}: {value} vs golden {golden[key]}"


def test_hydro_regression_d8_golden():
    snap = _d8_snapshot()
    assert snap["acc_center"] > snap["acc_corner"]
    assert snap["acc_max"] >= snap["acc_center"]
    _assert_or_write_golden(
        D8_GOLDEN,
        snap,
        rtol_keys={"acc_sum": 1.0, "acc_max": 0.01, "acc_center": 0.01},
    )


def test_hydro_regression_model_version_pinned():
    """Garante que a versão do motor não muda silenciosamente."""
    assert HYDRO_MODEL_VERSION == "2.7"


def test_hydro_regression_flood_bands_golden():
    rasterio = pytest.importorskip("rasterio")
    del rasterio
    from shapely.geometry import box

    size = 64
    elev = _bowl_elev(size)
    muni = box(-0.01, -0.01, 0.01, 0.01)
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
    features = fc.get("features") or []
    bands: dict[str, int] = {}
    for f in features:
        band = (f.get("properties") or {}).get("depth_band") or "unknown"
        bands[band] = bands.get(band, 0) + 1

    snap = {
        "model_version": HYDRO_MODEL_VERSION,
        "precip_mm": 120.0,
        "max_depth_m": round(float(np.nanmax(depth)), 4),
        "flood_patches": len(features),
        "bands": bands,
        "depth_finite_cells": int(np.isfinite(depth).sum()),
    }
    assert snap["flood_patches"] >= 1
    assert 0.05 < snap["max_depth_m"] < 5.0

    if os.getenv("UPDATE_GOLDEN") == "1" or not FLOOD_GOLDEN.exists():
        FIXTURES.mkdir(parents=True, exist_ok=True)
        FLOOD_GOLDEN.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if os.getenv("UPDATE_GOLDEN") == "1":
            pytest.skip("Golden flood atualizado")
        return

    golden = json.loads(FLOOD_GOLDEN.read_text(encoding="utf-8"))
    assert snap["model_version"] == golden["model_version"]
    assert snap["flood_patches"] == golden["flood_patches"]
    assert snap["bands"] == golden["bands"]
    assert abs(snap["max_depth_m"] - golden["max_depth_m"]) <= 0.05
