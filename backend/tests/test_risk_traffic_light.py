"""Testes do painel de risco único (17h.1a / 17h.1b)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.risk_traffic_light_service import (
    _nivel_from_index,
    _nivel_from_score,
    _resolve_low_maturity,
    build_risk_panel,
)
from app.services.unified_risk_model import ml_prob_to_nivel


def test_ml_prob_to_nivel():
    assert ml_prob_to_nivel(0.8) == "VERMELHO"
    assert ml_prob_to_nivel(0.6) == "LARANJA"
    assert ml_prob_to_nivel(0.4) == "AMARELO"
    assert ml_prob_to_nivel(0.1) == "VERDE"
    assert ml_prob_to_nivel(None) == "VERDE"



def test_nivel_from_score_thresholds():
    assert _nivel_from_score(80) == "VERMELHO"
    assert _nivel_from_score(50) == "LARANJA"
    assert _nivel_from_score(35) == "AMARELO"
    assert _nivel_from_score(10) == "VERDE"
    assert _nivel_from_score(None) == "VERDE"


def test_nivel_from_index_thresholds():
    assert _nivel_from_index(0.8) == "VERMELHO"
    assert _nivel_from_index(0.5) == "LARANJA"
    assert _nivel_from_index(0.35) == "AMARELO"
    assert _nivel_from_index(0.1) == "VERDE"


def test_resolve_low_maturity_bronze():
    result = _resolve_low_maturity(
        maturity={"classificacao": "Bronze", "score": 18},
        coverage_classificacao="Alta",
        coverage_pct=80,
        onboarding_status="concluido",
    )
    assert result["ativo"] is True
    assert "Maturidade" in result["motivos"][0]
    assert "bootstrap" in result["aviso"].lower()


def test_resolve_low_maturity_ok():
    result = _resolve_low_maturity(
        maturity={"classificacao": "Prata", "score": 40},
        coverage_classificacao="Media",
        coverage_pct=55,
        onboarding_status="concluido",
    )
    assert result["ativo"] is False
    assert result["aviso"] == ""


@patch("app.services.risk_traffic_light_service.recommend_measures")
@patch("app.services.risk_traffic_light_service.build_municipal_profile")
@patch("app.services.risk_traffic_light_service.coverage_for_code")
@patch("app.services.risk_traffic_light_service.compute_maturity")
@patch("app.services.risk_traffic_light_service.live_alert_snapshot")
@patch("app.services.risk_traffic_light_service._avg_vm")
@patch("app.services.risk_traffic_light_service.build_bairro_ranking")
def test_build_risk_panel_consolidates_status(
    mock_ranking,
    mock_vm,
    mock_alerta,
    mock_maturity,
    mock_coverage,
    mock_perfil,
    mock_medidas,
):
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    muni.nome = "Recife"
    muni.uf = "PE"

    mock_ranking.return_value = (
        [
            {
                "bairro": "Boa Vista",
                "bairro_id": 11,
                "score_sinidu": 72,
                "ivc": 0.7,
                "iri": 0.6,
                "componentes": {},
                "fatores": [
                    {"id": "renda", "nome": "Estresse de renda", "contribuicao": 12.0},
                    {"id": "impermeabilizacao", "nome": "Impermeabilização", "contribuicao": 10.0},
                ],
                "fatores_principais": ["renda", "impermeabilizacao"],
                "populacao": 12000,
            },
            {
                "bairro": "Sancho",
                "bairro_id": 12,
                "score_sinidu": 40,
                "ivc": 0.4,
                "iri": 0.35,
                "componentes": {},
                "fatores": [],
                "fatores_principais": [],
                "populacao": 8000,
            },
        ],
        {
            "score_sinidu": 52,
            "media_ivc": 0.43,
            "media_iri": 0.46,
            "media_adaptacao": 0.4,
            "alertas_ativos_count": 2,
            "historico_desastres_count": 9,
            "populacao": 1500000,
        },
    )
    mock_vm.return_value = (0.51, 12)
    mock_alerta.return_value = {
        "nivel_alerta": "AMARELO",
        "cemaden_ativos_24h": 1,
        "alertas_total_24h": 2,
        "fonte": "cemaden",
        "titulo_recente": "Alerta hidrológico",
        "vivo": True,
    }
    mock_maturity.return_value = {
        "classificacao": "Prata",
        "score": 42.0,
    }
    mock_coverage.return_value = (62, [], [])
    mock_perfil.return_value = {
        "porte": "metropole",
        "porte_label": "Metrópole",
        "capag": {"nota": "B", "interpretacao": "ok"},
        "plano_diretor": {"status": "OFICIAL", "fontes_cadastradas": 1},
        "defesa_civil": {"sinal": "presente", "tem_gasto_registrado": True},
        "restricoes": [],
    }
    mock_medidas.return_value = [
        {
            "id": "microdrenagem",
            "titulo": "Desobstrução",
            "descricao": "Limpeza",
            "custo": "Médio",
            "horizonte": "Curto prazo",
            "prioridade": "Alta",
            "orgao": "Obras",
            "fonte": "teste",
            "tipo_risco": "inundacao",
            "bairros_alvo": ["Boa Vista"],
            "motivo": "Risco LARANJA",
        }
    ]

    db = MagicMock()
    seed = MagicMock()
    seed.onboarding_status = "concluido"
    b1 = MagicMock()
    b1.id = 11
    b1.municipio_id = 1
    b1.pop_censo2022 = 12000
    b1.geom = object()
    b2 = MagicMock()
    b2.id = 12
    b2.municipio_id = 1
    b2.pop_censo2022 = 8000
    b2.geom = object()

    def query_side_effect(model):
        q = MagicMock()
        name = getattr(model, "__name__", str(model))
        if "MunicipioSeed" in name or "Seed" in str(model):
            q.filter.return_value.first.return_value = seed
        elif "Bairro" in name:
            q.filter.return_value.all.return_value = [b1, b2]
        elif "Escola" in name or "Saude" in name or "Territorio" in name:
            q.filter.return_value.all.return_value = []
        else:
            q.filter.return_value.first.return_value = muni
        return q

    db.query.side_effect = query_side_effect

    panel = build_risk_panel(db, "2611606", top_bairros=5)

    assert panel["codigo_ibge"] == "2611606"
    assert panel["status"] in ("VERDE", "AMARELO", "LARANJA", "VERMELHO")
    # Score 52 → LARANJA; alerta AMARELO → status final LARANJA (max)
    assert panel["status"] == "LARANJA"
    assert panel["status_label"] == "Elevado"
    assert panel["componentes"]["score"]["valor"] == 52
    assert panel["componentes"]["alerta"]["nivel"] == "AMARELO"
    assert panel["componentes"]["vm"]["valor"] == 0.51
    assert len(panel["bairros"]) == 2
    assert panel["bairros"][0]["bairro"] == "Boa Vista"
    assert panel["bairros"][0]["nivel"] == "VERMELHO"
    assert panel["bairros"][0]["fatores_principais"] == ["renda", "impermeabilizacao"]
    assert panel["bairros"][0]["exposicao"]["populacao"] == 12000
    assert panel["exposicao_resumo"]["bairros_criticos"] == 1  # só Boa Vista >= 45
    assert panel["modo_baixa_maturidade"]["ativo"] is False
    assert panel["perfil"]["porte"] == "metropole"
    assert len(panel["medidas_recomendadas"]) == 1
    assert panel["ciclo"] == "agir"
    assert panel["versao"] == "21f.5"
    assert "ml_preditivo" in panel["componentes"]
    assert panel["modelo_risco"]["versao"] == "21f.5+21f.2"
    assert "ml_preditivo" in panel["modelo_risco"]["regra_status"]
    assert "ranking_bairros" in panel["modelo_risco"]



@patch("app.services.risk_traffic_light_service.recommend_measures")
@patch("app.services.risk_traffic_light_service.build_municipal_profile")
@patch("app.services.risk_traffic_light_service.coverage_for_code")
@patch("app.services.risk_traffic_light_service.compute_maturity")
@patch("app.services.risk_traffic_light_service.live_alert_snapshot")
@patch("app.services.risk_traffic_light_service._avg_vm")
@patch("app.services.risk_traffic_light_service.build_bairro_ranking")
def test_build_risk_panel_baixa_maturidade(
    mock_ranking,
    mock_vm,
    mock_alerta,
    mock_maturity,
    mock_coverage,
    mock_perfil,
    mock_medidas,
):
    muni = MagicMock()
    muni.id = 2
    muni.codigo_ibge = "1400233"
    muni.nome = "Caroebe"
    muni.uf = "RR"

    mock_ranking.return_value = (
        [],
        {"score_sinidu": 20, "media_ivc": 0.2, "media_iri": 0.2, "media_adaptacao": 0.5},
    )
    mock_vm.return_value = (None, 0)
    mock_alerta.return_value = {
        "nivel_alerta": "VERDE",
        "cemaden_ativos_24h": 0,
        "alertas_total_24h": 0,
        "fonte": "monitoramento",
        "titulo_recente": None,
        "vivo": False,
    }
    mock_maturity.return_value = {"classificacao": "Bronze", "score": 12.0}
    mock_coverage.return_value = (30, [], [])
    mock_perfil.return_value = {
        "porte": "pequeno",
        "porte_label": "Pequeno",
        "capag": {"nota": "D", "interpretacao": "limitada"},
        "plano_diretor": {"status": "LACUNA", "fontes_cadastradas": 0},
        "defesa_civil": {"sinal": "desconhecido", "tem_gasto_registrado": False},
        "restricoes": ["CAPAG D"],
    }
    mock_medidas.return_value = []

    db = MagicMock()
    seed = MagicMock()
    seed.onboarding_status = "pendente"

    def query_side_effect(model):
        q = MagicMock()
        name = str(model)
        if "Seed" in name:
            q.filter.return_value.first.return_value = seed
        elif "Bairro" in name:
            q.filter.return_value.all.return_value = []
        else:
            q.filter.return_value.first.return_value = muni
        return q

    db.query.side_effect = query_side_effect

    panel = build_risk_panel(db, "1400233")
    assert panel["modo_baixa_maturidade"]["ativo"] is True
    assert panel["modo_baixa_maturidade"]["aviso"]
    assert panel["status"] == "VERDE"
    assert panel["perfil"]["porte"] == "pequeno"
