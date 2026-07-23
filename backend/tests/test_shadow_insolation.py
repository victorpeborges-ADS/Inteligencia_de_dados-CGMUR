"""Testes 17d.3 sombra/insolação e helpers 17f.8."""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.shadow_insolation_service import solar_position, _hsp_factor, _shade_from_neighbors


def test_solar_position_noon_tropical():
    # meio-dia UTC aproximado sobre Recife lon
    when = datetime(2026, 3, 21, 15, 0, tzinfo=timezone.utc)  # ~12h BRT
    sun = solar_position(-8.05, -34.88, when)
    assert "elevacao_graus" in sun
    assert "azimute_graus" in sun
    assert -90 <= sun["elevacao_graus"] <= 90


def test_hsp_and_shade():
    assert _hsp_factor(-5) == 0.0
    assert _hsp_factor(90) > 0.9
    shade = _shade_from_neighbors(10, [30, 28, 12], 20)
    assert 0 < shade <= 0.9
    open_sky = _shade_from_neighbors(20, [10, 12], 60)
    assert open_sky < shade
