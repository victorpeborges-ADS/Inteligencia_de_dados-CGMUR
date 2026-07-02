"""Testes do pipeline RAG e provedores de IA."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from rag.config import CHUNK_SIZE_CHARS, EMBEDDING_DIM
from rag.ingest import _split_text
from rag.providers.registry import default_chat_provider_id, get_chat_provider, list_chat_providers


def test_chunk_splitter_defaults():
    text = "A" * (CHUNK_SIZE_CHARS * 3)
    chunks = _split_text(text)
    assert len(chunks) >= 2
    assert all(len(c) <= CHUNK_SIZE_CHARS + 50 for c in chunks)


def test_mistral_embed_dimensions():
    fake_vec = [0.1] * EMBEDDING_DIM
    with patch("rag.embeddings.mistral_client.embed", return_value=fake_vec):
        from rag.store import embed_query

        result = embed_query("teste de embedding")
        assert len(result) == EMBEDDING_DIM


def test_fiscal_route_bypasses_llm():
    db = MagicMock()
    muni = MagicMock()
    muni.nome = "Recife"
    muni.uf = "PE"
    muni.codigo_ibge = "2611606"
    muni.id = 1
    muni.populacao = 1000000
    muni.area_km2 = 200

    with patch("rag.chat.detect_fiscal_intent", return_value=True), patch(
        "rag.chat.answer_fiscal_question",
        return_value={"response": "Resposta fiscal", "source_url": "https://example.com"},
    ):
        from rag.chat import rag_assistant

        out = rag_assistant.chat(db, muni, "Qual a despesa com pessoal?", [])
        assert out["response"] == "Resposta fiscal"
        assert out["rag_sources"] == []
        assert out["source_url"] == "https://example.com"


def test_list_providers_mistral_only():
    providers = list_chat_providers()
    ids = [p.id for p in providers]
    assert ids == ["mistral"]


def test_default_provider_is_mistral():
    assert default_chat_provider_id() == "mistral"


def test_get_chat_provider_rejects_non_allowed():
    try:
        get_chat_provider("openai", api_key="sk-test-key")
        assert False, "deveria rejeitar openai"
    except ValueError as exc:
        assert "não permitido" in str(exc).lower()


def test_get_chat_provider_mistral_with_api_key_override():
    provider = get_chat_provider("mistral", api_key="test-key")
    assert provider.is_available()
