from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from rag.config import TOP_K_CHUNKS
from rag.embeddings import embed_text
from rag.store import RetrievedChunk, search_similar


def retrieve(db: Session, query: str, top_k: int = TOP_K_CHUNKS) -> List[RetrievedChunk]:
    return search_similar(db, embed_text(query), top_k=top_k)
