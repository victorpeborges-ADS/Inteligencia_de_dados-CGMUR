#!/bin/sh
set -e

ollama serve &
OLLAMA_PID=$!

echo "Aguardando Ollama..."
for i in $(seq 1 60); do
  if ollama list >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "Baixando modelos (primeira execução pode demorar)..."
ollama pull nomic-embed-text || true
ollama pull llama3.1:8b-instruct-q4_K_M || true
ollama pull mistral:7b-instruct-v0.3-q4_K_M || true

echo "Ollama pronto."
wait $OLLAMA_PID
