from __future__ import annotations

import logging
from typing import List

import httpx

from rag.providers.base import ProviderInfo

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    """OpenAI, OpenRouter, Groq e outros endpoints compatíveis com /chat/completions."""

    def __init__(
        self,
        provider_id: str,
        label: str,
        description: str,
        api_key: str,
        base_url: str,
        default_model: str,
        models: List[str],
        extra_headers: dict[str, str] | None = None,
    ):
        self.id = provider_id
        self.label = label
        self.is_local = False
        self._description = description
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._models = models
        self._extra_headers = extra_headers or {}

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            label=self.label,
            description=self._description,
            available=self.is_available(),
            is_local=False,
            requires_api_key=True,
            default_model=self._default_model,
            models=self._models,
            privacy_note="O contexto RAG e dados municipais são enviados ao provedor externo.",
        )

    def is_available(self) -> bool:
        return bool(self._api_key)

    def chat(
        self,
        messages: List[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        data = self.chat_completion(messages, model=model, temperature=temperature)
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return (message.get("content") or "").strip()

    def chat_completion(
        self,
        messages: List[dict],
        model: str | None = None,
        temperature: float = 0.2,
        tools: List[dict] | None = None,
    ) -> dict:
        if not self._api_key:
            raise RuntimeError(f"API key não configurada para {self.label}.")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            **self._extra_headers,
        }
        payload: dict = {
            "model": model or self._default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def with_api_key(self, api_key: str) -> OpenAICompatibleProvider:
        return OpenAICompatibleProvider(
            provider_id=self.id,
            label=self.label,
            description=self._description,
            api_key=api_key,
            base_url=self._base_url,
            default_model=self._default_model,
            models=self._models,
            extra_headers=self._extra_headers,
        )
