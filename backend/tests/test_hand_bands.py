"""Camada HAND em faixas."""

from __future__ import annotations

import numpy as np

from app.services.hand_service import HAND_BANDS, HAND_BAND_COLORS, compute_hand_raster


def test_hand_bands_cover_low_range():
    ids = [b[0] for b in HAND_BANDS]
    assert "muito_baixa" in ids and "baixa" in ids
    assert all(bid in HAND_BAND_COLORS for bid in ids)


def test_compute_hand_stream_cells_zero():
    elev = np.zeros((12, 12), dtype=np.float64)
    # tigela: centro baixo
    yy, xx = np.mgrid[0:12, 0:12]
    elev = 10.0 + 0.2 * ((xx - 6) ** 2 + (yy - 6) ** 2)
    mask = np.ones_like(elev, dtype=bool)
    hand, meta = compute_hand_raster(elev, mask)
    assert meta.get("ok") is True
    assert meta.get("stream_cells", 0) >= 1
    assert np.isfinite(hand[mask]).any()
    # centro (perto da drenagem) deve ter HAND menor que borda
    assert float(hand[6, 6]) <= float(hand[0, 0]) + 1e-6
