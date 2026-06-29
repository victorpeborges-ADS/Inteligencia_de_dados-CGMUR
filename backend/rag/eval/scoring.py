from __future__ import annotations

import unicodedata
from typing import Any, Iterable, Sequence


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def keyword_hits(text: str, keywords: Sequence[str]) -> tuple[int, int]:
    if not keywords:
        return 0, 0
    haystack = normalize_text(text)
    hits = sum(1 for kw in keywords if normalize_text(kw) in haystack)
    return hits, len(keywords)


def score_keywords(text: str, keywords: Sequence[str]) -> float:
    hits, total = keyword_hits(text, keywords)
    if total == 0:
        return 1.0
    return hits / total


def source_label_match(source_label: str, expected: str) -> bool:
    return normalize_text(expected) in normalize_text(source_label)


def score_retrieval(
    chunks: Iterable[Any],
    *,
    expected_source_labels: Sequence[str] | None = None,
    min_similarity: float = 0.0,
) -> dict[str, Any]:
    chunk_list = list(chunks)
    if not chunk_list:
        return {
            "hit": False,
            "best_similarity": 0.0,
            "matched_labels": [],
            "top_label": None,
        }

    best = max(chunk_list, key=lambda c: float(getattr(c, "similarity", 0) or 0))
    best_sim = float(getattr(best, "similarity", 0) or 0)
    labels = [str(getattr(c, "source_label", "") or "") for c in chunk_list]

    matched: list[str] = []
    if expected_source_labels:
        for expected in expected_source_labels:
            if any(source_label_match(label, expected) for label in labels):
                matched.append(expected)

    label_ok = not expected_source_labels or bool(matched)
    sim_ok = best_sim >= min_similarity
    return {
        "hit": label_ok and sim_ok,
        "best_similarity": round(best_sim, 4),
        "matched_labels": matched,
        "top_label": getattr(best, "source_label", None),
    }


def evaluate_case(
    case: dict[str, Any],
    chunks: Iterable[Any],
    response_text: str = "",
) -> dict[str, Any]:
    retrieval = score_retrieval(
        chunks,
        expected_source_labels=case.get("expected_source_labels") or [],
        min_similarity=float(case.get("min_retrieval_similarity") or 0.0),
    )
    keywords = case.get("expected_keywords") or []
    chunk_text = "\n".join(str(getattr(c, "content", "")) for c in chunks)
    retrieval_kw = score_keywords(chunk_text, keywords)
    response_kw = score_keywords(response_text, keywords) if response_text else None

    passed = retrieval["hit"] and retrieval_kw >= 0.5
    if response_text:
        passed = passed and (response_kw or 0) >= 0.4

    return {
        "id": case.get("id"),
        "question": case.get("question"),
        "passed": passed,
        "retrieval": retrieval,
        "retrieval_keyword_score": round(retrieval_kw, 3),
        "response_keyword_score": round(response_kw, 3) if response_kw is not None else None,
    }


def aggregate_results(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item.get("passed"))
    retrieval_hits = sum(1 for item in results if item.get("retrieval", {}).get("hit"))
    avg_kw = 0.0
    if total:
        avg_kw = sum(float(item.get("retrieval_keyword_score") or 0) for item in results) / total
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "retrieval_hit_rate": round(retrieval_hits / total, 3) if total else 0.0,
        "avg_retrieval_keyword_score": round(avg_kw, 3),
    }
