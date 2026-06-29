from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from rag.eval.scoring import aggregate_results, evaluate_case
from rag.retriever import retrieve

DATASET_PATH = Path(__file__).resolve().parent / "dataset.yaml"


def load_eval_dataset(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or DATASET_PATH
    with target.open(encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    return list(payload.get("cases") or [])


def run_retrieval_eval(db: Session, *, top_k: int = 5) -> dict[str, Any]:
    cases = load_eval_dataset()
    results = []
    for case in cases:
        question = str(case.get("question") or "")
        chunks = retrieve(db, question, top_k=top_k)
        results.append(evaluate_case(case, chunks))
    summary = aggregate_results(results)
    return {"summary": summary, "results": results}


def format_eval_report(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        f"RAG eval — {summary.get('passed', 0)}/{summary.get('total', 0)} casos OK",
        f"  retrieval hit rate: {summary.get('retrieval_hit_rate', 0):.1%}",
        f"  avg keyword score:  {summary.get('avg_retrieval_keyword_score', 0):.2f}",
        "",
    ]
    for item in report.get("results") or []:
        status = "OK" if item.get("passed") else "FAIL"
        retrieval = item.get("retrieval") or {}
        lines.append(
            f"[{status}] {item.get('id')} — sim={retrieval.get('best_similarity')} "
            f"label={retrieval.get('top_label')}"
        )
    return "\n".join(lines)
