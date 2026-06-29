from __future__ import annotations

from typing import List

from rag.config import OLLAMA_EMBED_MODEL
from rag.ollama_client import ollama_client


def embed_text(text: str) -> List[float]:
    return ollama_client.embed(text, model=OLLAMA_EMBED_MODEL)


def embed_texts(texts: List[str]) -> List[List[float]]:
    return ollama_client.embed_batch(texts, model=OLLAMA_EMBED_MODEL)
