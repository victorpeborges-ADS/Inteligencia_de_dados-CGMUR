"""Testes do contexto regional."""

from unittest.mock import MagicMock, patch

from app.services.regional_context_service import (
    _aggregate_metrics,
    _peer_codigos_ibge,
    build_regional_overlay,
)


def test_peer_codigos_regiao_imediata():
    localidade = {
        "regiao-imediata": {"id": 260001, "nome": "Recife, PE"},
    }
    with patch(
        "app.services.regional_context_service._fetch_municipios_por_nivel",
        return_value=[{"id": 2611606}, {"id": 2607901}],
    ):
        codes = _peer_codigos_ibge(localidade, "regiao_imediata")
    assert "2611606" in codes
    assert "2607901" in codes


def test_aggregate_metrics():
    result = _aggregate_metrics([
        {"disponivel": True, "score_sinidu": 50, "populacao": 1000},
        {"disponivel": True, "score_sinidu": 70, "populacao": 2000},
    ])
    assert result["municipios_com_dados"] == 2
    assert result["score_sinidu_medio"] == 60.0
    assert result["populacao_total"] == 3000


@patch("app.services.regional_context_service._fetch_municipio_localidade")
@patch("app.services.regional_context_service._peer_codigos_ibge")
@patch("app.services.regional_context_service._referencia_comparacao")
@patch("app.services.regional_context_service._regional_geojson")
@patch("app.services.regional_context_service._municipio_metrics")
def test_build_regional_overlay_structure(
    mock_metrics,
    mock_geo,
    mock_ref,
    mock_peers,
    mock_local,
):
    mock_local.return_value = {"regiao-imediata": {"id": 1, "nome": "RM"}}
    mock_peers.return_value = ["2611606", "2607901"]
    mock_ref.return_value = {"codigo_ibge": "2607901", "nome": "Jaboatão", "motivo": "UF"}
    mock_geo.return_value = {"type": "FeatureCollection", "features": []}
    mock_metrics.return_value = {"codigo_ibge": "2611606", "disponivel": True, "score_sinidu": 55}

    muni = MagicMock(codigo_ibge="2611606", nome="Recife", uf="PE", id=1)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = True

    payload = build_regional_overlay(db, muni, escopo="regiao_imediata")
    assert payload["escopo"] == "regiao_imediata"
    assert payload["referencia_comparacao"]["codigo_ibge"] == "2607901"
    assert "geojson" in payload
