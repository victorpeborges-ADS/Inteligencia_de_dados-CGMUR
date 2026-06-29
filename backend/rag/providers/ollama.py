from __future__ import annotations

from typing import List

from rag.config import OLLAMA_CHAT_MODEL
from rag.ollama_client import ollama_client
from rag.providers.base import ProviderInfo


class OllamaChatProvider:
    id = "ollama"
    label = "Ollama (local)"
    is_local = True

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            label=self.label,
            description="LLM local via Ollama — dados não saem do servidor.",
            available=self.is_available(),
            is_local=True,
            requires_api_key=False,
            default_model=OLLAMA_CHAT_MODEL,
            models=[
                OLLAMA_CHAT_MODEL,
                "llama3.1:8b-instruct-q4_K_M",
                "mistral:7b-instruct-v0.3-q4_K_M",
                "gemma2:9b",
            ],
            privacy_note="Recomendado para dados sensíveis de municípios.",
        )

    def is_available(self) -> bool:
        return ollama_client.health()

    def chat(
        self,
        messages: List[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        return ollama_client.chat(messages, model=model, temperature=temperature)

    def with_api_key(self, api_key: str) -> OllamaChatProvider:
        return self
