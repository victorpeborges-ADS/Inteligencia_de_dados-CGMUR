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
   dados IBGE, MapBiomas, CEMADEN, S2ID, políticas MCID
9. Use as ferramentas disponíveis quando precisar de dados atualizados não presentes no contexto
   (inclui get_exposicao_edificios para "quantos prédios/pessoas alagam/deslizam/esquentam")
10. Quando dados locais estiverem ausentes ou parciais, use get_georedus_referencia e cite o GeoReDUS
    com o link municipioId retornado pela ferramenta. NUNCA invente valores do GeoReDUS — apenas
    oriente o gestor a consultar o catálogo nacional ReDUS como complemento ao Sinidu
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
    if score is not None and ("score" in lower or "sinidu" in lower):
        return (
            f"No município de {label}, o **Score Sinidu+Clima** consolidado é **{score}** "
            "(escala 0–100). O índice agrega vulnerabilidade climática (IVC), risco de inundação (IRI) "
            "e capacidade de adaptação municipal. Consulte o painel executivo e a camada de vulnerabilidade "
            "para detalhar bairros críticos."
        )
    return (
        "O assistente contextual está em modo demonstração (MISTRAL_API_KEY não configurada no servidor). "
        "Use o painel, simulações e diagnóstico automático para explorar os indicadores do município."
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
) -> str:
    """Executa chamadas de ferramenta até resposta final em texto."""
    rounds = max_rounds if max_rounds is not None else CONTEXTUAL_AGENT_MAX_TOOL_ROUNDS
    for _ in range(rounds):
        result = provider.chat_completion(messages, model=model, tools=TOOL_DEFINITIONS)
        choice = (result.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            content = (message.get("content") or "").strip()
            if content:
                return content
            return "Não foi possível gerar uma resposta. Tente reformular a pergunta."

        messages.append(message)
        for call in tool_calls:
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            tool_result = execute_tool(db, name, fn.get("arguments") or "{}")
            messages.append(
                {
                    "role": "tool",
                    "name": name,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                    "tool_call_id": call.get("id") or name,
                }
            )

    return "Limite de consultas atingido. Resuma com os dados já obtidos."


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
    if not provider.is_available():
        answer = (
            _offline_contextual_reply(dados_municipio, message)
            if _is_simple_question(message)
            else "MISTRAL_API_KEY não configurada no servidor."
        )
        elapsed = int((time.time() - start) * 1000)
        yield _sse({"type": "done", "response": answer, "response_time_ms": elapsed, "ai_provider": None})
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
            answer = _run_tool_loop(db, provider, messages, model)
    except Exception as exc:
        logger.exception("Falha no agente contextual")
        answer = f"Erro ao processar: {exc}"

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
    yield _sse(
        {
            "type": "done",
            "response": answer.strip(),
            "response_time_ms": elapsed,
            "ai_provider": provider.id,
            "ai_model": model,
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
