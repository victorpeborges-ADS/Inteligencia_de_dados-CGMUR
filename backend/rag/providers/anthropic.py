from __future__ import annotations

import logging
from typing import List

import httpx

from rag.config import ANTHROPIC_API_KEY, ANTHROPIC_CHAT_MODEL
from rag.providers.base import ProviderInfo

logger = logging.getLogger(__name__)


class AnthropicProvider:
    id = "anthropic"
    label = "Anthropic (Claude)"
    is_local = False

    def __init__(self, api_key: str | None = None):
        self._api_key = (api_key if api_key is not None else ANTHROPIC_API_KEY).strip()

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            label=self.label,
            description="Claude via API Anthropic.",
            available=self.is_available(),
            is_local=False,
            requires_api_key=True,
            default_model=ANTHROPIC_CHAT_MODEL,
            models=[
                ANTHROPIC_CHAT_MODEL,
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
            ],
            privacy_note="Contexto RAG enviado à Anthropic.",
        )

    def is_available(self) -> bool:
        return bool(self._api_key)

    def with_api_key(self, api_key: str) -> AnthropicProvider:
        return AnthropicProvider(api_key=api_key)

    def chat(
        self,
        messages: List[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        if not self.is_available():
            raise RuntimeError("ANTHROPIC_API_KEY não configurada.")

        system_parts: List[str] = []
        api_messages: List[dict[str, str]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role in {"user", "assistant"}:
                api_messages.append({"role": role, "content": content})

        body = {
            "model": model or ANTHROPIC_CHAT_MODEL,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": api_messages,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            blocks = data.get("content", [])
            return "".join(block.get("text", "") for block in blocks if block.get("type") == "text").strip()
