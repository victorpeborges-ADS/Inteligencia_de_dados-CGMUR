#!/usr/bin/env bash
# Stack completa de homologação: auth + multi-tenant + proxy TLS + Keycloak OIDC.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${1:-.env.homolog}"
COMPOSE=(
  docker compose
  -f docker-compose.yml
  -f docker-compose.prod.yml
  -f docker-compose.proxy-tls.yml
  -f docker-compose.oidc.yml
)

if [[ -f "$ENV_FILE" ]]; then
  COMPOSE+=(--env-file "$ENV_FILE")
  echo "Usando $ENV_FILE"
fi

"$ROOT/scripts/generate-dev-certs.sh"

BUILD_FLAG="--no-build"
if [[ "${FORCE_BUILD:-0}" == "1" ]]; then
  BUILD_FLAG="--build"
  echo "FORCE_BUILD=1 — rebuild completo (pode levar vários minutos)."
elif ! docker image inspect sinidumvp-backend:latest >/dev/null 2>&1 \
  || ! docker image inspect sinidumvp-frontend:latest >/dev/null 2>&1; then
  BUILD_FLAG="--build"
  echo "Imagens ausentes — build inicial."
else
  echo "Imagens locais encontradas — subindo sem rebuild (FORCE_BUILD=1 para reconstruir)."
fi

echo "Subindo stack de homologação…"
"${COMPOSE[@]}" up -d ${BUILD_FLAG}

echo ""
echo "Aguardando readiness do backend…"
for _ in $(seq 1 30); do
  if curl -skf "https://localhost/health/ready" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo ""
echo "=== Homologação Sinidu+Clima ==="
echo "App:       https://localhost  (aceite o certificado autoassinado — rota recomendada)"
echo "Alternativa: http://localhost:3000  (mapa offline se API HTTPS bloquear no browser)"
echo "API:       https://localhost/api/v1/"
echo "Keycloak:  http://localhost:8080  (admin / admin)"
echo ""
echo "Usuários OIDC de teste (realm sinidu):"
echo "  admin.sinidu / admin   → role admin"
echo "  gestor.pe / gestor     → gestor municipal (UF PE)"
echo "  leitor.pe / leitor     → leitor (UF PE)"
echo ""
echo "Login SSO: botão na modal de autenticação do frontend."
echo "Auditoria: https://localhost/auditoria (após login admin)"
echo ""
echo "Smoke OIDC/TLS:"
echo "  ./scripts/validacao_oidc_govbr.sh https://localhost"
echo "Smoke completo (auth + amostra):"
echo "  ./scripts/demo-smoke.sh https://localhost"
echo "Piloto Recife+Aracaju (opcional, ~5 min):"
echo "  RUN_PILOTO_VALIDATION=1 ./scripts/demo-smoke.sh https://localhost"
