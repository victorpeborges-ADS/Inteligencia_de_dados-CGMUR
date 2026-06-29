#!/usr/bin/env bash
# Sobe stack de staging/produção com auth, multi-tenant e frontend Next standalone.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${1:-.env}"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

if [[ -f "$ENV_FILE" ]]; then
  COMPOSE+=(--env-file "$ENV_FILE")
  echo "Usando variáveis de $ENV_FILE"
else
  echo "Aviso: $ENV_FILE não encontrado — usando defaults de docker-compose.prod.yml"
fi

echo "Build e subida dos serviços…"
"${COMPOSE[@]}" up -d --build

echo ""
echo "Health:"
curl -sf "http://localhost:8000/health/ready" | head -c 200 || echo "(backend ainda iniciando)"
echo ""
echo "Frontend: http://localhost:3000"
echo "API docs: http://localhost:8000/docs"
