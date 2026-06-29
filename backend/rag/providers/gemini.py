from __future__ import annotations

import logging
from typing import List

import httpx

from rag.config import GEMINI_API_KEY, GEMINI_CHAT_MODEL
from rag.providers.base import ProviderInfo

logger = logging.getLogger(__name__)


class GeminiProvider:
    id = "gemini"
    label = "Google Gemini"
    is_local = False

    def __init__(self, api_key: str | None = None):
        self._api_key = (api_key if api_key is not None else GEMINI_API_KEY).strip()

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id=self.id,
            label=self.label,
            description="Gemini via Google AI Studio / Vertex.",
            available=self.is_available(),
            is_local=False,
            requires_api_key=True,
            default_model=GEMINI_CHAT_MODEL,
            models=[GEMINI_CHAT_MODEL, "gemini-2.0-flash-lite", "gemini-1.5-pro"],
            privacy_note="Contexto RAG enviado ao Google.",
        )

    def is_available(self) -> bool:
        return bool(self._api_key)

    def with_api_key(self, api_key: str) -> GeminiProvider:
        return GeminiProvider(api_key=api_key)

    def chat(
        self,
        messages: List[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        if not self.is_available():
            raise RuntimeError("GEMINI_API_KEY não configurada.")

        model_name = model or GEMINI_CHAT_MODEL
        system_parts: List[str] = []
        contents: List[dict] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        body: dict = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        if system_parts:
            body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={self._api_key}"
        )
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini retornou resposta vazia.")
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(part.get("text", "") for part in parts).strip()
