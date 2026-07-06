"""Testes do cache de interpretação de simulação."""

from unittest.mock import MagicMock, patch

from app.services import simulation_interpret_cache as cache_mod


@patch("app.services.simulation_interpret_cache.interpret_simulation")
@patch("app.services.simulation_interpret_cache.cache_set_json")
@patch("app.services.simulation_interpret_cache.cache_get_json")
def test_interpret_cache_hit(mock_get, mock_set, mock_interpret):
    mock_get.return_value = {"resumo_executivo": "cached", "from_cache": False}
    muni = MagicMock()
    muni.codigo_ibge = "2611606"
    result = cache_mod.interpret_simulation_cached(
        MagicMock(),
        muni,
        tipo_simulacao="chuva",
        parametro_atual=120,
        parametro_referencia=80,
        resultado_simulacao={"affected_area_km2": 5.0, "simulation_meta": {"flood_patches": 3}},
    )
    assert result["from_cache"] is True
    assert result["resumo_executivo"] == "cached"
    mock_interpret.assert_not_called()
    mock_set.assert_not_called()


@patch("app.services.simulation_interpret_cache.interpret_simulation")
@patch("app.services.simulation_interpret_cache.cache_set_json")
@patch("app.services.simulation_interpret_cache.cache_get_json")
def test_interpret_cache_miss(mock_get, mock_set, mock_interpret):
    mock_get.return_value = None
    mock_interpret.return_value = {"resumo_executivo": "fresh", "disclaimer": "x"}
    muni = MagicMock()
    muni.codigo_ibge = "2611606"
    result = cache_mod.interpret_simulation_cached(
        MagicMock(),
        muni,
        tipo_simulacao="chuva",
        parametro_atual=120,
        resultado_simulacao={"affected_area_km2": 5.0},
    )
    assert result["from_cache"] is False
    assert result["resumo_executivo"] == "fresh"
    mock_interpret.assert_called_once()
    mock_set.assert_called_once()
