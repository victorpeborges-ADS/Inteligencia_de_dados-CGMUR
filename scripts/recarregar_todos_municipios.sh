#!/bin/bash
# Recarga sequencial dos 60 municípios (exceto Recife) — rodar fora do horário de pico.
set -euo pipefail

BASE="${SINIDU_API:-http://localhost:8000}"
MUNICIPIOS_FILE="${1:-scripts/municipios_prioritarios.txt}"

if [ ! -f "$MUNICIPIOS_FILE" ]; then
  echo "Arquivo não encontrado: $MUNICIPIOS_FILE"
  exit 1
fi

while IFS= read -r cod_ibge; do
  [ -z "$cod_ibge" ] && continue
  [[ "$cod_ibge" =~ ^# ]] && continue

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Recarregando $cod_ibge..."
  curl -s -X POST "$BASE/api/v1/municipios/$cod_ibge/recarregar-dados-reais" \
    -H "Content-Type: application/json" \
    -d '{"fontes": ["malha_ibge", "socioeconomico_censo", "s2id", "cemaden", "seguranca_sinesp"]}' > /dev/null

  for i in $(seq 1 120); do
    STATUS=$(curl -sf "$BASE/api/v1/municipios/$cod_ibge/status-recarga" 2>/dev/null \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null \
      || echo "unknown")
    if [ "$STATUS" = "concluido" ] || [ "$STATUS" = "erro" ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] $cod_ibge → $STATUS"
      break
    fi
    sleep 30
  done

  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $cod_ibge concluído. Aguardando 60s..."
  sleep 60
done < "$MUNICIPIOS_FILE"

echo "Recarga completa. Gere o relatório:"
echo "python3 scripts/auditoria_municipios.py --persist"
