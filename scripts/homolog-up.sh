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

echo "Subindo stack de homologação (build pode levar alguns minutos)…"
"${COMPOSE[@]}" up -d --build

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
echo "App:       https://localhost  (aceite o certificado autoassinado)"
echo "Alternativa: http://localhost:3000  (frontend direto, mesma build prod)"
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
