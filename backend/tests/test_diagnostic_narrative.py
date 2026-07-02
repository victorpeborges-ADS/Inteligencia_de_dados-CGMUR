"""Testes da narrativa executiva IA — Step 4."""

from app.services.diagnostic_narrative_service import (
    _fallback_narrative,
    _split_paragraphs,
    build_narrative_context,
    generate_executive_narrative,
)


def test_split_paragraphs_three_sections():
    text = "§1 CONTEXTO: Primeiro parágrafo.\n\n§2 PRIORIDADES: Segundo parágrafo.\n\n§3 PRÓXIMOS PASSOS: Terceiro."
    parts = _split_paragraphs(text)
    assert len(parts) == 3
    assert "Primeiro" in parts[0]
    assert "Segundo" in parts[1]
    assert "Terceiro" in parts[2]


def test_fallback_narrative_has_three_paragraphs():
    ctx = {
        "municipio_nome": "Recife/PE",
        "score": 53,
        "severidade": "Alta",
        "ivc": 0.62,
        "iri": 0.58,
        "capag": "B",
        "top3_bairros": ["Centro", "Vasques", "Mangueira"],
        "n_eventos": 4,
        "n_alertas": 2,
        "programas": ["PAC Seleções", "Pro-Cidades"],
    }
    text = _fallback_narrative(ctx)
    assert "Recife/PE" in text
    assert "Centro" in text
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    assert len(paragraphs) == 3


def test_generate_executive_narrative_deterministic_without_ai():
    ctx = build_narrative_context(
        "Recife",
        "PE",
        snapshot={"score_sinidu": 53, "media_ivc": 0.62, "media_iri": 0.58},
        sections={
            "situacao_fiscal": {"nota_capag": "B"},
            "situacao_climatica": {"alertas_ativos": 2},
            "historico_desastres": {"total_10_anos": 3, "eventos": []},
            "lacunas": {"lacunas": ["S2ID"]},
            "principais_riscos": {"areas_criticas": [{"bairro": "Centro"}]},
        },
        action_plan={
            "total_acoes": 9,
            "acoes_curto_prazo": [{}] * 5,
            "acoes_medio_prazo": [{}],
            "acoes_longo_prazo": [{}] * 3,
            "programas_financiamento": [{"nome": "PAC Seleções"}],
        },
        severidade="Alta",
    )
    result = generate_executive_narrative(ctx, use_ai=False)
    assert result["narrativa_ia"]
    assert result["ai_provider"] == "deterministic"
    assert len(result["paragrafos"]) >= 1
