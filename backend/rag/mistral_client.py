from __future__ import annotations

from typing import List

import httpx

from rag.config import EMBEDDING_DIM, MISTRAL_API_KEY, MISTRAL_BASE_URL, MISTRAL_EMBED_MODEL


class MistralClient:
    """Cliente Mistral — embeddings (RAG) via API oficial."""

    def embed(self, text: str, model: str | None = None) -> List[float]:
        return self.embed_batch([text], model=model)[0]

    def embed_batch(self, texts: List[str], model: str | None = None) -> List[List[float]]:
        if not MISTRAL_API_KEY.strip():
            raise RuntimeError("MISTRAL_API_KEY não configurada.")

        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY.strip()}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or MISTRAL_EMBED_MODEL,
            "input": texts,
        }
        url = f"{MISTRAL_BASE_URL.rstrip('/')}/embeddings"
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            items = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
            vectors = [item["embedding"] for item in items]
            for vector in vectors:
                if len(vector) != EMBEDDING_DIM:
                    raise ValueError(
                        f"Embedding Mistral com {len(vector)} dimensões; esperado {EMBEDDING_DIM}."
                    )
            return vectors


mistral_client = MistralClient()
