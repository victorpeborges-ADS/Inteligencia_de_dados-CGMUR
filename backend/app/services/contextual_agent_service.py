"""Agente Sinidu contextual — prompt dinâmico, ferramentas e streaming."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Iterator
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AlertaCemaden, HistoricoDesastreS2ID, Municipio
from app.services.contextual_agent_cache import (
    get_cached_bundle,
    get_cached_response,
    set_cached_bundle,
    set_cached_response,
)
from app.services.contextual_agent_tools import TOOL_DEFINITIONS, execute_tool
from app.services.municipio_audit_service import audit_municipio
from rag.providers.registry import resolve_chat_provider_with_fallback

logger = logging.getLogger(__name__)

CONTEXTUAL_AGENT_FAST_MODEL = os.getenv("CONTEXTUAL_AGENT_FAST_MODEL", "mistral-small-latest")
CONTEXTUAL_AGENT_MAX_TOOL_ROUNDS = int(os.getenv("CONTEXTUAL_AGENT_MAX_TOOL_ROUNDS", "2"))

_SIMPLE_QUESTION_RE = re.compile(
    r"(como usar|como interpretar|o que significa|o que é|explique|ajuda|como funciona|para que serve)",
    re.IGNORECASE,
)
_DATA_QUESTION_RE = re.compile(
    r"(alerta|bairro|score|dados|catálogo|catalogo|ivc|iri|desastre|cemaden|mapbiomas|pib|idh)",
    re.IGNORECASE,
)

SYSTEM_TEMPLATE = """Você é o Agente Sinidu+Clima, assistente especializado em inteligência territorial
e gestão de risco urbano para municípios brasileiros.

CONTEXTO ATUAL:
- Município em análise: {municipio_nome} ({cod_ibge}) — {uf}
- Módulo ativo: {pagina_atual}
- {descricao_pagina}

DADOS REAIS DO MUNICÍPIO (extraídos agora do sistema):
{dados_municipio_json}

DADOS DA PÁGINA ATUAL:
{dados_pagina_json}

REGRAS:
1. Responda SEMPRE em português brasileiro
2. Seja direto e objetivo — máximo 3 parágrafos por resposta
3. Quando citar números, use os dados reais acima (nunca invente valores)
4. Se não souber ou os dados não estiverem disponíveis, diga explicitamente
5. Para perguntas sobre "como usar": explique em passos simples
6. Para perguntas sobre "análise": interprete os dados do contexto acima
7. Sempre termine com uma sugestão de próxima ação quando relevante
8. Você tem conhecimento sobre: gestão de risco urbano, legislação COBRADE,
   indicadores de vulnerabilidade, finanças públicas municipais (LRF, CAPAG),
   Plano Diretor e legislação urbanística municipal, dados IBGE, MapBiomas,
   CEMADEN, S2ID, políticas MCID
8b. Sempre que falar de priorização, intervenções ou plano de ação, deixe claro
    que as recomendações Sinidu+Clima consideram o Plano Diretor do município
    em análise (quando houver fonte oficial cadastrada no perfil).
9. Use as ferramentas disponíveis quando precisar de dados atualizados não presentes no contexto
   (inclui get_exposicao_edificios para "quantos prédios/pessoas alagam/deslizam/esquentam"
   e explain_mancha_inundacao para "explique esta mancha / posso usar como laudo")
10. Quando dados locais estiverem ausentes ou parciais, use get_georedus_referencia e cite o GeoReDUS
    com o link municipioId retornado pela ferramenta. NUNCA invente valores do GeoReDUS — apenas
    oriente o gestor a consultar o catálogo nacional ReDUS como complemento ao Sinidu
