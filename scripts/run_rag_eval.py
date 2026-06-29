#!/usr/bin/env python3
"""Executa eval de retrieval RAG contra o corpus indexado."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.db import SessionLocal
from rag.eval.runner import format_eval_report, run_retrieval_eval


def main() -> int:
    db = SessionLocal()
    try:
        report = run_retrieval_eval(db)
        print(format_eval_report(report))
        summary = report.get("summary") or {}
        min_rate = float(os.getenv("RAG_EVAL_MIN_PASS_RATE", "0.5"))
        return 0 if float(summary.get("pass_rate") or 0) >= min_rate else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
