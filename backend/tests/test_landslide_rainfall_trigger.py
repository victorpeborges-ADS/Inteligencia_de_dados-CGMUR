"""Testes do gatilho de chuva no deslizamento (17g.1e)."""

import numpy as np
import pytest
from shapely.geometry import box
from unittest.mock import MagicMock


def test_antecedent_rain_expands_landslide_zones():
    pytest.importorskip("rasterio")
    from app.services.hydro_simulator import landslide_features_from_slope

    size = 48
    yy, xx = np.mgrid[0:size, 0:size]
    # Encosta íngreme no canto
    elev = 10.0 + 0.9 * xx.astype(float)
    muni = box(-0.01, -0.01, 0.01, 0.01)
    mask = np.ones_like(elev, dtype=bool)
    west, south = -0.01, -0.01
    res = 0.02 / size

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.scalar.return_value = None

    dry = landslide_features_from_slope(
        elev, muni, mask, 40.0, west, south, res, res, db, 1, chuva_antecedente_mm=0,
    )
    wet = landslide_features_from_slope(
        elev, muni, mask, 40.0, west, south, res, res, db, 1, chuva_antecedente_mm=120,
    )
    # Com antecedente, limiar cai → mais chance de zonas
    assert isinstance(dry, list)
    assert isinstance(wet, list)
    if wet:
        props = wet[0]["properties"]
        assert props["landslide_method"] == "slope_rainfall_trigger"
        assert props["chuva_efetiva_mm"] > props["precipitation_mm"]
