from __future__ import annotations

from typing import List

from rag.mistral_client import mistral_client


def embed_text(text: str) -> List[float]:
    return mistral_client.embed(text)


def embed_texts(texts: List[str]) -> List[List[float]]:
    return mistral_client.embed_batch(texts)
