#!/usr/bin/env bash
# Prepara dados OSRM para roteamento local (Geofabrik Brasil — regiões macro)
# Regiões: nordeste | sudeste | sul | centro-oeste | norte | brazil | pe-se (demo Recife+Aracaju)
# UFs padrão derivam de OSRM_REGION no backend (ou defina OSRM_COVERED_UFS explicitamente)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}"
REGION="${OSRM_REGION:-pe-se}"
VALID_REGIONS="nordeste sudeste sul centro-oeste norte brazil pe-se"
DOCKER_MEMORY="${OSRM_DOCKER_MEMORY:-8g}"

if ! echo "${VALID_REGIONS}" | grep -qw "${REGION}"; then
  echo "Região inválida: ${REGION}. Use: ${VALID_REGIONS}"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Erro: Docker não está em execução. Abra o Docker Desktop e tente novamente."
  exit 1
fi

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

download_pbf() {
  local url="$1"
  local dest="$2"
  echo "==> Baixando ${url} ..."
  curl -fL --progress-bar -o "${dest}.partial" "${url}"
  mv "${dest}.partial" "${dest}"
  validate_pbf "${dest}" || {
    echo "Erro: download não parece um PBF válido (>5 MB, não HTML)."
    rm -f "${dest}"
    exit 1
  }
}

echo "==> Sinidu+Clima OSRM setup (${REGION})"
echo "    Docker memory limit: ${DOCKER_MEMORY} (ajuste OSRM_DOCKER_MEMORY se OOM/killed 137)"
echo "    Recomendado: Docker Desktop → Resources → Memory ≥ 8 GB"
mkdir -p "${DATA_DIR}"

if [[ "${REGION}" == "pe-se" ]]; then
  PE_FILE="${DATA_DIR}/pernambuco-latest.osm.pbf"
  SE_FILE="${DATA_DIR}/sergipe-latest.osm.pbf"
  PE_URL="https://download.openstreetmap.fr/extracts/south-america/brazil/northeast/pernambuco-latest.osm.pbf"
  SE_URL="https://download.openstreetmap.fr/extracts/south-america/brazil/northeast/sergipe-latest.osm.pbf"

  if [[ ! -f "${PE_FILE}" ]]; then
    download_pbf "${PE_URL}" "${PE_FILE}"
  else
    echo "==> Pernambuco PBF já existe: ${PE_FILE}"
  fi
  if [[ ! -f "${SE_FILE}" ]]; then
    download_pbf "${SE_URL}" "${SE_FILE}"
  else
    echo "==> Sergipe PBF já existe: ${SE_FILE}"
  fi

  if [[ ! -f "${PBF_FILE}" ]] || ! validate_pbf "${PBF_FILE}"; then
    echo "==> Mesclando PE + SE (~80 MB) para demo Recife/Aracaju..."
    if command -v osmium >/dev/null 2>&1; then
      osmium merge \
        "${PE_FILE}" \
        "${SE_FILE}" \
        -o "${PBF_FILE}" \
        --overwrite
    else
      docker run --rm -v "${DATA_DIR}:/data" ghcr.io/osmcode/osmium-tool \
        osmium merge \
        "/data/pernambuco-latest.osm.pbf" \
        "/data/sergipe-latest.osm.pbf" \
        -o "/data/pe-se-latest.osm.pbf" \
        --overwrite
    fi
    validate_pbf "${PBF_FILE}" || {
      echo "Erro: merge PE+SE falhou. Instale osmium-tool (brew install osmium-tool) ou verifique Docker."
      exit 1
    }
  else
    echo "==> PBF demo PE+SE já existe: ${PBF_FILE}"
  fi
else
  PBF_URL="https://download.geofabrik.de/south-america/brazil/${REGION}-latest.osm.pbf"
  if [[ -f "${PBF_FILE}" ]] && ! validate_pbf "${PBF_FILE}"; then
    echo "==> PBF inválido ou incompleto — removendo ${PBF_FILE}"
    rm -f "${PBF_FILE}"
  fi
  if [[ ! -f "${PBF_FILE}" ]]; then
    download_pbf "${PBF_URL}" "${PBF_FILE}"
  else
    echo "==> PBF já existe: ${PBF_FILE}"
  fi
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

echo "==> Extraindo grafo (pe-se ~3–8 min; nordeste ~10–25 min no Mac Mini)..."
osrm_docker osrm-extract -p /opt/car.lua "/data/${REGION}-latest.osm.pbf"

echo "==> Particionando..."
osrm_docker osrm-partition "/data/${REGION}-latest.osrm"

echo "==> Customizando..."
osrm_docker osrm-customize "/data/${REGION}-latest.osrm"

ln -sf "${REGION}-latest.osrm" "${DATA_DIR}/region.osrm" 2>/dev/null || true

echo "==> Concluído. Reinicie: docker compose up -d osrm"
echo "    Arquivo base: ${OSRM_BASE}"
