"""Testes do pipeline RAG e provedores de IA."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from rag.config import CHUNK_SIZE_CHARS, EMBEDDING_DIM
from rag.ingest import _split_text
from rag.providers.registry import get_chat_provider, list_chat_providers


def test_chunk_splitter_defaults():
    text = "A" * (CHUNK_SIZE_CHARS * 3)
    chunks = _split_text(text)
    assert len(chunks) >= 2
    assert all(len(c) <= CHUNK_SIZE_CHARS + 50 for c in chunks)


def test_ollama_embed_dimensions():
    fake_vec = [0.1] * EMBEDDING_DIM
    with patch("rag.store.ollama_client.embed", return_value=fake_vec):
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


def test_list_providers_includes_ollama():
    providers = list_chat_providers()
    ids = [p.id for p in providers]
    assert "ollama" in ids
    assert "openai" in ids
    assert "anthropic" in ids
    assert "mistral" in ids


def test_get_chat_provider_with_api_key_override():
    provider = get_chat_provider("openai", api_key="sk-test-key")
    assert provider.is_available()


def test_list_providers_with_user_keys():
    providers = list_chat_providers({"openai": "sk-user-key"})
    openai = next(p for p in providers if p.id == "openai")
    assert openai.available is True
