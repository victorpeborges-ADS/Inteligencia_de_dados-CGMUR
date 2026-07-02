"""Testes do interpretador de simulações."""

from unittest.mock import MagicMock, patch

from app.services.simulation_interpreter import (
    _deterministic_interpretation,
    extract_simulation_metrics,
    _nivel_suscetibilidade,
)


def test_nivel_suscetibilidade():
    assert _nivel_suscetibilidade(40) == "MUITO_ALTA"
    assert _nivel_suscetibilidade(15) == "MEDIA"
    assert _nivel_suscetibilidade(5) == "BAIXA"


@patch("app.services.simulation_interpreter._equipamentos_na_mancha")
@patch("app.services.simulation_interpreter._historico_s2id")
def test_extract_metrics(mock_s2id, mock_eq):
    mock_eq.return_value = []
    mock_s2id.return_value = {"total": 0, "evento_similar": None}
    db = MagicMock()
    muni = MagicMock()
    muni.id = 1
    muni.nome = "Recife"
    muni.uf = "PE"
    sim = {
        "affected_area_km2": 8.4,
        "affected_population": 47000,
        "affected_bairros": ["Centro", "Boa Viagem"],
        "simulation_meta": {
            "bairros_exposicao": [
                {"bairro": "Centro", "exposicao_pct": 45.0, "populacao_exposta": 12000},
            ],
        },
        "geometry": {"type": "FeatureCollection", "features": []},
    }
    metrics = extract_simulation_metrics(db, muni, sim, parametro_atual=120)
    assert metrics["area_afetada_km2"] == 8.4
    assert metrics["n_bairros_afetados"] == 1


def test_deterministic_has_disclaimer():
    muni = MagicMock(nome="Recife", uf="PE")
    metrics = {
        "area_afetada_km2": 5,
        "populacao_estimada_atingida": 1000,
        "n_bairros_afetados": 2,
        "bairros_afetados": [{"nome": "Centro", "exposicao_pct": 30}],
        "equipamentos": [],
        "historico_s2id": {"evento_similar": None},
    }
    out = _deterministic_interpretation(muni, metrics, tipo_simulacao="chuva", parametro_atual=120, parametro_referencia=None)
    assert "simulação exploratória" in out["disclaimer"].lower()
    assert out["resumo_executivo"]
