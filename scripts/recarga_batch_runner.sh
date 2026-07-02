#!/bin/bash
# Runner resiliente para batch de recarga (executar via nohup ou docker exec -d).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BASE="${SINIDU_API:-http://localhost:8000}"
MUNICIPIOS_FILE="${1:-/tmp/municipios_restantes.txt}"
LOG="${2:-recarga_batch_20260702_1219.log}"

while IFS= read -r cod_ibge; do
  [ -z "$cod_ibge" ] && continue
  [[ "$cod_ibge" =~ ^# ]] && continue

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Recarregando $cod_ibge..." | tee -a "$LOG"
  curl -sf -X POST "$BASE/api/v1/municipios/$cod_ibge/recarregar-dados-reais" \
    -H "Content-Type: application/json" \
    -d '{"fontes": ["malha_ibge", "socioeconomico_censo", "s2id", "cemaden", "seguranca_sinesp"]}' \
    >/dev/null 2>&1 || echo "[$(date '+%Y-%m-%d %H:%M:%S')] POST falhou $cod_ibge" | tee -a "$LOG"

  for _ in $(seq 1 120); do
    STATUS=$(curl -sf "$BASE/api/v1/municipios/$cod_ibge/status-recarga" 2>/dev/null \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null \
      || echo "unknown")
    if [ "$STATUS" = "concluido" ] || [ "$STATUS" = "erro" ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] $cod_ibge → $STATUS" | tee -a "$LOG"
      break
    fi
    sleep 30
  done

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $cod_ibge aguardando 60s..." | tee -a "$LOG"
  sleep 60
done < "$MUNICIPIOS_FILE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Recarga completa." | tee -a "$LOG"
