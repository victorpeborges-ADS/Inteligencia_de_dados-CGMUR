"""Testes do agente contextual."""

from unittest.mock import MagicMock, patch

from app.services.contextual_agent_tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    get_georedus_referencia,
    get_score_municipio,
)


def test_tool_definitions_count():
    assert len(TOOL_DEFINITIONS) == 15
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert "get_bairros_criticos" in names
    assert "get_score_municipio" in names
    assert "get_georedus_referencia" in names
    assert "get_plano_contingencia" in names
    assert "get_comparador_calor_lst" in names
    assert "get_maturidade_detalhe" in names
    assert "get_alerta_vivo" in names
    assert "get_risco_alagamento_ml" in names
    assert "get_exposicao_edificios" in names
    assert "recommend_cruzamento_camadas" in names


def test_execute_tool_unknown():
    db = MagicMock()
    result = execute_tool(db, "tool_inexistente", {})
    assert "error" in result


@patch("app.services.contextual_agent_tools.audit_municipio")
def test_get_score_municipio(mock_audit):
    db = MagicMock()
    muni = MagicMock()
    muni.nome = "Recife"
    muni.uf = "PE"
    db.query.return_value.filter.return_value.first.return_value = muni
    mock_audit.return_value = {
        "score_sinidu": 53,
        "score_confiabilidade": "MEDIA",
        "confiabilidade_geral": "MEDIA",
        "campos_reais_pct": 55,
        "bairros_total": 10,
    }

    out = get_score_municipio(db, "2611606")
    assert out["score_sinidu"] == 53
    assert out["score_confiabilidade"] == "MEDIA"
    assert out["campos_reais_pct"] == 55


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


@patch("app.services.contextual_agent_tools.plan_to_dict")
def test_get_plano_contingencia(mock_plan):
    from app.models import ContingencyPlan, Municipio
    from app.services.contextual_agent_tools import get_plano_contingencia

    db = MagicMock()
    muni = MagicMock(id=1, codigo_ibge="2611606", nome="Recife")
    plan = MagicMock()

    def _query(model):
        q = MagicMock()
        if model is Municipio:
            q.filter.return_value.first.return_value = muni
        elif model is ContingencyPlan:
            q.filter.return_value.order_by.return_value.first.return_value = plan
        return q

    db.query.side_effect = _query
    mock_plan.return_value = {
        "status": "ATIVO",
        "cenario_tipo": "INUNDACAO",
        "nivel_alerta": "AMARELO",
        "versao": 2,
        "zonas_evacuacao": [{}, {}],
        "rotas_fuga": [{}],
        "pontos_apoio": [{}, {}, {}],
        "contatos_defesa_civil": [{"nome": "DC"}],
        "acoes_por_nivel": {"AMARELO": ["ativar sirenes", "abrir abrigos", "extra"]},
    }
    out = get_plano_contingencia(db, "2611606")
    assert out["disponivel"] is True
    assert out["zonas_evacuacao_count"] == 2
    assert out["nivel_alerta"] == "AMARELO"


@patch("app.services.contextual_agent_tools.compute_maturity")
def test_get_maturidade_detalhe(mock_mat):
    from app.services.contextual_agent_tools import get_maturidade_detalhe

    mock_mat.return_value = {
        "codigo_ibge": "2611606",
        "nome": "Recife",
        "uf": "PE",
        "score": 62.0,
        "completeness_score": 70.0,
        "classificacao": "Ouro",
        "resumo": "ok",
        "fontes": [{"id": "ibge", "nome": "IBGE", "status": "OFICIAL", "detail": "pop"}],
        "fontes_faltantes": [],
        "fontes_parciais": [],
    }
    out = get_maturidade_detalhe(MagicMock(), "2611606")
    assert out["classificacao"] == "Ouro"
    assert out["fontes"][0]["id"] == "ibge"


@patch("app.services.contextual_agent_tools.live_alert_snapshot")
def test_get_alerta_vivo(mock_snap):
    from app.services.contextual_agent_tools import get_alerta_vivo

    mock_snap.return_value = {
        "codigo_ibge": "2611606",
        "nivel_alerta": "LARANJA",
        "vivo": True,
        "cemaden_ativos_24h": 2,
    }
    out = get_alerta_vivo(MagicMock(), "2611606")
    assert out["nivel_alerta"] == "LARANJA"
    mock_snap.assert_called_once()


