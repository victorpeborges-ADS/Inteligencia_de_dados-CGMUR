#!/usr/bin/env bash
# Produção MCID — valida certificados institucionais e sobe stack com auth + TLS.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${1:-.env}"
COMPOSE=(
  docker compose
  -f docker-compose.yml
  -f docker-compose.prod.yml
  -f docker-compose.prod-tls.yml
)

if [[ -f "$ENV_FILE" ]]; then
  COMPOSE+=(--env-file "$ENV_FILE")
  echo "Usando $ENV_FILE"
else
  echo "Erro: crie $ENV_FILE a partir de .env.production.example" >&2
  exit 1
fi

chmod +x "$ROOT/scripts/validate-tls-certs.sh" "$ROOT/deploy/nginx/docker-entrypoint.sh"
"$ROOT/scripts/validate-tls-certs.sh"

echo "Subindo produção Sinidu+Clima…"
"${COMPOSE[@]}" up -d --build

echo ""
echo "Aguardando readiness…"
BASE="$(grep -E '^PUBLIC_BASE_URL=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' || echo 'https://localhost')"
for _ in $(seq 1 40); do
  if curl -skf "${BASE}/health/ready" >/dev/null 2>&1; then
    break
  fi
  sleep 3
done

echo ""
echo "=== Sinidu+Clima — Produção ==="
echo "App:  $BASE"
echo "API:  $BASE/api/v1/"
echo "TLS:  $BASE/health/tls"
echo "OIDC: $BASE/health/oidc"
echo ""
echo "Smoke de prontidão…"
python3 "$ROOT/scripts/homolog_smoke_test.py" "$BASE" || {
  echo "WARN: smoke reportou falhas — revise AUTH_JWT_SECRET, DEM e batch no painel Sistema" >&2
}
