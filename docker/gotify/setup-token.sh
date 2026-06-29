#!/usr/bin/env bash
# Cria app Gotify e imprime token para docker-compose (primeira execução)
set -euo pipefail

GOTIFY_URL="${GOTIFY_URL:-http://localhost:8888}"
USER="${GOTIFY_USER:-admin}"
PASS="${GOTIFY_PASS:-admin}"

echo "==> Autenticando em ${GOTIFY_URL} ..."
TOKEN=$(curl -s -X POST "${GOTIFY_URL}/client/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${USER}\",\"password\":\"${PASS}\"}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

if [[ -z "${TOKEN}" ]]; then
  echo "Falha no login. Acesse ${GOTIFY_URL} e crie um Application Token manualmente."
  exit 1
fi

APP=$(curl -s -X POST "${GOTIFY_URL}/application" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Sinidu+Clima","description":"Alertas operacionais MCID","defaultPriority":8}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('token',''))")

if [[ -z "${APP}" ]]; then
  echo "App já existe ou erro. Liste em ${GOTIFY_URL} → Apps"
  exit 1
fi

echo ""
echo "Adicione ao docker-compose.yml (backend environment):"
echo "  - GOTIFY_TOKEN=${APP}"
echo ""
echo "Abra ${GOTIFY_URL} no browser para ver notificações."