11. HONESTIDADE METODOLÓGICA (obrigatório):
    - NÃO diga que a simulação Sinidu é "metodologia oficial", "homologada", "laudo",
      "HEC-RAS", "preciso como engenharia" ou "alerta oficial" sem qualificador.
    - Sempre que falar de simulação/mancha/predição, cite o selo (Oficial / Observado /
      Estimado / Derivado) quando existir no contexto.
    - Distinga: fontes oficiais de *entrada* (IBGE, CEMADEN, S2ID, MapBiomas) ≠
      resultado de *simulação* (em geral Derivado/Estimado — triagem, não laudo).
    - Predição ML só é "probabilidade" se model_kind=full; caso contrário diga "score heurístico".
    - Nunca diga que o Sinidu substitui alerta CEMADEN ou Defesa Civil.
12. NÍVEL DE ALERTA (obrigatório — contrato de tools):
    - Nunca invente VERDE/AMARELO/LARANJA/VERMELHO. Só cite nível se veio de
      get_alerta_vivo (ou get_alertas_cemaden) nesta conversa.
    - Se interpretacao=sem_alerta_monitorado ou sem_alerta_ativo_24h=true: diga
      "sem alerta monitorado nas últimas 24h", NÃO "município seguro" nem "status oficial VERDE".
    - Sem tool de alerta: diga que precisa consultar o Monitor / get_alerta_vivo.
13. Você é o modo Operacional do Agente Sinidu (dados do município + tools). Legislação/RAG
    normativo fica no modo Normativo (aba Assistente). Não ative plano nem dissemine alerta.
