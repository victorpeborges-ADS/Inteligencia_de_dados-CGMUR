"""Testes do serviço de clima urbano oficial."""

from __future__ import annotations

from app.services.official_climate import (
    ESTIMATED_TIMELINE,
    _PILOT_INMET_TEMP,
)


def test_recife_pilot_temperature_series_complete():
    pilot = _PILOT_INMET_TEMP["2611606"]
    assert len(pilot) >= 6
    assert pilot[1985] < pilot[2024]


def test_estimated_timeline_aligns_with_mapbiomas_years():
    years = {item["ano"] for item in ESTIMATED_TIMELINE}
    assert {1985, 1995, 2005, 2015, 2020, 2024}.issubset(years)
