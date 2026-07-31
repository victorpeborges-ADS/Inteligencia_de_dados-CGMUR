"""Testes do simulador de ilha de calor (modelo temperatura-driven v1.1)."""

from app.services.heat_simulator import (
    HEAT_BANDS,
    _delta_t_bairro,
    _heat_band,
    _heatwave_amplification,
)

BASE_LAND = {"vegetacao": 0.2, "urbana": 0.5, "impermeabilidade": 0.6}


def test_heat_band_thresholds():
    assert _heat_band(1.0) == "leve"
    assert _heat_band(2.0) == "moderada"
    assert _heat_band(4.0) == "severa"


def test_heat_bands_cover_full_range():
    assert len(HEAT_BANDS) == 3


def test_heatwave_amplification_monotonic():
    mild = _heatwave_amplification(30.0, 27.0)
    hot = _heatwave_amplification(40.0, 27.0)
    assert hot > mild >= 1.0


def test_heatwave_amplification_floor_at_one():
    # Pico igual ou abaixo da normal não amplifica
    assert _heatwave_amplification(25.0, 27.0) == 1.0


def test_delta_t_decreases_with_shade_and_vent():
    base = _delta_t_bairro(
        land=BASE_LAND,
        density_norm=0.6,
        temperatura_pico_c=36.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=0,
        impermeabilizacao_extra_pct=0,
        shade_factor=0.0,
        ventilacao_factor=0.0,
    )
    shaded = _delta_t_bairro(
        land=BASE_LAND,
        density_norm=0.6,
        temperatura_pico_c=36.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=0,
        impermeabilizacao_extra_pct=0,
        shade_factor=0.8,
        ventilacao_factor=0.0,
    )
    ventilated = _delta_t_bairro(
        land=BASE_LAND,
        density_norm=0.6,
        temperatura_pico_c=36.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=0,
        impermeabilizacao_extra_pct=0,
        shade_factor=0.0,
        ventilacao_factor=0.8,
    )
    assert shaded < base
    assert ventilated < base


def test_heat_model_version():
    from app.services.heat_simulator import HEAT_MODEL_VERSION

    assert HEAT_MODEL_VERSION == "1.2"


def test_delta_t_increases_with_vegetation_loss():
    land = {"vegetacao": 0.4, "urbana": 0.5, "impermeabilidade": 0.5}
    mild = _delta_t_bairro(
        land=land,
        density_norm=0.6,
        temperatura_pico_c=38.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=0,
        impermeabilizacao_extra_pct=0,
    )
    severe = _delta_t_bairro(
        land=land,
        density_norm=0.6,
        temperatura_pico_c=38.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=90,
        impermeabilizacao_extra_pct=0,
    )
    assert severe > mild


def test_delta_t_increases_with_peak_temperature():
    cooler = _delta_t_bairro(
        land={**BASE_LAND, "impermeabilidade": 0.9, "vegetacao": 0.05},
        density_norm=0.6,
        temperatura_pico_c=30.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=0,
        impermeabilizacao_extra_pct=0,
    )
    hotter = _delta_t_bairro(
        land={**BASE_LAND, "impermeabilidade": 0.9, "vegetacao": 0.05},
        density_norm=0.6,
        temperatura_pico_c=42.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=0,
        impermeabilizacao_extra_pct=0,
    )
    assert hotter > cooler


def test_green_neighborhood_has_low_delta():
    green = _delta_t_bairro(
        land={"vegetacao": 0.85, "urbana": 0.05, "impermeabilidade": 0.15},
        density_norm=0.1,
        temperatura_pico_c=36.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=0,
        impermeabilizacao_extra_pct=0,
    )
    assert green < 1.0


def test_vegetation_gain_reduces_delta():
    land = {"vegetacao": 0.1, "urbana": 0.6, "impermeabilidade": 0.8}
    sem_arborizacao = _delta_t_bairro(
        land=land,
        density_norm=0.6,
        temperatura_pico_c=38.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=0,
        impermeabilizacao_extra_pct=0,
        ganho_vegetal_pct=0,
    )
    com_arborizacao = _delta_t_bairro(
        land=land,
        density_norm=0.6,
        temperatura_pico_c=38.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=0,
        impermeabilizacao_extra_pct=0,
        ganho_vegetal_pct=40,
    )
    assert com_arborizacao < sem_arborizacao


def test_more_vegetation_gain_means_more_cooling():
    land = {"vegetacao": 0.1, "urbana": 0.6, "impermeabilidade": 0.85}
    pouco = _delta_t_bairro(
        land=land,
        density_norm=0.6,
        temperatura_pico_c=40.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=0,
        impermeabilizacao_extra_pct=0,
        ganho_vegetal_pct=15,
    )
    muito = _delta_t_bairro(
        land=land,
        density_norm=0.6,
        temperatura_pico_c=40.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=0,
        impermeabilizacao_extra_pct=0,
        ganho_vegetal_pct=50,
    )
    assert muito < pouco


def test_delta_t_bounded():
    delta = _delta_t_bairro(
        land={"vegetacao": 0.0, "urbana": 1.0, "impermeabilidade": 1.0},
        density_norm=1.0,
        temperatura_pico_c=48.0,
        baseline_normal_c=27.0,
        perda_vegetal_pct=100,
        impermeabilizacao_extra_pct=50,
    )
    assert 0.0 <= delta <= 8.0
