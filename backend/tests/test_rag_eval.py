"""Testes do eval set RAG — scoring determinístico (sem LLM)."""

from __future__ import annotations

from types import SimpleNamespace

from rag.eval.runner import load_eval_dataset
from rag.eval.scoring import (
    aggregate_results,
    evaluate_case,
    score_keywords,
    score_retrieval,
    source_label_match,
)


def _chunk(label: str, content: str, similarity: float):
    return SimpleNamespace(source_label=label, content=content, similarity=similarity)


def test_source_label_match_partial():
    assert source_label_match("Lei nº 12.608/2012 — PNPDEC", "Lei nº 12.608/2012")
    assert not source_label_match("Outro documento", "Lei nº 12.608/2012")


def test_score_retrieval_hit():
    chunks = [
        _chunk("Lei nº 12.608/2012 — PNPDEC", "competências municipais mapeamento de áreas de risco", 0.72),
    ]
    result = score_retrieval(
        chunks,
        expected_source_labels=["Lei nº 12.608/2012"],
        min_similarity=0.35,
    )
    assert result["hit"] is True
    assert result["best_similarity"] == 0.72


def test_score_keywords_ratio():
    text = "O município deve elaborar plano municipal e sistema de alerta precoce."
    assert score_keywords(text, ["plano", "alerta", "inexistente"]) == 2 / 3


def test_evaluate_case_pass():
    case = {
        "id": "demo",
        "question": "competências municipais defesa civil",
        "expected_source_labels": ["Lei nº 12.608/2012"],
        "expected_keywords": ["municip", "risco"],
        "min_retrieval_similarity": 0.4,
    }
    chunks = [
        _chunk(
            "Lei nº 12.608/2012 — PNPDEC",
            "Competências municipais incluem mapear áreas de risco e defesa civil.",
            0.65,
        )
    ]
    out = evaluate_case(case, chunks)
    assert out["passed"] is True
    assert out["retrieval"]["hit"] is True


def test_evaluate_case_fail_low_similarity():
    case = load_eval_dataset()[0]
    chunks = [_chunk("Lei nº 12.608/2012", "texto", 0.1)]
    out = evaluate_case(case, chunks)
    assert out["passed"] is False


def test_dataset_has_minimum_cases():
    cases = load_eval_dataset()
    assert len(cases) >= 14
    ids = {c["id"] for c in cases}
    assert "sinidu_contingencia" in ids
    assert "sinidu_calor_lst" in ids
    assert "sinidu_maturidade" in ids
    assert "sinidu_alerta_vivo" in ids
    assert "sinidu_ml_alagamento" in ids
    assert all(c.get("question") and c.get("id") for c in cases)


def test_aggregate_results():
    summary = aggregate_results(
        [
            {"passed": True, "retrieval": {"hit": True}, "retrieval_keyword_score": 0.8},
            {"passed": False, "retrieval": {"hit": False}, "retrieval_keyword_score": 0.2},
        ]
    )
    assert summary["total"] == 2
    assert summary["passed"] == 1
    assert summary["pass_rate"] == 0.5
