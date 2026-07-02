from __future__ import annotations

import time
from typing import Dict, List

from rag.config import (
    AI_ALLOWED_PROVIDERS,
    AI_CHAT_PROVIDER,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_CHAT_MODEL,
    MISTRAL_API_KEY,
    MISTRAL_BASE_URL,
    MISTRAL_CHAT_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_CHAT_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_CHAT_MODEL,
)
from rag.providers.anthropic import AnthropicProvider
from rag.providers.base import ChatProvider, ProviderInfo
from rag.providers.gemini import GeminiProvider
from rag.providers.ollama import OllamaChatProvider
from rag.providers.openai_compatible import OpenAICompatibleProvider

_PROVIDERS: Dict[str, ChatProvider] = {
    "ollama": OllamaChatProvider(),
    "openai": OpenAICompatibleProvider(
        provider_id="openai",
        label="OpenAI",
        description="GPT via API OpenAI.",
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        default_model=OPENAI_CHAT_MODEL,
        models=[OPENAI_CHAT_MODEL, "gpt-4o", "gpt-4o-mini", "gpt-4.1-mini"],
    ),
    "openrouter": OpenAICompatibleProvider(
        provider_id="openrouter",
        label="OpenRouter",
        description="Agregador com centenas de modelos (Claude, Llama, Mistral…).",
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        default_model=OPENROUTER_CHAT_MODEL,
        models=[
            OPENROUTER_CHAT_MODEL,
            "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.3-70b-instruct",
            "google/gemini-2.0-flash-001",
        ],
        extra_headers={"HTTP-Referer": "https://sinidu-clima.local", "X-Title": "Sinidu+Clima"},
    ),
    "groq": OpenAICompatibleProvider(
        provider_id="groq",
        label="Groq",
        description="Inferência rápida em nuvem (Llama, Mixtral…).",
        api_key=GROQ_API_KEY,
        base_url=GROQ_BASE_URL,
        default_model=GROQ_CHAT_MODEL,
        models=[GROQ_CHAT_MODEL, "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
    ),
    "mistral": OpenAICompatibleProvider(
        provider_id="mistral",
        label="Mistral AI",
        description="Modelos Mistral via API oficial (Large, Small, Nemo).",
        api_key=MISTRAL_API_KEY,
        base_url=MISTRAL_BASE_URL,
        default_model=MISTRAL_CHAT_MODEL,
        models=[
            MISTRAL_CHAT_MODEL,
            "mistral-large-latest",
            "mistral-small-latest",
            "open-mistral-nemo",
            "ministral-8b-latest",
        ],
    ),
    "anthropic": AnthropicProvider(),
    "gemini": GeminiProvider(),
}


def _apply_api_key(provider: ChatProvider, api_key: str | None) -> ChatProvider:
    if api_key and api_key.strip():
        return provider.with_api_key(api_key.strip())
    return provider


def _allowed_provider_ids() -> list[str]:
    allowed = [p for p in AI_ALLOWED_PROVIDERS if p in _PROVIDERS]
    return allowed or ["mistral"]


def list_chat_providers(api_keys: Dict[str, str] | None = None) -> List[ProviderInfo]:
    keys = api_keys or {}
    result: List[ProviderInfo] = []
    for provider_id in _allowed_provider_ids():
        provider = _PROVIDERS[provider_id]
        bound = _apply_api_key(provider, keys.get(provider_id))
        result.append(bound.info())
    return result


def get_chat_provider(provider_id: str | None = None, api_key: str | None = None) -> ChatProvider:
    chosen = (provider_id or AI_CHAT_PROVIDER or "mistral").strip().lower()
    allowed = _allowed_provider_ids()
    if chosen not in allowed:
        raise ValueError(f"Provedor de IA não permitido: {chosen}. Permitidos: {', '.join(allowed)}")
    if chosen not in _PROVIDERS:
        raise ValueError(f"Provedor de IA desconhecido: {chosen}")
    return _apply_api_key(_PROVIDERS[chosen], api_key)


def _provider_configured(provider_id: str) -> bool:
    if provider_id not in _PROVIDERS:
        return False
    return _PROVIDERS[provider_id].is_available()


def default_chat_provider_id() -> str:
    """Somente Mistral (ou primeiro provedor permitido configurado)."""
    for candidate in _allowed_provider_ids():
        if _provider_configured(candidate):
            return candidate
    return _allowed_provider_ids()[0]


def resolve_chat_provider_with_fallback(
    provider_id: str | None = None,
    api_key: str | None = None,
) -> ChatProvider:
    """Resolve provedor Mistral — sem fallback para Ollama/Gemini."""
    preferred = (provider_id or default_chat_provider_id() or "mistral").strip().lower()
    provider = get_chat_provider(preferred, api_key)
    if not provider.is_available():
        raise RuntimeError(
            "Mistral AI não está configurado. Defina MISTRAL_API_KEY no ambiente."
        )
    return provider


def test_chat_provider(
    provider_id: str,
    api_key: str | None = None,
    model: str | None = None,
) -> dict:
    """Ping mínimo ao LLM para validar credenciais."""
    provider = get_chat_provider(provider_id, api_key)
    info = provider.info()
    if not provider.is_available():
        return {
            "ok": False,
            "message": "Informe uma API key válida para este provedor.",
            "response_time_ms": 0,
            "sample_response": None,
        }

    test_model = model or info.default_model
    messages = [{"role": "user", "content": "Responda apenas com a palavra OK."}]
    start = time.time()
    try:
        sample = provider.chat(messages, model=test_model, temperature=0)
        elapsed = int((time.time() - start) * 1000)
        return {
            "ok": True,
            "message": f"Conectado a {info.label} ({test_model}).",
            "response_time_ms": elapsed,
            "sample_response": sample[:120],
        }
    except Exception as exc:
        elapsed = int((time.time() - start) * 1000)
        return {
            "ok": False,
            "message": str(exc),
            "response_time_ms": elapsed,
            "sample_response": None,
        }
