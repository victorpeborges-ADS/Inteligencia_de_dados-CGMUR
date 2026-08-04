"""Helpers GloFAS / tile lookup (sem download obrigatório)."""

from __future__ import annotations

from app.services.glofas_hazard_service import BANDS, BAND_COLORS


def test_glofas_bands_cover_depth_range():
    ids = [b[0] for b in BANDS]
    assert ids == ["leve", "moderada", "profunda"]
    assert all(bid in BAND_COLORS for bid in ids)
    assert BANDS[0][1] < BANDS[1][1] < BANDS[2][1]
