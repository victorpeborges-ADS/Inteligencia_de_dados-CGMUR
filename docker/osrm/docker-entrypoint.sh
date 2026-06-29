#!/bin/sh
set -e
REGION="${OSRM_REGION:-pernambuco}"
BASE="/data/${REGION}-latest.osrm"

if [ ! -f "${BASE}" ] && [ ! -f "${BASE}.cells" ]; then
  echo "OSRM: dados não encontrados em ${BASE}"
  echo "Execute: bash docker/osrm/setup-osrm.sh"
  echo "Backend usará fallback geodésico até OSRM estar pronto."
  exec sleep infinity
fi

echo "OSRM: iniciando roteamento ${REGION}..."
exec osrm-routed --algorithm mld "${BASE}"
