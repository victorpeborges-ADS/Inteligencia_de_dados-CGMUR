"""Testes — casos de sucesso e busca semântica."""

from __future__ import annotations

from app.services.casos_sucesso_service import (
    SEED_CASES,
    POP_FAIXAS,
    _passes_filters,
    _scale_factor,
    format_caso_referencia,
    regiao_from_uf,
    embedding_source_text,
)


def test_regiao_from_uf():
    assert regiao_from_uf("PE") == "Nordeste"
    assert regiao_from_uf("SP") == "Sudeste"
    assert regiao_from_uf("RS") == "Sul"


def test_seed_has_minimum_cases():
    assert len(SEED_CASES) >= 15
    for case in SEED_CASES:
        assert case.get("problema_original")
        assert case.get("solucao_implementada")
        assert case.get("fonte_referencia")


def test_format_caso_referencia():
    texto = format_caso_referencia(
        {
            "municipio_nome": "Guarulhos",
            "municipio_uf": "SP",
            "ano_implementacao": 2019,
            "programa_financiador": "PAC Drenagem",
            "custo_estimado_reais": 8_000_000,
            "resultado_mensuravel": "Redução de 60% nos alagamentos",
        }
    )
    assert "Guarulhos/SP" in texto
    assert "PAC Drenagem" in texto
    assert "60%" in texto


def test_passes_filters_faixa_populacao():
    case = {"regiao": "Sudeste", "tipo_intervencao": "drenagem", "populacao_aprox": 1_345_000}
    assert _passes_filters(case, faixa_populacao="metropole")
    assert not _passes_filters(case, faixa_populacao="pequeno")


def test_scale_factor():
    assert _scale_factor(1_000_000, 500_000) == 0.5
    assert _scale_factor(None, 100_000) == 1.0


def test_embedding_source_text():
    text = embedding_source_text(SEED_CASES[0])
    assert "Guarulhos" in text
    assert "drenagem" in text.lower() or "piscin" in text.lower()


def test_pop_faixas_cover_ranges():
    assert POP_FAIXAS["pequeno"][1] == 100_000
    assert POP_FAIXAS["metropole"][0] == 1_000_000
