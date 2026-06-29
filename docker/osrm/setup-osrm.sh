#!/usr/bin/env bash
# Prepara dados OSRM para roteamento local (Pernambuco — ~50 MB, cobre Recife e região)
# Regiões Geofabrik: pernambuco | nordeste | sudeste | sul | centro-oeste | norte | brazil
# UFs padrão derivam de OSRM_REGION no backend (ou defina OSRM_COVERED_UFS explicitamente)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}"
REGION="${OSRM_REGION:-pernambuco}"
VALID_REGIONS="pernambuco nordeste sudeste sul centro-oeste norte brazil"
if ! echo "${VALID_REGIONS}" | grep -qw "${REGION}"; then
  echo "Região inválida: ${REGION}. Use: ${VALID_REGIONS}"
  exit 1
fi
PBF_URL="https://download.geofabrik.de/south-america/brazil/${REGION}-latest.osm.pbf"
PBF_FILE="${DATA_DIR}/${REGION}-latest.osm.pbf"
OSRM_BASE="${DATA_DIR}/${REGION}-latest.osrm"

echo "==> Sinidu+Clima OSRM setup (${REGION})"
mkdir -p "${DATA_DIR}"

if [[ ! -f "${PBF_FILE}" ]]; then
  echo "==> Baixando ${PBF_URL} ..."
  curl -L --progress-bar -o "${PBF_FILE}" "${PBF_URL}"
else
  echo "==> PBF já existe: ${PBF_FILE}"
fi

if [[ -f "${OSRM_BASE}.cells" ]]; then
  echo "==> OSRM já processado: ${OSRM_BASE}"
  ln -sf "${REGION}-latest.osrm" "${DATA_DIR}/region.osrm" 2>/dev/null || true
  exit 0
fi

echo "==> Extraindo grafo (pode levar 5–15 min no Mac Mini)..."
docker run --rm -t -v "${DATA_DIR}:/data" osrm/osrm-backend \
  osrm-extract -p /opt/car.lua "/data/${REGION}-latest.osm.pbf"

echo "==> Particionando..."
docker run --rm -t -v "${DATA_DIR}:/data" osrm/osrm-backend \
  osrm-partition "/data/${REGION}-latest.osrm"

echo "==> Customizando..."
docker run --rm -t -v "${DATA_DIR}:/data" osrm/osrm-backend \
  osrm-customize "/data/${REGION}-latest.osrm"

ln -sf "${REGION}-latest.osrm" "${DATA_DIR}/region.osrm" 2>/dev/null || cp "${OSRM_BASE}.fileIndex" /dev/null 2>/dev/null || true

echo "==> Concluído. Reinicie: docker compose up -d osrm"
echo "    Arquivo base: ${OSRM_BASE}"
