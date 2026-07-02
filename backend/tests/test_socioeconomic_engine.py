"""Testes do motor socioeconômico intra-municipal."""

from app.services.socioeconomic_engine import (
    classify_renda_tertiles,
    classe_renda_from_value,
    _monthly_anchor_from_pib,
    _zona_multiplier,
)


def test_monthly_anchor_from_pib():
    anchor = _monthly_anchor_from_pib(24000.0, 1_000_000)
    assert anchor > 3000


def test_zona_multiplier_periferia():
    assert _zona_multiplier("Zona Periferia") >= 0.72


def test_tertile_classification():
    p33, p66 = classify_renda_tertiles([1000, 2000, 3000, 4000, 5000, 6000])
    assert classe_renda_from_value(5500, p33, p66) == "ALTA"
    assert classe_renda_from_value(2500, p33, p66) == "MEDIA"
    assert classe_renda_from_value(1200, p33, p66) == "BAIXA"