@patch("ml.predictor.predictor.predict")
@patch("ml.bootstrap.ensure_model_for", return_value=True)
def test_get_risco_alagamento_ml(mock_ensure, mock_predict):
    from app.services.contextual_agent_tools import get_risco_alagamento_ml

    mock_predict.return_value = {
        "risk_probability": 0.72,
        "risk_level": "ALTO",
        "threshold_mm_24h": 65.0,
        "model_kind": "baseline_synthetic",
        "disclaimer": "demo",
    }
    out = get_risco_alagamento_ml(MagicMock(), "2611606", precip_24h=90)
    assert out["risk_level"] == "ALTO"
    assert out["precip_24h_mm"] == 90.0
    mock_ensure.assert_called_once()


@patch("app.services.contextual_agent_tools.compare_heat_simulation_with_lst")
@patch("app.services.contextual_agent_tools.run_heat_island_simulation")
@patch(
    "app.services.contextual_agent_tools.get_lst_observada_config",
    return_value={"source": "GeoReDUS", "periodo_mosaico": "2020-2024"},
)
def test_get_comparador_calor_lst(mock_cfg, mock_sim, mock_cmp):
    from app.services.contextual_agent_tools import get_comparador_calor_lst

    db = MagicMock()
    muni = MagicMock(id=1, codigo_ibge="2611606", nome="Recife")
    db.query.return_value.filter.return_value.first.return_value = muni
    mock_sim.return_value = {"ok": True}
    mock_cmp.return_value = {
        "disponivel": True,
        "lst_fonte": "GeoReDUS",
        "lst_periodo": "2020-2024",
        "lst_mediana_c": 34.0,
        "sim_temp_mediana_c": 37.0,
        "divergencia_mediana_c": 3.0,
        "amostras_validas": 5,
        "bairros": [{"bairro": "Centro"}],
        "narrativa": "Comparação LST × simulação.",
        "limites_metodologicos": ["LST ≠ ar"],
    }
    out = get_comparador_calor_lst(db, "2611606", temperatura_pico_c=40)
    assert out["disponivel"] is True
    assert out["divergencia_mediana_c"] == 3.0
    mock_sim.assert_called_once()


@patch("app.services.contextual_agent_tools.AnalyticalEngine.run_chuva_extrema_simulation")
def test_get_exposicao_edificios_inundacao(mock_sim):
    from app.services.contextual_agent_tools import get_exposicao_edificios, execute_tool

    db = MagicMock()
    muni = MagicMock(id=1, codigo_ibge="2611606", nome="Recife", uf="PE")
    db.query.return_value.filter.return_value.first.return_value = muni
    mock_sim.return_value = {
        "affected_population": 1200,
        "affected_bairros": ["Boa Viagem", "Centro"],
        "simulation_meta": {
            "exposicao_cenario": {
                "disponivel": True,
                "edificios_total": 100,
                "edificios_expostos": 12,
                "por_faixa": {"superficial": 2, "moderada": 5, "critica": 5},
                "populacao_edificios_estimada": 340,
                "escolas_expostas": {"n": 1},
                "saude_exposta": {"n": 0},
                "amostra": [
                    {"id": 1, "nome": "Torre A", "depth_band": "critica", "depth_m": 1.1, "altura_m": 24, "populacao_estimada": 40},
                ],
            },
            "exposicao_deslizamento": {
                "disponivel": True,
                "edificios_total": 100,
                "edificios_expostos": 3,
                "por_faixa": {"moderada": 1, "alta": 2, "critica": 0},
                "populacao_edificios_estimada": 55,
                "slope_threshold_deg": 22.0,
                "amostra": [],
            },
        },
    }

    out = get_exposicao_edificios(db, "2611606", tipo="inundacao", precipitacao_mm=120)
    assert out["tipo"] == "inundacao"
    assert out["inundacao"]["edificios_expostos"] == 12
    assert out["inundacao"]["populacao_edificios_estimada"] == 340
    assert out["inundacao"]["amostra"][0]["nome"] == "Torre A"

    via_dispatch = execute_tool(
        db,
        "get_exposicao_edificios",
        {"cod_ibge": "2611606", "tipo": "todos", "precipitacao_mm": 100},
    )
    assert via_dispatch["deslizamento"]["edificios_expostos"] == 3