"""


def build_municipio_data_bundle(db: Session, muni: Municipio) -> dict[str, Any]:
    """Bundle leve para o prompt — evita executive_snapshot (IVC/IRI por bairro) a cada pergunta."""
    cached = get_cached_bundle(muni.codigo_ibge)
    if cached:
        return cached

    audit = audit_municipio(db, muni, persist=False)
    alerts_count = (
        db.query(func.count(AlertaCemaden.id))
        .filter(AlertaCemaden.municipio_id == muni.id)
        .scalar()
    ) or 0
    disasters_count = (
        db.query(func.count(HistoricoDesastreS2ID.id))
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .scalar()
    ) or 0
    area = float(muni.area_km2 or 0)
    bundle = {
        "codigo_ibge": muni.codigo_ibge,
        "nome": muni.nome,
        "uf": muni.uf,
        "populacao": muni.populacao,
        "area_km2": area,
        "densidade_demografica": round(muni.populacao / area, 2) if area > 0 else 0,
        "score_sinidu": audit.get("score_sinidu"),
        "score_confiabilidade": audit.get("score_confiabilidade"),
        "confiabilidade_geral": audit.get("confiabilidade_geral"),
        "campos_reais_pct": audit.get("campos_reais_pct"),
        "bairros_total": audit.get("bairros_total"),
        "malha_fonte": audit.get("malha_fonte"),
        "flag_malha": audit.get("flag_malha"),
        "alertas_ativos_count": int(alerts_count),
        "historico_desastres_count": int(disasters_count),
    }
    set_cached_bundle(muni.codigo_ibge, bundle)
    return bundle


def _is_simple_question(message: str) -> bool:
    if _SIMPLE_QUESTION_RE.search(message):
        return True
    return not _DATA_QUESTION_RE.search(message) and len(message.split()) <= 12


def _offline_contextual_reply(dados_municipio: dict[str, Any], message: str) -> str:
    """Resposta determinística quando o LLM não está configurado (demo/homolog)."""
    lower = message.lower()
    nome = dados_municipio.get("nome") or "município"
    uf = dados_municipio.get("uf") or ""
    label = f"{nome}/{uf}" if uf else str(nome)
    score = dados_municipio.get("score_sinidu")
    honesty = (
        " Lembrete: simulações Sinidu são triagem territorial (selo Derivado/Estimado) — "
        "não substituem laudo de engenharia nem alerta oficial CEMADEN/Defesa Civil."
    )
    if score is not None and ("score" in lower or "sinidu" in lower):
        return (
            f"No município de {label}, o **Score Sinidu+Clima** consolidado é **{score}** "
            "(escala 0–100). O índice agrega vulnerabilidade climática (IVC), risco de inundação (IRI) "
            "e capacidade de adaptação municipal. Consulte o painel executivo e a camada de vulnerabilidade "
            "para detalhar bairros críticos."
            + honesty
        )
    if any(k in lower for k in ("simula", "mancha", "alag", "inund", "calor", "chuva")):
        return (
            f"Para {label}, use a aba Simulações com o volume/cenário desejado e leia o "
            "**selo de confiança** e a **nota metodológica**. Resultado = estimativa para "
            "priorização e contingência — não é HEC-RAS, laudo nem alerta CEMADEN."
            + honesty
        )
    return (
        "O assistente contextual está em modo demonstração (MISTRAL_API_KEY não configurada no servidor). "
        "Use o painel, simulações e diagnóstico automático para explorar os indicadores do município."
        + honesty
    )


def _resolve_model(ai_model: str | None, provider: Any) -> str:
    if ai_model:
        return ai_model
    fast = CONTEXTUAL_AGENT_FAST_MODEL.strip()
    if fast and fast in (provider.info().models or []):
        return fast
    return provider.info().default_model


def _chat_without_tools(provider: Any, messages: list[dict[str, Any]], model: str) -> str:
    result = provider.chat_completion(messages, model=model, tools=None)
    choice = (result.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = (message.get("content") or "").strip()
    return content or "Não foi possível gerar uma resposta. Tente reformular a pergunta."


def _run_tool_loop(
    db: Session,
    provider: Any,
    messages: list[dict[str, Any]],
    model: str,
    *,
    max_rounds: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Executa chamadas de ferramenta até resposta final em texto."""
    rounds = max_rounds if max_rounds is not None else CONTEXTUAL_AGENT_MAX_TOOL_ROUNDS
    stats: dict[str, Any] = {"tool_calls": 0, "tool_errors": 0, "tools_used": []}
    for _ in range(rounds):
        result = provider.chat_completion(messages, model=model, tools=TOOL_DEFINITIONS)
        choice = (result.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            content = (message.get("content") or "").strip()
            if content:
                return content, stats
            return (
                "Não foi possível gerar uma resposta. Tente reformular a pergunta.",
                stats,
            )

        messages.append(message)
        for call in tool_calls:
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            tool_result = execute_tool(db, name, fn.get("arguments") or "{}")
            stats["tool_calls"] += 1
            if name:
                stats["tools_used"].append(name)
            if tool_result.get("error") or tool_result.get("error_code") in {
                "unknown_tool",
                "invalid_args",
                "tool_error",
            }:
                stats["tool_errors"] += 1
            messages.append(
                {
                    "role": "tool",
                    "name": name,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                    "tool_call_id": call.get("id") or name,
                }
            )

    return "Limite de consultas atingido. Resuma com os dados já obtidos.", stats


def contextual_chat_stream(
    db: Session,
    muni: Municipio,
    *,
    message: str,
    pagina_atual: str,
    descricao_pagina: str,
    dados_pagina: dict[str, Any] | None,
    historico: list[dict[str, str]],
    ai_provider: str | None = None,
    ai_model: str | None = None,
    ai_api_key: str | None = None,
) -> Iterator[str]:
    """Gera eventos SSE: token chunks + done metadata."""
    start = time.time()

    cached_answer = get_cached_response(muni.codigo_ibge, pagina_atual, message)
    if cached_answer and not historico:
        answer = str(cached_answer.get("response") or "")
        for word in answer.split(" "):
            yield _sse({"type": "token", "content": word + " "})
        elapsed = int((time.time() - start) * 1000)
        yield _sse(
            {
                "type": "done",
                "response": answer.strip(),
                "response_time_ms": elapsed,
                "ai_provider": cached_answer.get("ai_provider"),
                "ai_model": cached_answer.get("ai_model"),
                "from_cache": True,
            }
        )
        return

    dados_municipio = build_municipio_data_bundle(db, muni)
    system_content = SYSTEM_TEMPLATE.format(
        municipio_nome=muni.nome,
        cod_ibge=muni.codigo_ibge,
        uf=muni.uf,
        pagina_atual=pagina_atual,
        descricao_pagina=descricao_pagina,
        dados_municipio_json=json.dumps(dados_municipio, ensure_ascii=False, indent=2),
        dados_pagina_json=json.dumps(dados_pagina or {}, ensure_ascii=False, indent=2),
    )

    try:
        provider = resolve_chat_provider_with_fallback(ai_provider, api_key=ai_api_key)
    except (ValueError, RuntimeError) as exc:
        yield _sse({"type": "error", "content": str(exc)})
        yield _sse({"type": "done", "response": str(exc), "response_time_ms": 0})
        return

    model = _resolve_model(ai_model, provider)
    telemetry: dict[str, Any] = {
        "tool_calls": 0,
        "tool_errors": 0,
        "tools_used": [],
        "fallback_deterministic": False,
        "from_cache": False,
    }
    if not provider.is_available():
        answer = (
            _offline_contextual_reply(dados_municipio, message)
            if _is_simple_question(message)
            else "MISTRAL_API_KEY não configurada no servidor."
        )
        elapsed = int((time.time() - start) * 1000)
        telemetry["fallback_deterministic"] = True
        logger.info(
            "ai_telemetry contextual offline ibge=%s latency_ms=%s",
            muni.codigo_ibge,
            elapsed,
        )
        yield _sse(
            {
                "type": "done",
                "response": answer,
                "response_time_ms": elapsed,
                "ai_provider": None,
                **telemetry,
            }
        )
        return

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_content}]
    for item in historico[-6:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": message})

    try:
        if _is_simple_question(message):
            answer = _chat_without_tools(provider, messages, model)
        else:
            answer, tool_stats = _run_tool_loop(db, provider, messages, model)
            telemetry.update(tool_stats)
    except Exception as exc:
        logger.exception("Falha no agente contextual")
        answer = f"Erro ao processar: {exc}"
        telemetry["fallback_deterministic"] = True

    if not historico:
        set_cached_response(
            muni.codigo_ibge,
            pagina_atual,
            message,
            response=answer,
            ai_provider=provider.id,
            ai_model=model,
        )

    # Streaming simulado por palavras (API Mistral tool loop não streama nativamente)
    buffer = ""
    for word in answer.split(" "):
        chunk = (word + " ")
        buffer += chunk
        yield _sse({"type": "token", "content": chunk})

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "ai_telemetry contextual ibge=%s latency_ms=%s tools=%s errors=%s provider=%s",
        muni.codigo_ibge,
        elapsed,
        telemetry.get("tool_calls"),
        telemetry.get("tool_errors"),
        provider.id,
    )
    yield _sse(
        {
            "type": "done",
            "response": answer.strip(),
            "response_time_ms": elapsed,
            "ai_provider": provider.id,
            "ai_model": model,
            **telemetry,
        }
    )


def contextual_chat_sync(
    db: Session,
    muni: Municipio,
    *,
    message: str,
    pagina_atual: str,
    descricao_pagina: str,
    dados_pagina: dict[str, Any] | None,
    historico: list[dict[str, str]],
    ai_provider: str | None = None,
    ai_model: str | None = None,
    ai_api_key: str | None = None,
) -> dict[str, Any]:
    """Versão síncrona (fallback sem SSE)."""
    chunks: list[str] = []
    result: dict[str, Any] = {}
    for event in contextual_chat_stream(
        db,
        muni,
        message=message,
        pagina_atual=pagina_atual,
        descricao_pagina=descricao_pagina,
        dados_pagina=dados_pagina,
        historico=historico,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_api_key=ai_api_key,
    ):
        if event.startswith("data: "):
            payload = json.loads(event[6:].strip())
            if payload.get("type") == "token":
                chunks.append(payload.get("content") or "")
            elif payload.get("type") == "done":
                result = payload
    if not result:
        result = {"response": "".join(chunks), "response_time_ms": 0}
    return result


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
