#!/usr/bin/env bash
# Smoke test rápido para demo MCID — API + dicas UI.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API="${1:-http://localhost:8000}"
FRONTEND="${FRONTEND_URL:-http://localhost:3000}"
SMOKE_EXIT=0

echo "=== Sinidu+Clima — demo smoke ==="
echo "API: $API"
echo ""

if [[ "$API" == https://* ]]; then
  echo "--- OIDC/TLS (homologação) ---"
  if [[ -x scripts/validacao_oidc_govbr.sh ]]; then
    ./scripts/validacao_oidc_govbr.sh "$API" || SMOKE_EXIT=1
  fi
  echo ""
fi

export HOMOLOG_USER="${HOMOLOG_USER:-admin}"
export HOMOLOG_PASSWORD="${HOMOLOG_PASSWORD:-admin}"
python3 scripts/homolog_smoke_test.py "$API"
SMOKE_EXIT=$?

if [[ -z "${HOMOLOG_TOKEN:-}" ]]; then
  CURL_TLS_PRE=()
  [[ "$API" == https://* ]] && CURL_TLS_PRE=(-k)
  HOMOLOG_TOKEN=$(curl -s "${CURL_TLS_PRE[@]}" -X POST "${API}/api/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"${HOMOLOG_USER}\",\"password\":\"${HOMOLOG_PASSWORD}\"}" \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
  export HOMOLOG_TOKEN
fi

echo ""
echo "--- Frontend ---"
if curl -sf --max-time 5 "${FRONTEND}/" >/dev/null 2>&1; then
  echo "[OK] Frontend respondendo em ${FRONTEND}"
else
  echo "[INFO] Frontend offline (${FRONTEND}) — suba com: docker compose up -d frontend"
fi

echo ""
echo "--- Simulação (Recife 120 mm, opcional) ---"
CURL_TLS=()
if [[ "$API" == https://* ]]; then
  CURL_TLS=(-k)
fi
if curl -sf "${CURL_TLS[@]}" --max-time 3 "${API}/health/ready" >/dev/null 2>&1; then
  CODE=$(curl -s "${CURL_TLS[@]}" -o /tmp/sinidu_sim_smoke.json -w "%{http_code}" \
    -X POST "${API}/api/v1/simulations/extreme-rainfall/async" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${HOMOLOG_TOKEN}" \
    -d '{"codigo_ibge":"2611606","precipitacao_mm":120}' 2>/dev/null || echo "000")
  if [[ "$CODE" == "200" || "$CODE" == "202" ]]; then
    echo "[OK] Job simulação aceito (HTTP ${CODE})"
  else
    echo "[INFO] Simulação async HTTP ${CODE} (pode exigir warm-up DEM)"
  fi
fi

echo ""
echo "--- OSRM (opcional) ---"
if [[ "${RUN_OSRM_VALIDATION:-0}" == "1" ]] && [[ -f scripts/validacao_osrm.py ]]; then
  python3 scripts/validacao_osrm.py "$API" || SMOKE_EXIT=1
else
  echo "[INFO] Pulado — defina RUN_OSRM_VALIDATION=1 para validacao_osrm.py"
fi

echo ""
echo "--- Validação piloto Recife+Aracaju (opcional, ~5 min) ---"
if [[ "${RUN_PILOTO_VALIDATION:-0}" == "1" ]] && [[ -f scripts/validacao_piloto_demo.py ]]; then
  python3 scripts/validacao_piloto_demo.py "$API" || SMOKE_EXIT=1
elif [[ "${RUN_RECIFE_VALIDATION:-0}" == "1" ]] && [[ -f scripts/validacao_recife_ui.py ]]; then
  python3 scripts/validacao_recife_ui.py "$API" || SMOKE_EXIT=1
else
  echo "[INFO] Pulado — RUN_PILOTO_VALIDATION=1 ou RUN_RECIFE_VALIDATION=1"
fi

echo ""
echo "Roteiro UI: CHECKLIST_DEMO_MCID.md §4"
exit "$SMOKE_EXIT"
