from __future__ import annotations

import logging
from typing import Any, List

import httpx

from rag.config import OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL, OLLAMA_EMBED_MODEL

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")

    def embed(self, text: str, model: str | None = None) -> List[float]:
        model = model or OLLAMA_EMBED_MODEL
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text},
            )
            response.raise_for_status()
            return response.json()["embedding"]

    def embed_batch(self, texts: List[str], model: str | None = None) -> List[List[float]]:
        return [self.embed(text, model=model) for text in texts]

    def chat(
        self,
        messages: List[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        model = model or OLLAMA_CHAT_MODEL
        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            return payload.get("message", {}).get("content", "").strip()

    def health(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False


ollama_client = OllamaClient()
