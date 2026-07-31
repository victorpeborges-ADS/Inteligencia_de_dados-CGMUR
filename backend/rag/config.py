from __future__ import annotations

import os

# --- Provedor padrão de chat (geração) ---
AI_CHAT_PROVIDER = os.getenv("AI_CHAT_PROVIDER", "mistral").strip().lower()

# --- Embeddings RAG (Mistral) ---
AI_EMBED_PROVIDER = os.getenv("AI_EMBED_PROVIDER", "mistral").strip().lower()

# Provedores expostos na API (somente Mistral por padrão)
AI_ALLOWED_PROVIDERS = [
    p.strip().lower()
    for p in os.getenv("AI_ALLOWED_PROVIDERS", "mistral").split(",")
    if p.strip()
]

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1:8b-instruct-q4_K_M")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# OpenAI / compatível
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

# OpenRouter (API OpenAI-compatível)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_CHAT_MODEL = os.getenv("OPENROUTER_CHAT_MODEL", "anthropic/claude-3.5-haiku")

# Groq (API OpenAI-compatível)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")

# Mistral AI (API OpenAI-compatível)
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
MISTRAL_CHAT_MODEL = os.getenv("MISTRAL_CHAT_MODEL", "mistral-small-latest")
MISTRAL_EMBED_MODEL = os.getenv("MISTRAL_EMBED_MODEL", "mistral-embed")

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_CHAT_MODEL = os.getenv("ANTHROPIC_CHAT_MODEL", "claude-3-5-haiku-20241022")

# Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.0-flash")

# RAG
CHUNK_SIZE_CHARS = int(os.getenv("RAG_CHUNK_SIZE_CHARS", "3200"))
CHUNK_OVERLAP_CHARS = int(os.getenv("RAG_CHUNK_OVERLAP_CHARS", "400"))
TOP_K_CHUNKS = int(os.getenv("RAG_TOP_K", "5"))
EMBEDDING_DIM = int(os.getenv("RAG_EMBEDDING_DIM", "1024"))

SYSTEM_PROMPT_TEMPLATE = """Você é o **Assistente Municipal Sinidu+Clima**, copiloto institucional para gestores públicos brasileiros.
Município em foco: **{municipio_nome}**.

## Regras obrigatórias
1. Responda **sempre em português**, com linguagem clara para gestores e técnicos municipais.
2. Use **apenas** os dados municipais integrados e os trechos documentais RAG abaixo. **Nunca invente** números, notas ou eventos.
3. **Cite a fonte** ao final de cada bloco factual, no formato `[Fonte: NOME]` — ex.: `[Fonte: CAPAG / Tesouro Nacional]`, `[Fonte: IBGE]`, `[Fonte: Sinidu+Clima]`.
4. Se a informação não constar nos dados, diga: *"Esta informação não está disponível na base Sinidu+Clima para este município."*
   Em seguida, se o contexto municipal citar **GeoReDUS**, oriente o gestor com o link `municipioId`
   indicado — **nunca invente valores** do GeoReDUS; trate-o apenas como referência externa complementar.
5. Para questões fiscais detalhadas, indique também o Siconfi.IA: https://siconfi-ia.tesourotransparente.gov.br/
6. Estruture respostas longas com títulos `###` e bullets quando útil.

## Dados municipais integrados (PostGIS, APIs públicas, diagnósticos)
{municipal_context}

## Documentos normativos e referências técnicas (RAG)
{rag_context}
"""
