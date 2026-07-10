#!/usr/bin/env bash
# Ativa malha viária OSRM para rotas reais na contingência.
# Padrão: pe-se (Recife + Aracaju, ~80 MB, processamento rápido).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REGION="${OSRM_REGION:-pe-se}"
OSRM_DATA="${ROOT}/docker/osrm"
PBF="${OSRM_DATA}/${REGION}-latest.osm.pbf"
CELLS="${OSRM_DATA}/${REGION}-latest.osrm.cells"
API="${SINIDU_API_URL:-http://localhost:8000}"

echo "==> Sinidu+Clima — ativar OSRM (${REGION})"

if [[ ! -f "${PBF}" ]]; then
  echo "    PBF ausente — executando setup completo (download + processamento)..."
  OSRM_REGION="${REGION}" bash "${ROOT}/docker/osrm/setup-osrm.sh" || exit 1
elif [[ ! -f "${CELLS}" ]]; then
  echo "    PBF encontrado — processando grafo (3–25 min conforme região)..."
  OSRM_REGION="${REGION}" bash "${ROOT}/docker/osrm/setup-osrm.sh" || exit 1
else
  echo "    Dados OSRM já processados."
fi

echo "==> Subindo container sinidu_osrm..."
docker compose up -d osrm

echo "==> Aguardando serviço na porta 5000..."
for i in $(seq 1 40); do
  if curl -sf -m 3 "http://localhost:5000/route/v1/driving/-34.88,-8.05;-34.87,-8.06?overview=false" >/dev/null 2>&1; then
    echo "    OSRM online (tentativa ${i})."
    break
  fi
  if [[ "$i" -eq 40 ]]; then
    echo "    Aviso: OSRM ainda não respondeu — verifique: docker logs sinidu_osrm"
    exit 1
  fi
  sleep 3
done

if curl -sf -m 5 "${API}/health/live" >/dev/null 2>&1; then
  echo "==> Status via API Sinidu:"
  curl -sf -m 10 "${API}/api/v1/routing/status" | python3 -m json.tool 2>/dev/null || true
fi

echo ""
echo "Pronto. Rotas de contingência em ${REGION} usarão malha real quando a UF estiver na cobertura."
echo "    Nordeste completo: OSRM_REGION=nordeste bash scripts/osrm-enable.sh"
