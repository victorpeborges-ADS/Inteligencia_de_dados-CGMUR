"""Testes de nível do mar / storm surge (17g.1c)."""

from app.services.sea_level_service import is_coastal, resolve_nivel_mar


def test_coastal_pilots():
    assert is_coastal("2611606")
    assert is_coastal("2800308")
    assert not is_coastal("3550308")


def test_ssp_scenario_recife():
    r = resolve_nivel_mar("2611606", cenario_nivel_mar="ssp5_85_2100")
    assert r["costeiro"] is True
    assert r["aplicado"] is True
    assert r["nivel_mar_m"] == 0.85


def test_inland_zero():
    r = resolve_nivel_mar("3550308", cenario_nivel_mar="storm_surge")
    assert r["costeiro"] is False
    assert r["nivel_mar_m"] == 0.0
    assert r["aplicado"] is False


def test_manual_override():
    r = resolve_nivel_mar("2611606", nivel_mar_m=0.5)
    assert r["nivel_mar_m"] == 0.5
    assert r["fonte"] == "manual"
