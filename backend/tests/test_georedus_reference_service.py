"""Testes do serviço de referência GeoReDUS — Fase 16d.3."""

from unittest.mock import MagicMock, patch

from app.services.georedus_reference_service import (
    build_georedus_referencia,
    detect_georedus_source_url,
    georedus_municipio_url,
    _match_query_indicators,
)


def test_georedus_municipio_url():
    assert georedus_municipio_url("2611606") == (
        "https://www.redus.org.br/georedus?v=v0&municipioId=2611606"
    )


def test_match_query_saude():
    hits = _match_query_indicators("quantas UBS existem no município?")
    assert any(h["id"] == "georedus_saude" for h in hits)


def test_match_query_educacao():
    hits = _match_query_indicators("matrículas INEP por bairro")
    assert any(h["id"] == "georedus_inep" for h in hits)


@patch("app.services.georedus_reference_service.coverage_for_code")
def test_build_georedus_referencia(mock_coverage):
    db = MagicMock()
    muni = MagicMock()
    muni.nome = "Recife"
    muni.uf = "PE"
    db.query.return_value.filter.return_value.first.return_value = muni

    mock_coverage.return_value = (
        55,
        [],
        [{"id": "inep_censo_escolar", "nome": "INEP Censo Escolar", "status": "Ausente"}],
    )

    out = build_georedus_referencia(db, "2611606", query="educação escolar")
    assert out["georedus_url"].endswith("municipioId=2611606")
    assert out["municipio"]["nome"] == "Recife"
    assert out["tem_lacunas"] is True
    assert any(i["id"] == "georedus_inep" for i in out["indicadores_sugeridos"])
    assert "GeoReDUS" in out["instrucao_agente"]


def test_detect_georedus_source_url():
    url = georedus_municipio_url("2611606")
    assert detect_georedus_source_url("dados de saúde", "consulte o GeoReDUS", url) == url
    assert detect_georedus_source_url("olá", "tudo bem", url) is None
