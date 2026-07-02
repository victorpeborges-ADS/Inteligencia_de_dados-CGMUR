#!/bin/sh
set -e

# Modelos removidos para economizar disco (~9 GB).
# Para reativar IA local: docker compose --profile ai up -d ollama
# e depois: docker exec sinidu_ollama ollama pull nomic-embed-text

ollama serve
