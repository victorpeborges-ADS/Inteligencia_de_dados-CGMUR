"""Agente Sinidu contextual — prompt dinâmico, ferramentas e streaming."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from typing import Any

from sqlalchemy.orm import Session

from app.api.analytics import executive_snapshot
from app.models import Municipio
from app.services.contextual_agent_tools import TOOL_DEFINITIONS, execute_tool
from app.services.municipio_audit_service import audit_municipio
from rag.providers.registry import resolve_chat_provider_with_fallback

logger = logging.getLogger(__name__)

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
10. Quando dados locais estiverem ausentes ou parciais, use get_georedus_referencia e cite o GeoReDUS
    com o link municipioId retornado pela ferramenta. NUNCA invente valores do GeoReDUS — apenas
    oriente o gestor a consultar o catálogo nacional ReDUS como complemento ao Sinidu
"""


def build_municipio_data_bundle(db: Session, muni: Municipio) -> dict[str, Any]:
    snap = executive_snapshot(db, muni)
    audit = audit_municipio(db, muni, persist=False)
    return {
        **snap,
        "score_confiabilidade": audit.get("score_confiabilidade"),
        "confiabilidade_geral": audit.get("confiabilidade_geral"),
        "campos_reais_pct": (audit.get("score") or {}).get("campos_reais_pct"),
        "malha_nivel": audit.get("malha", {}).get("nivel"),
        "bairros_count": audit.get("malha", {}).get("bairros_count"),
    }


def _run_tool_loop(
    db: Session,
    provider: Any,
    messages: list[dict[str, Any]],
    model: str,
    *,
    max_rounds: int = 4,
) -> str:
    """Executa chamadas de ferramenta até resposta final em texto."""
    for _ in range(max_rounds):
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
    except ValueError as exc:
        yield _sse({"type": "error", "content": str(exc)})
        yield _sse({"type": "done", "response": str(exc), "response_time_ms": 0})
        return

    model = ai_model or provider.info().default_model
    if not provider.is_available():
        msg = "MISTRAL_API_KEY não configurada no servidor."
        yield _sse({"type": "error", "content": msg})
        yield _sse({"type": "done", "response": msg, "response_time_ms": 0})
        return

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_content}]
    for item in historico[-10:]:
        if item.get("role") in {"user", "assistant"} and item.get("content"):
            messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": message})

    try:
        answer = _run_tool_loop(db, provider, messages, model)
    except Exception as exc:
        logger.exception("Falha no agente contextual")
        answer = f"Erro ao processar: {exc}"

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
