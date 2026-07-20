from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, List

import yaml
from sqlalchemy.orm import Session

from rag.config import CHUNK_OVERLAP_CHARS, CHUNK_SIZE_CHARS
from rag.embeddings import embed_text
from rag.store import delete_source, ensure_vector_extension, insert_chunks

logger = logging.getLogger(__name__)

MANIFEST_PATH = Path(__file__).resolve().parent / "corpus" / "manifest.yaml"
RAG_ROOT = Path(__file__).resolve().parent


def _load_document(path: Path) -> str:
    from langchain_community.document_loaders import PyPDFLoader, TextLoader

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        loader = PyPDFLoader(str(path))
        pages = loader.load()
        return "\n\n".join(page.page_content for page in pages if page.page_content)
    if suffix in {".md", ".txt"}:
        return TextLoader(str(path), encoding="utf-8").load()[0].page_content
    raise ValueError(f"Formato não suportado: {path}")


def _split_text(text: str) -> List[str]:
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        # Fallback sem langchain (testes/host leve)
        size = CHUNK_SIZE_CHARS
        overlap = CHUNK_OVERLAP_CHARS
        if size <= 0:
            return [text] if text else []
        chunks: List[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = min(n, start + size)
            chunks.append(text[start:end])
            if end >= n:
                break
            start = max(0, end - overlap)
        return chunks

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE_CHARS,
        chunk_overlap=CHUNK_OVERLAP_CHARS,
        length_function=len,
    )
    return splitter.split_text(text)


def load_manifest() -> List[dict[str, Any]]:
    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("documents", [])


def ingest_all(db: Session, force: bool = False) -> dict[str, int]:
    ensure_vector_extension(db)
    stats = {"documents": 0, "chunks": 0}
    for doc in load_manifest():
        doc_id = doc["id"]
        label = doc["label"]
        rel_path = doc["path"]
        path = (RAG_ROOT / rel_path).resolve()
        source_key = f"{doc_id}:{path.name}"

        if not path.exists():
            logger.warning("Documento ausente: %s", path)
            continue

        if force:
            delete_source(db, source_key)

        from sqlalchemy import text as sql_text

        existing = db.execute(
            sql_text("SELECT COUNT(*) FROM rag_documents WHERE source = :s"),
            {"s": source_key},
        ).scalar()
        if existing and not force:
            logger.info("Pulando %s (%d chunks já indexados)", label, existing)
            continue

        logger.info("Indexando %s...", label)
        text = _load_document(path)
        chunks = _split_text(text)
        records = []
        for idx, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            embedding = embed_text(chunk)
            vec = "[" + ",".join(str(float(x)) for x in embedding) + "]"
            records.append({
                "source": source_key,
                "source_label": label,
                "chunk_idx": idx,
                "content": chunk.strip(),
                "embedding": vec,
                "metadata": json.dumps({"doc_id": doc_id, "category": doc.get("category", "")}, ensure_ascii=False),
            })
        inserted = insert_chunks(db, records)
        stats["documents"] += 1
        stats["chunks"] += inserted
        logger.info("%s → %d chunks", label, inserted)
    return stats
