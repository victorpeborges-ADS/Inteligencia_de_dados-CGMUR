"""Ferramentas de leitura para o Agente Sinidu contextual."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.data_catalog import coverage_for_code
from app.models import (
    AlertaCemaden,
    ContingencyPlan,
    HistoricoDesastreS2ID,
    MonitoringAlert,
    Municipio,
    PlanoAcaoMunicipal,
)
from app.services.action_plan_engine import action_plan_to_dict
from app.services.analytical_engine import AnalyticalEngine
from app.services.contingency_planner import plan_to_dict
from app.services.georedus_lst_service import get_lst_observada_config
from app.services.georedus_reference_service import build_georedus_referencia
from app.services.heat_simulator import run_heat_island_simulation
from app.services.lst_heat_comparator import compare_heat_simulation_with_lst
from app.services.live_alert_level import live_alert_snapshot
from app.services.maturity_engine import compute_maturity
from app.services.municipio_audit_service import audit_municipio
from app.services.report_generator import build_bairro_ranking


def get_score_municipio(db: Session, codigo_ibge: str) -> dict[str, Any]:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        return {"error": "Município não encontrado"}
    audit = audit_municipio(db, muni, persist=False)
    return {
        "codigo_ibge": codigo_ibge,
        "nome": muni.nome,
        "uf": muni.uf,
        "score_sinidu": audit.get("score_sinidu"),
        "score_confiabilidade": audit.get("score_confiabilidade"),
        "confiabilidade_geral": audit.get("confiabilidade_geral"),
        "campos_reais_pct": audit.get("campos_reais_pct"),
        "bairros_total": audit.get("bairros_total"),
        "nota": "Índices IVC/IRI por bairro: use o módulo Painel ou Simulações no Sinidu+Clima.",
    }


def get_alertas_cemaden(db: Session, codigo_ibge: str) -> dict[str, Any]:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        return {"error": "Município não encontrado"}
    since = datetime.utcnow() - timedelta(hours=24)
    alerts_db = (
        db.query(MonitoringAlert)
        .filter(MonitoringAlert.codigo_ibge == codigo_ibge, MonitoringAlert.created_at >= since)
        .order_by(MonitoringAlert.created_at.desc())
        .limit(30)
        .all()
    )
    cemaden_layer = (
        db.query(AlertaCemaden)
        .filter(AlertaCemaden.municipio_id == muni.id)
        .order_by(AlertaCemaden.data_referencia.desc())
        .limit(20)
        .all()
    )
    return {
        "codigo_ibge": codigo_ibge,
        "alertas_24h": len(alerts_db),
        "cemaden_ativos": len([a for a in alerts_db if a.tipo == "CEMADEN_ALERT"]),
        "nivel_maximo": max((a.nivel for a in alerts_db), default="VERDE"),
        "timeline": [
            {
                "tipo": a.tipo,
                "nivel": a.nivel,
                "titulo": a.titulo,
                "mensagem": (a.mensagem or "")[:200],
            }
            for a in alerts_db[:10]
        ],
        "camada_cemaden_count": len(cemaden_layer),
    }


def get_catalogo_dados(db: Session, codigo_ibge: str) -> dict[str, Any]:
    maturidade, bases, gaps = coverage_for_code(codigo_ibge, db)
    lacunas = [g.get("nome") or g.get("id") for g in gaps]
    georedus = build_georedus_referencia(db, codigo_ibge) if lacunas else {}
    return {
        "codigo_ibge": codigo_ibge,
        "maturidade_percentual": maturidade,
        "maturidade_tier": "Alta" if maturidade >= 75 else ("Media" if maturidade >= 50 else "Baixa"),
        "fontes": [
            {
                "id": f.get("id"),
                "nome": f.get("nome"),
                "status": f.get("status"),
            }
            for f in bases[:12]
        ],
        "lacunas": lacunas[:8],
        "georedus_url": georedus.get("georedus_url"),
        "georedus_indicadores": georedus.get("indicadores_sugeridos") or [],
    }


def get_georedus_referencia(
    db: Session,
    codigo_ibge: str,
    tema: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    return build_georedus_referencia(db, codigo_ibge, tema=tema, query=query)


def get_historico_desastres(db: Session, codigo_ibge: str) -> dict[str, Any]:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        return {"error": "Município não encontrado"}
    rows = (
        db.query(HistoricoDesastreS2ID)
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .order_by(HistoricoDesastreS2ID.ano.desc())
        .limit(15)
        .all()
    )
    total_danos = db.query(func.sum(HistoricoDesastreS2ID.danos_materiais)).filter(
        HistoricoDesastreS2ID.municipio_id == muni.id
    ).scalar()
    return {
        "codigo_ibge": codigo_ibge,
        "total_eventos": len(rows),
        "danos_materiais_total": float(total_danos or 0),
        "eventos": [
            {
                "ano": r.ano,
                "tipo": r.tipo_desastre,
                "danos_materiais": float(r.danos_materiais or 0),
            }
            for r in rows
        ],
    }


def get_bairros_criticos(db: Session, codigo_ibge: str, top_n: int = 5) -> dict[str, Any]:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        return {"error": "Município não encontrado"}
    ranking, _ = build_bairro_ranking(db, muni)
    top = ranking[: max(1, min(top_n, 10))]
    return {
        "codigo_ibge": codigo_ibge,
        "bairros": [
            {
                "bairro": r.get("bairro"),
                "score_sinidu": r.get("score_sinidu"),
                "ivc": r.get("ivc"),
                "iri": r.get("iri"),
            }
            for r in top
        ],
    }


def get_plano_acao(db: Session, codigo_ibge: str) -> dict[str, Any]:
    record = (
        db.query(PlanoAcaoMunicipal)
        .filter(PlanoAcaoMunicipal.codigo_ibge == codigo_ibge)
        .order_by(PlanoAcaoMunicipal.gerado_em.desc())
        .first()
    )
    if not record:
        return {"codigo_ibge": codigo_ibge, "disponivel": False, "mensagem": "Nenhum plano de ação gerado ainda."}
    payload = action_plan_to_dict(record)
    return {
        "codigo_ibge": codigo_ibge,
        "disponivel": True,
        "score_sinidu": payload.get("score_sinidu"),
        "acoes_curto_prazo": (payload.get("acoes_curto_prazo") or [])[:5],
        "acoes_medio_prazo": (payload.get("acoes_medio_prazo") or [])[:3],
        "acoes_longo_prazo": (payload.get("acoes_longo_prazo") or [])[:3],
    }


def get_simulacao_resultado(db: Session, codigo_ibge: str, precipitacao_mm: float = 120.0) -> dict[str, Any]:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        return {"error": "Município não encontrado"}
    try:
        result = AnalyticalEngine.run_chuva_extrema_simulation(db, muni.id, precipitacao_mm)
        summary = result.get("summary") or result
        return {
            "codigo_ibge": codigo_ibge,
            "precipitacao_mm": precipitacao_mm,
            "area_inundada_ha": summary.get("area_inundada_ha") or result.get("area_inundada_ha"),
            "bairros_afetados": summary.get("bairros_afetados") or result.get("bairros_afetados"),
            "profundidade_max_m": summary.get("profundidade_max_m") or result.get("profundidade_max_m"),
            "setores_criticos": summary.get("setores_criticos") or result.get("setores_criticos"),
        }
    except Exception as exc:
        return {"codigo_ibge": codigo_ibge, "error": str(exc)[:200]}


def get_plano_contingencia(db: Session, codigo_ibge: str) -> dict[str, Any]:
    """Plano de contingência municipal (evacuação, rotas, ações por nível)."""
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        return {"error": "Município não encontrado"}
    plan = (
        db.query(ContingencyPlan)
        .filter(ContingencyPlan.municipio_id == muni.id)
        .order_by(ContingencyPlan.updated_at.desc())
        .first()
    )
    if not plan:
        return {
            "codigo_ibge": codigo_ibge,
            "disponivel": False,
            "mensagem": "Nenhum plano de contingência cadastrado. Use o módulo Contingência para criar.",
        }
    payload = plan_to_dict(plan, muni)
    acoes = payload.get("acoes_por_nivel") or {}
    return {
        "codigo_ibge": codigo_ibge,
        "disponivel": True,
        "status": payload.get("status"),
        "cenario_tipo": payload.get("cenario_tipo"),
        "nivel_alerta": payload.get("nivel_alerta"),
        "versao": payload.get("versao"),
        "zonas_evacuacao_count": len(payload.get("zonas_evacuacao") or []),
        "rotas_fuga_count": len(payload.get("rotas_fuga") or []),
        "pontos_apoio_count": len(payload.get("pontos_apoio") or []),
        "contatos_defesa_civil": (payload.get("contatos_defesa_civil") or [])[:5],
        "acoes_resumo": {
            nivel: (itens[:3] if isinstance(itens, list) else itens)
            for nivel, itens in list(acoes.items())[:4]
        },
    }


def get_comparador_calor_lst(
    db: Session,
    codigo_ibge: str,
    temperatura_pico_c: float = 38.0,
) -> dict[str, Any]:
    """Compara simulação de ilha de calor Sinidu com LST observada (GeoReDUS)."""
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        return {"error": "Município não encontrado"}
    lst_cfg = get_lst_observada_config()
    try:
        sim = run_heat_island_simulation(
            db,
            muni.id,
            temperatura_pico_c=float(temperatura_pico_c),
        )
        cmp = compare_heat_simulation_with_lst(db, muni, sim, max_bairros=8)
        return {
            "codigo_ibge": codigo_ibge,
            "disponivel": bool(cmp.get("disponivel")),
            "lst_fonte": cmp.get("lst_fonte") or lst_cfg.get("source"),
            "lst_periodo": cmp.get("lst_periodo") or lst_cfg.get("periodo_mosaico"),
            "lst_mediana_c": cmp.get("lst_mediana_c"),
            "sim_temp_mediana_c": cmp.get("sim_temp_mediana_c"),
            "divergencia_mediana_c": cmp.get("divergencia_mediana_c"),
            "amostras_validas": cmp.get("amostras_validas"),
            "bairros": (cmp.get("bairros") or [])[:5],
            "narrativa": (cmp.get("narrativa") or "")[:500],
            "limites_metodologicos": cmp.get("limites_metodologicos"),
        }
    except Exception as exc:
        return {
            "codigo_ibge": codigo_ibge,
            "disponivel": False,
            "lst_fonte": lst_cfg.get("source"),
            "lst_periodo": lst_cfg.get("periodo_mosaico"),
            "mensagem": "Comparador indisponível agora; use o módulo Simulações → Calor / LST.",
            "error": str(exc)[:200],
        }


def get_maturidade_detalhe(db: Session, codigo_ibge: str) -> dict[str, Any]:
    """Score de maturidade informacional por fonte (IBGE, SICONFI, S2ID, etc.)."""
    try:
        result = compute_maturity(db, codigo_ibge)
    except Exception as exc:
        return {"codigo_ibge": codigo_ibge, "error": str(exc)[:200]}
    fontes = result.get("fontes") or []
    return {
        "codigo_ibge": result.get("codigo_ibge"),
        "nome": result.get("nome"),
        "uf": result.get("uf"),
        "score": result.get("score"),
        "completeness_score": result.get("completeness_score"),
        "classificacao": result.get("classificacao"),
        "resumo": result.get("resumo"),
        "fontes": [
            {
                "id": f.get("id"),
                "nome": f.get("nome"),
                "status": f.get("status"),
                "detail": f.get("detail"),
            }
            for f in fontes
        ],
        "fontes_faltantes": result.get("fontes_faltantes") or [],
        "fontes_parciais": result.get("fontes_parciais") or [],
    }


def get_alerta_vivo(db: Session, codigo_ibge: str) -> dict[str, Any]:
    """Nível CEMADEN/monitoramento das últimas 24h para contingência."""
    return live_alert_snapshot(db, codigo_ibge, hours=24)


def get_risco_alagamento_ml(
    db: Session,
    codigo_ibge: str,
    precip_24h: float = 80.0,
) -> dict[str, Any]:
    """Probabilidade de alagamento via modelo ML (baseline ou treinado)."""
    try:
        from ml.bootstrap import ensure_model_for
        from ml.predictor import predictor

        ensure_model_for(codigo_ibge, db)
        p24 = float(precip_24h)
        result = predictor.predict(
            db,
            codigo_ibge,
            p24,
            p24 * 1.4,
            p24 * 1.7,
        )
        return {
            "codigo_ibge": codigo_ibge,
            "precip_24h_mm": p24,
            "risk_probability": result.get("risk_probability"),
            "risk_level": result.get("risk_level"),
            "threshold_mm_24h": result.get("threshold_mm_24h"),
            "model_kind": result.get("model_kind") or result.get("model_version"),
            "disclaimer": (result.get("disclaimer") or "")[:280],
        }
    except Exception as exc:
        return {
            "codigo_ibge": codigo_ibge,
            "error": str(exc)[:200],
            "mensagem": "Modelo ML indisponível — use Bootstrap no painel Sistema ou simulação pluvial.",
        }


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_score_municipio",
            "description": "Retorna Score Sinidu, IVC, IRI e confiabilidade do município.",
            "parameters": {
                "type": "object",
                "properties": {"cod_ibge": {"type": "string", "description": "Código IBGE 7 dígitos"}},
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_alertas_cemaden",
            "description": "Lista alertas CEMADEN e monitoramento das últimas 24h.",
            "parameters": {
                "type": "object",
                "properties": {"cod_ibge": {"type": "string"}},
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_catalogo_dados",
            "description": "Maturidade informacional e status das fontes de dados.",
            "parameters": {
                "type": "object",
                "properties": {"cod_ibge": {"type": "string"}},
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_historico_desastres",
            "description": "Eventos S2ID dos últimos anos no município.",
            "parameters": {
                "type": "object",
                "properties": {"cod_ibge": {"type": "string"}},
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bairros_criticos",
            "description": "Bairros com maior score de risco territorial.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cod_ibge": {"type": "string"},
                    "top_n": {"type": "integer", "default": 5},
                },
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_plano_acao",
            "description": "Plano de ação municipal atual (curto/médio/longo prazo).",
            "parameters": {
                "type": "object",
                "properties": {"cod_ibge": {"type": "string"}},
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_simulacao_resultado",
            "description": "Resultado da simulação pluvial para uma precipitação em mm.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cod_ibge": {"type": "string"},
                    "precipitacao_mm": {"type": "number", "default": 120},
                },
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_georedus_referencia",
            "description": (
                "Referência externa GeoReDUS quando dados locais estão ausentes ou parciais. "
                "Retorna deep link municipioId e indicadores sugeridos — sem ingestão nacional."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cod_ibge": {"type": "string", "description": "Código IBGE 7 dígitos"},
                    "tema": {"type": "string", "description": "Tema da pergunta (ex.: saúde, educação)"},
                    "query": {"type": "string", "description": "Texto livre para casar indicadores GeoReDUS"},
                },
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_plano_contingencia",
            "description": (
                "Plano de contingência municipal: zonas de evacuação, rotas de fuga, "
                "pontos de apoio e ações por nível de alerta (CEMADEN)."
            ),
            "parameters": {
                "type": "object",
                "properties": {"cod_ibge": {"type": "string"}},
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_comparador_calor_lst",
            "description": (
                "Compara simulação de ilha de calor Sinidu com LST observada (GeoReDUS). "
                "Útil para perguntas sobre calor urbano, temperatura de superfície e divergência modelo×observado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cod_ibge": {"type": "string"},
                    "temperatura_pico_c": {
                        "type": "number",
                        "default": 38,
                        "description": "Temperatura de pico prevista (°C) para a simulação",
                    },
                },
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_maturidade_detalhe",
            "description": (
                "Maturidade informacional detalhada por fonte (IBGE, SICONFI, CAPAG, S2ID, "
                "MapBiomas, SNIS, bairros, plano diretor, clima) com score e classificação."
            ),
            "parameters": {
                "type": "object",
                "properties": {"cod_ibge": {"type": "string"}},
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_alerta_vivo",
            "description": (
                "Nível de alerta vivo (CEMADEN/monitoramento 24h) para pré-preencher contingência. "
                "Retorna VERDE/AMARELO/LARANJA/VERMELHO e contagens."
            ),
            "parameters": {
                "type": "object",
                "properties": {"cod_ibge": {"type": "string"}},
                "required": ["cod_ibge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_risco_alagamento_ml",
            "description": (
                "Probabilidade de alagamento pelo modelo ML Sinidu (Random Forest) "
                "para uma precipitação 24h em mm."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cod_ibge": {"type": "string"},
                    "precip_24h": {
                        "type": "number",
                        "default": 80,
                        "description": "Precipitação acumulada 24h em mm",
                    },
                },
                "required": ["cod_ibge"],
            },
        },
    },
]

_TOOL_DISPATCH = {
    "get_score_municipio": lambda db, args: get_score_municipio(db, args["cod_ibge"]),
    "get_alertas_cemaden": lambda db, args: get_alertas_cemaden(db, args["cod_ibge"]),
    "get_catalogo_dados": lambda db, args: get_catalogo_dados(db, args["cod_ibge"]),
    "get_historico_desastres": lambda db, args: get_historico_desastres(db, args["cod_ibge"]),
    "get_bairros_criticos": lambda db, args: get_bairros_criticos(db, args["cod_ibge"], int(args.get("top_n") or 5)),
    "get_plano_acao": lambda db, args: get_plano_acao(db, args["cod_ibge"]),
    "get_simulacao_resultado": lambda db, args: get_simulacao_resultado(
        db, args["cod_ibge"], float(args.get("precipitacao_mm") or 120)
    ),
    "get_georedus_referencia": lambda db, args: get_georedus_referencia(
        db,
        args["cod_ibge"],
        tema=args.get("tema"),
        query=args.get("query"),
    ),
    "get_plano_contingencia": lambda db, args: get_plano_contingencia(db, args["cod_ibge"]),
    "get_comparador_calor_lst": lambda db, args: get_comparador_calor_lst(
        db,
        args["cod_ibge"],
        float(args.get("temperatura_pico_c") or 38),
    ),
    "get_maturidade_detalhe": lambda db, args: get_maturidade_detalhe(db, args["cod_ibge"]),
    "get_alerta_vivo": lambda db, args: get_alerta_vivo(db, args["cod_ibge"]),
    "get_risco_alagamento_ml": lambda db, args: get_risco_alagamento_ml(
        db,
        args["cod_ibge"],
        float(args.get("precip_24h") or 80),
    ),
}


def execute_tool(db: Session, name: str, arguments: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            args = {}
    else:
        args = arguments
    fn = _TOOL_DISPATCH.get(name)
    if not fn:
        return {"error": f"Ferramenta desconhecida: {name}"}
    return fn(db, args)
