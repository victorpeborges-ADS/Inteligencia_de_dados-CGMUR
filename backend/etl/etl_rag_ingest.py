#!/usr/bin/env python3
"""Ingestão RAG: PDFs/Markdown → chunks → embeddings Ollama → pgvector.

Uso:
  python etl/etl_rag_ingest.py
  python etl/etl_rag_ingest.py --force
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from rag.ingest import ingest_all
from rag.store import count_documents

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingestão RAG Sinidu+Clima")
    parser.add_argument("--force", action="store_true", help="Reindexar todos os documentos")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = ingest_all(db, force=args.force)
        total = count_documents(db)
        print(f"Documentos processados: {stats['documents']}, chunks novos: {stats['chunks']}, total DB: {total}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
