"""Testes 17h.3a/3b (medidas + financiamento) e 17h.4a (perfil municipal)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.federal_financing_catalog import programs_for_measure, suggest_programs
from app.services.measures_catalog import recommend_measures
from app.services.municipal_profile_service import classify_porte, build_municipal_profile


def test_classify_porte_faixas():
    assert classify_porte(50_000) == "pequeno"
    assert classify_porte(250_000) == "medio"
    assert classify_porte(750_000) == "grande"
    assert classify_porte(1_500_000) == "metropole"
    assert classify_porte(None) == "pequeno"


def test_recommend_measures_bloqueia_alto_custo_capag_c():
    perfil = {
        "porte": "medio",
        "porte_label": "Médio",
        "capag": {"nota": "C"},
    }
    medidas = recommend_measures(
        perfil,
        nivel_risco="VERMELHO",
        fatores_principais=["impermeabilizacao", "s2id"],
        bairros_alvo=["Centro"],
        limit=10,
    )
    ids = {m["id"] for m in medidas}
    assert "nbs_retencao" not in ids
    assert "carteira_drenagem" not in ids
    assert "priorizar_nao_reembolsavel" in ids
    assert all(m["custo"] != "Alto" for m in medidas)
    assert any(m["custo"] == "Baixo" for m in medidas)


def test_recommend_measures_pequeno_prioriza_operacional():
    perfil = {
        "porte": "pequeno",
        "capag": {"nota": "B"},
    }
    medidas = recommend_measures(
        perfil,
        nivel_risco="LARANJA",
        fatores_principais=["s2id", "exposicao"],
        limit=8,
    )
    ids = {m["id"] for m in medidas}
    assert "carteira_drenagem" not in ids  # só grande/metrópole
    assert "apoio_sedec" in ids or "capacitacao_dc" in ids or "mon_cemaden_dc" in ids
    assert len(medidas) >= 1


def test_recommend_measures_metropole_capag_a_permite_estrutural():
    perfil = {
        "porte": "metropole",
        "capag": {"nota": "A"},
    }
    medidas = recommend_measures(
        perfil,
        nivel_risco="VERMELHO",
        fatores_principais=["impermeabilizacao", "iri"],
        limit=10,
    )
    ids = {m["id"] for m in medidas}
    assert "nbs_retencao" in ids or "carteira_drenagem" in ids


def test_programs_for_measure_capag_c_bloqueia_credito():
    fontes = programs_for_measure(
        "carteira_drenagem",
        tipo_risco="estrutural",
        custo="Alto",
        nota_capag="C",
        limit=5,
    )
    ids = {f["id"] for f in fontes}
    assert "pro_cidades" not in ids
    assert "credito_uniao" not in ids
    assert "pac_cidades" in ids or "saneamento" in ids or "orcamento_proprio" in ids


def test_programs_for_measure_capag_a_inclui_pro_cidades():
    fontes = programs_for_measure(
        "nbs_retencao",
        tipo_risco="inundacao",
        custo="Alto",
        nota_capag="A",
        limit=5,
    )
    ids = {f["id"] for f in fontes}
    assert "pro_cidades" in ids or "credito_uniao" in ids or "pac_cidades" in ids


def test_recommend_measures_anexa_fontes_financiamento():
    perfil = {"porte": "pequeno", "capag": {"nota": "D"}}
    medidas = recommend_measures(
        perfil,
        nivel_risco="LARANJA",
        fatores_principais=["s2id"],
        limit=4,
    )
    assert medidas
    for m in medidas:
        assert "fontes_financiamento" in m
        assert len(m["fontes_financiamento"]) >= 1
        for f in m["fontes_financiamento"]:
            assert f["id"] not in {"pro_cidades", "credito_uniao"}


def test_suggest_programs_capag_c_sem_credito_uniao():
    progs = suggest_programs(severidade="Crítica", nota_capag="C", media_ivc=0.7)
    ids = {p.get("id") for p in progs}
    assert "credito_uniao" not in ids
    assert "pro_cidades" not in ids
    assert "defesa_civil" in ids or "fundo_clima" in ids or "fcp" in ids


@patch("app.services.municipal_profile_service.compute_maturity")
@patch("app.services.municipal_profile_service._ensure_capag_fresh")
def test_build_municipal_profile(mock_capag, mock_maturity):
    muni = MagicMock()
    muni.codigo_ibge = "2611606"
    muni.nome = "Recife"
    muni.uf = "PE"
    muni.populacao = 1_488_920

    fiscal = MagicMock()
    fiscal.nota_capag = "B"
    fiscal.exec_defesa_civil = 1_200_000.0

    mock_capag.return_value = (
        fiscal,
        {
            "status": "ok",
            "nota": "B",
            "indicadores": [],
        },
    )
    mock_maturity.return_value = {
        "classificacao": "Ouro",
        "score": 72.0,
        "fontes": [{"id": "plano_diretor", "status": "OFICIAL"}],
    }

    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        name = str(model)
        if "Fiscal" in name:
            q.filter.return_value.first.return_value = fiscal
        else:
            q.filter.return_value.first.return_value = muni
        return q

    db.query.side_effect = query_side_effect

    perfil = build_municipal_profile(db, "2611606")
    assert perfil["porte"] == "metropole"
    assert perfil["porte_label"] == "Metrópole"
    assert perfil["capag"]["nota"] == "B"
    assert perfil["defesa_civil"]["tem_gasto_registrado"] is True
    assert perfil["plano_diretor"]["status"] == "OFICIAL"
    assert perfil["maturidade_tier"] == "Ouro"
