#!/usr/bin/env bash
# Smoke test rápido para demo MCID — API + dicas UI.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API="${1:-http://localhost:8000}"
FRONTEND="${FRONTEND_URL:-http://localhost:3000}"

echo "=== Sinidu+Clima — demo smoke ==="
echo "API: $API"
echo ""

python3 scripts/homolog_smoke_test.py "$API"
SMOKE_EXIT=$?

echo ""
echo "--- Frontend ---"
if curl -sf --max-time 5 "${FRONTEND}/" >/dev/null 2>&1; then
  echo "[OK] Frontend respondendo em ${FRONTEND}"
else
  echo "[INFO] Frontend offline (${FRONTEND}) — suba com: docker compose up -d frontend"
fi

echo ""
echo "--- Simulação (Recife 120 mm, opcional) ---"
if curl -sf --max-time 3 "${API}/health/ready" >/dev/null 2>&1; then
  CODE=$(curl -s -o /tmp/sinidu_sim_smoke.json -w "%{http_code}" \
    -X POST "${API}/api/v1/simulations/extreme-rainfall/async" \
    -H 'Content-Type: application/json' \
    -d '{"codigo_ibge":"2611606","precipitation_mm":120}' 2>/dev/null || echo "000")
  if [[ "$CODE" == "200" || "$CODE" == "202" ]]; then
    echo "[OK] Job simulação aceito (HTTP ${CODE})"
  else
    echo "[INFO] Simulação async HTTP ${CODE} (pode exigir warm-up DEM)"
  fi
fi

echo ""
echo "--- Validação Recife (opcional, ~3 min) ---"
if [[ "${RUN_RECIFE_VALIDATION:-0}" == "1" ]] && [[ -f scripts/validacao_recife_ui.py ]]; then
  python3 scripts/validacao_recife_ui.py "$API" || SMOKE_EXIT=1
else
  echo "[INFO] Pulado — defina RUN_RECIFE_VALIDATION=1 para rodar validacao_recife_ui.py"
fi

echo ""
echo "Roteiro UI: CHECKLIST_DEMO_MCID.md §4"
exit "$SMOKE_EXIT"
