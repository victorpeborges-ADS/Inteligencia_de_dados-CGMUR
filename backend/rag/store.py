from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from rag.config import EMBEDDING_DIM, TOP_K_CHUNKS
from rag.embeddings import embed_text

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    id: int
    source: str
    source_label: str
    chunk_idx: int
    content: str
    similarity: float


def ensure_vector_extension(db: Session) -> None:
    db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    db.commit()


def search_similar(db: Session, query_embedding: List[float], top_k: int = TOP_K_CHUNKS) -> List[RetrievedChunk]:
    if len(query_embedding) != EMBEDDING_DIM:
        raise ValueError(f"Embedding deve ter {EMBEDDING_DIM} dimensões.")

    vec_literal = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"
    sql = text(
        """
        SELECT id, source, source_label, chunk_idx, content,
               1 - (embedding <=> CAST(:vec AS vector)) AS similarity
        FROM rag_documents
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:vec AS vector)
        LIMIT :top_k
        """
    )
    rows = db.execute(sql, {"vec": vec_literal, "top_k": top_k}).mappings().all()
    return [
        RetrievedChunk(
            id=row["id"],
            source=row["source"],
            source_label=row["source_label"],
            chunk_idx=row["chunk_idx"],
            content=row["content"],
            similarity=float(row["similarity"] or 0),
        )
        for row in rows
    ]


def delete_source(db: Session, source: str) -> None:
    db.execute(text("DELETE FROM rag_documents WHERE source = :source"), {"source": source})
    db.commit()


def insert_chunks(db: Session, records: List[dict[str, Any]]) -> int:
    if not records:
        return 0
    sql = text(
        """
        INSERT INTO rag_documents (source, source_label, chunk_idx, content, embedding, metadata)
        VALUES (:source, :source_label, :chunk_idx, :content, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
        """
    )
    for rec in records:
        db.execute(sql, rec)
    db.commit()
    return len(records)


def count_documents(db: Session) -> int:
    return db.execute(text("SELECT COUNT(*) FROM rag_documents")).scalar() or 0


def embed_query(text_query: str) -> List[float]:
    return embed_text(text_query)
