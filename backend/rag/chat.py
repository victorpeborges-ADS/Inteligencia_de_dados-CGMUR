from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app.assistant.siconfi_ia_bridge import answer_fiscal_question, detect_fiscal_intent
from app.models import Municipio
from rag.config import SYSTEM_PROMPT_TEMPLATE
from rag.providers.registry import resolve_chat_provider_with_fallback
from rag.retriever import retrieve
from rag.store import RetrievedChunk
from app.services.georedus_reference_service import detect_georedus_source_url
from app.services.municipal_assistant_context import (
    build_municipal_assistant_context,
    format_context_for_prompt,
    format_sources_for_response,
)

logger = logging.getLogger(__name__)


def _format_rag_context(chunks: List[RetrievedChunk]) -> str:
    if not chunks:
        return "Nenhum trecho documental recuperado."
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[{i}] Fonte: {chunk.source_label} (similaridade {chunk.similarity:.2f})\n{chunk.content[:1200]}"
        )
    return "\n\n".join(parts)


def _suggested_layer(query: str, response: str) -> Optional[str]:
    text = (query + " " + response).lower()
    if any(k in text for k in ["inunda", "alag", "enchente", "iri"]):
        return "inundacao"
    if any(k in text for k in ["vulnera", "ivc", "calor", "ilha"]):
        return "vulnerabilidade"
    if any(k in text for k in ["desastre", "s2id"]):
        return "desastres"
    if any(k in text for k in ["alerta", "cemaden"]):
        return "alertas"
    return None


def _unavailable_message(provider_label: str) -> str:
    return (
        f"O provedor **{provider_label}** não está disponível. "
        "Verifique se **MISTRAL_API_KEY** está configurada no servidor."
    )


class RagAssistant:
    def chat(
        self,
        db: Session,
        muni: Municipio,
        message: str,
        history: List[dict[str, str]],
        ai_provider: str | None = None,
        ai_model: str | None = None,
        ai_api_key: str | None = None,
    ) -> dict[str, Any]:
        start = time.time()

        if detect_fiscal_intent(message.lower()):
            fiscal = answer_fiscal_question(db, muni, message)
            try:
                ctx = build_municipal_assistant_context(db, muni)
            except Exception:
                logger.exception("Contexto municipal indisponível no ramo fiscal")
                ctx = {"suggested_questions": []}
            elapsed = int((time.time() - start) * 1000)
            return {
                "response": fiscal["response"],
                "source_url": fiscal["source_url"],
                "rag_sources": [],
                "municipal_sources": format_sources_for_response(ctx) if ctx else [],
                "suggested_questions": ctx.get("suggested_questions") or [],
                "response_time_ms": elapsed,
                "suggested_layer": None,
                "coordinates": None,
                "zoom": 12,
                "ai_provider": None,
                "ai_model": None,
            }

        try:
            provider = resolve_chat_provider_with_fallback(ai_provider, api_key=ai_api_key)
        except ValueError as exc:
            elapsed = int((time.time() - start) * 1000)
            return {
                "response": str(exc),
                "rag_sources": [],
                "municipal_sources": [],
                "suggested_questions": [],
                "response_time_ms": elapsed,
                "suggested_layer": None,
                "source_url": None,
                "coordinates": None,
                "zoom": 13,
                "ai_provider": ai_provider,
                "ai_model": ai_model,
            }

        model = ai_model or provider.info().default_model
        provider_info = provider.info()

        ctx = build_municipal_assistant_context(db, muni)
        chunks = retrieve(db, message, top_k=5)
        rag_context = _format_rag_context(chunks)
        municipal_context = format_context_for_prompt(ctx)

        system_content = SYSTEM_PROMPT_TEMPLATE.format(
            municipio_nome=f"{muni.nome} - {muni.uf}",
            rag_context=rag_context,
            municipal_context=municipal_context,
        )

        messages = [{"role": "system", "content": system_content}]
        for item in history[-8:]:
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                messages.append({"role": item["role"], "content": item["content"]})
        messages.append({"role": "user", "content": message})

        if not provider.is_available():
            elapsed = int((time.time() - start) * 1000)
            return {
                "response": _unavailable_message(provider_info.label),
                "rag_sources": [],
                "municipal_sources": format_sources_for_response(ctx),
                "suggested_questions": ctx.get("suggested_questions") or [],
                "response_time_ms": elapsed,
                "suggested_layer": _suggested_layer(message, ""),
                "source_url": None,
                "coordinates": None,
                "zoom": 13,
                "ai_provider": provider.id,
                "ai_model": model,
            }

        try:
            answer = provider.chat(messages, model=model)
            used_provider = provider
        except Exception as exc:
            logger.exception("Falha no provedor %s", provider.id)
            used_provider = provider
            answer = (
                f"Não foi possível gerar resposta via **{provider_info.label}**: {exc}. "
                "Verifique a configuração da API Mistral."
            )

        elapsed = int((time.time() - start) * 1000)
        rag_sources = [
            {
                "source": c.source,
                "source_label": c.source_label,
                "chunk_idx": c.chunk_idx,
                "content": c.content,
                "similarity": round(c.similarity, 3),
            }
            for c in chunks
        ]

        georedus_url = ctx.get("georedus_url")
        source_url = detect_georedus_source_url(message, answer, georedus_url)

        return {
            "response": answer,
            "rag_sources": rag_sources,
            "municipal_sources": format_sources_for_response(ctx),
            "suggested_questions": ctx.get("suggested_questions") or [],
            "response_time_ms": elapsed,
            "suggested_layer": _suggested_layer(message, answer),
            "source_url": source_url,
            "coordinates": None,
            "zoom": 13,
            "ai_provider": used_provider.id,
            "ai_model": model,
        }


rag_assistant = RagAssistant()
