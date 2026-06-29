from unittest.mock import patch

import pytest

from app.services.onboarding_engine import validate_ibge_code, _completeness_from_steps, _step


def test_validate_ibge_rejects_invalid():
    with pytest.raises(ValueError):
        validate_ibge_code("abc")


@patch("app.services.onboarding_engine.requests.get")
def test_validate_ibge_ok(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "id": 2611606,
        "nome": "Recife",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "PE", "regiao": {"nome": "Nordeste"}}}},
    }
    result = validate_ibge_code("2611606")
    assert result["nome"] == "Recife"
    assert result["uf"] == "PE"
    assert result["valido"] is True


def test_completeness_from_steps():
    steps = {
        "geometria": _step("ok"),
        "ibge_indicadores": _step("parcial"),
        "capag": _step("falha"),
    }
    score = _completeness_from_steps(steps)
    assert score == 20 + 15 * 0.5  # geometria ok + ibge parcial
