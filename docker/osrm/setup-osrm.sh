#!/usr/bin/env bash
# Prepara dados OSRM para roteamento local (Geofabrik Brasil — regiões macro)
# Regiões: nordeste | sudeste | sul | centro-oeste | norte | brazil
# UFs padrão derivam de OSRM_REGION no backend (ou defina OSRM_COVERED_UFS explicitamente)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}"
REGION="${OSRM_REGION:-nordeste}"
VALID_REGIONS="nordeste sudeste sul centro-oeste norte brazil"
DOCKER_MEMORY="${OSRM_DOCKER_MEMORY:-8g}"
if ! echo "${VALID_REGIONS}" | grep -qw "${REGION}"; then
  echo "Região inválida: ${REGION}. Use: ${VALID_REGIONS}"
  exit 1
fi
PBF_URL="https://download.geofabrik.de/south-america/brazil/${REGION}-latest.osm.pbf"
PBF_FILE="${DATA_DIR}/${REGION}-latest.osm.pbf"
OSRM_BASE="${DATA_DIR}/${REGION}-latest.osrm"
MIN_PBF_BYTES=5000000

validate_pbf() {
  local f="$1"
  [[ -f "$f" ]] || return 1
  local size
  size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
  [[ "$size" -ge "$MIN_PBF_BYTES" ]] || return 1
  ! head -c 15 "$f" | grep -q '<!DOCTYPE' 2>/dev/null
}

osrm_docker() {
  docker run --rm -t --memory="${DOCKER_MEMORY}" --memory-swap="${DOCKER_MEMORY}" \
    -v "${DATA_DIR}:/data" osrm/osrm-backend "$@"
}

echo "==> Sinidu+Clima OSRM setup (${REGION})"
echo "    Docker memory limit: ${DOCKER_MEMORY} (ajuste OSRM_DOCKER_MEMORY se OOM/killed 137)"
echo "    Recomendado: Docker Desktop → Resources → Memory ≥ 8 GB"
mkdir -p "${DATA_DIR}"

if [[ -f "${PBF_FILE}" ]] && ! validate_pbf "${PBF_FILE}"; then
  echo "==> PBF inválido ou incompleto — removendo ${PBF_FILE}"
  rm -f "${PBF_FILE}"
fi

if [[ ! -f "${PBF_FILE}" ]]; then
  echo "==> Baixando ${PBF_URL} ..."
  curl -fL --progress-bar -o "${PBF_FILE}.partial" "${PBF_URL}"
  mv "${PBF_FILE}.partial" "${PBF_FILE}"
  validate_pbf "${PBF_FILE}" || {
    echo "Erro: download não parece um PBF válido (>5 MB, não HTML)."
    rm -f "${PBF_FILE}"
    exit 1
  }
else
  echo "==> PBF já existe: ${PBF_FILE}"
fi

if [[ -f "${OSRM_BASE}.cells" ]]; then
  echo "==> OSRM já processado: ${OSRM_BASE}"
  ln -sf "${REGION}-latest.osrm" "${DATA_DIR}/region.osrm" 2>/dev/null || true
  exit 0
fi

if [[ -f "${OSRM_BASE}" || -f "${OSRM_BASE}.names" ]] && [[ ! -f "${OSRM_BASE}.ebg" ]]; then
  echo "==> Artefatos parciais detectados (extract incompleto) — limpando ${REGION}-latest.osrm*"
  rm -f "${DATA_DIR}/${REGION}-latest.osrm"*
fi

echo "==> Extraindo grafo (pode levar 10–25 min no Mac Mini para nordeste)..."
osrm_docker osrm-extract -p /opt/car.lua "/data/${REGION}-latest.osm.pbf"

echo "==> Particionando..."
osrm_docker osrm-partition "/data/${REGION}-latest.osrm"

echo "==> Customizando..."
osrm_docker osrm-customize "/data/${REGION}-latest.osrm"

ln -sf "${REGION}-latest.osrm" "${DATA_DIR}/region.osrm" 2>/dev/null || true

echo "==> Concluído. Reinicie: docker compose up -d osrm"
echo "    Arquivo base: ${OSRM_BASE}"
