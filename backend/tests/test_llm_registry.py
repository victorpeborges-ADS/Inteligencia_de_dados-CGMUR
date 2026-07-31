"""Testes do registry de provedores LLM."""

from rag.providers.registry import get_chat_provider, resolve_chat_provider_with_fallback


def test_resolve_chat_provider_without_api_key_returns_instance(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    provider = resolve_chat_provider_with_fallback()
    assert provider.id == "mistral"
    assert provider.is_available() is False


def test_get_chat_provider_mistral_without_key(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    provider = get_chat_provider("mistral")
    assert not provider.is_available()
