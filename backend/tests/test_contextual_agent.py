"""Testes do agente contextual."""

from unittest.mock import MagicMock, patch

from app.services.contextual_agent_tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    get_georedus_referencia,
    get_score_municipio,
)


def test_tool_definitions_count():
    assert len(TOOL_DEFINITIONS) == 8
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert "get_bairros_criticos" in names
    assert "get_score_municipio" in names
    assert "get_georedus_referencia" in names


def test_execute_tool_unknown():
    db = MagicMock()
    result = execute_tool(db, "tool_inexistente", {})
    assert "error" in result


@patch("app.services.contextual_agent_tools.executive_snapshot")
@patch("app.services.contextual_agent_tools.audit_municipio")
def test_get_score_municipio(mock_audit, mock_snap):
    db = MagicMock()
    muni = MagicMock()
    muni.nome = "Recife"
    muni.uf = "PE"
    db.query.return_value.filter.return_value.first.return_value = muni
    mock_snap.return_value = {"score_sinidu": 53, "media_ivc": 0.5, "media_iri": 0.4, "media_adaptacao": 0.6}
    mock_audit.return_value = {"score_confiabilidade": "MEDIA", "confiabilidade_geral": "MEDIA", "score": {"campos_reais_pct": 55}}

    out = get_score_municipio(db, "2611606")
    assert out["score_sinidu"] == 53
    assert out["score_confiabilidade"] == "MEDIA"


@patch("app.services.contextual_agent_tools.build_georedus_referencia")
def test_get_georedus_referencia_tool(mock_build):
    db = MagicMock()
    mock_build.return_value = {
        "georedus_url": "https://www.redus.org.br/georedus?v=v0&municipioId=2611606",
        "indicadores_sugeridos": [{"id": "georedus_saude", "label": "Equipamentos de saúde"}],
    }
    out = get_georedus_referencia(db, "2611606", tema="saúde")
    assert "georedus_url" in out
    mock_build.assert_called_once_with(db, "2611606", tema="saúde", query=None)
