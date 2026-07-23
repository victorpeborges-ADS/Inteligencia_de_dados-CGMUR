"""Testes unitários — módulos climáticos 17g.1g."""

from app.services.climate_modules_service import (
    CLIMATE_MODULES_VERSION,
    _nivel,
    _temp_suitability_aedes,
)


def test_nivel_bands():
    assert _nivel(10) == "baixo"
    assert _nivel(40) == "moderado"
    assert _nivel(60) == "alto"
    assert _nivel(90) == "muito_alto"


def test_aedes_temp_peak_near_28():
    assert _temp_suitability_aedes(28) > _temp_suitability_aedes(20)
    assert _temp_suitability_aedes(28) > _temp_suitability_aedes(34)
    assert _temp_suitability_aedes(15) < 0.1


def test_version():
    assert CLIMATE_MODULES_VERSION == "1.0"
