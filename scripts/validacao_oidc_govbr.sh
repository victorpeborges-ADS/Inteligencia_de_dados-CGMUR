#!/usr/bin/env bash
# Valida stack de homologação/produção: TLS, OIDC, auth e API.
# Uso: ./scripts/validacao_oidc_govbr.sh [https://localhost]
set -euo pipefail

BASE="${1:-https://localhost}"
BASE="${BASE%/}"
FAIL=0

check() {
  local label="$1"
  local url="$2"
  local expect="${3:-200}"
  local code
  code=$(curl -sk -o /tmp/sinidu_oidc_chk.json -w "%{http_code}" --max-time 15 "$url" 2>/dev/null || echo "000")
  if [[ "$code" == "$expect" ]]; then
    echo "[OK] $label (HTTP $code)"
  else
    echo "[FAIL] $label (HTTP $code, esperado $expect)"
    FAIL=1
  fi
}

echo "=== Validação OIDC/TLS — $BASE ==="
echo ""

check "health/live" "$BASE/health/live"
check "health/ready" "$BASE/health/ready"

code=$(curl -sk -o /tmp/sinidu_oidc_meta.json -w "%{http_code}" --max-time 15 "$BASE/health/oidc" 2>/dev/null || echo "000")
if [[ "$code" == "200" ]]; then
  status=$(python3 -c "import json; d=json.load(open('/tmp/sinidu_oidc_meta.json')); print(d.get('status','?'))" 2>/dev/null || echo "?")
  if [[ "$status" == "ok" ]]; then
    echo "[OK] health/oidc (IdP acessível)"
  elif [[ "$status" == "disabled" ]]; then
    echo "[INFO] health/oidc — OIDC desligado (OIDC_ENABLED=false)"
  else
    echo "[FAIL] health/oidc — status=$status"
    python3 -m json.tool /tmp/sinidu_oidc_meta.json 2>/dev/null | head -12 || true
    FAIL=1
  fi
else
  echo "[FAIL] health/oidc (HTTP $code)"
  FAIL=1
fi

code=$(curl -sk -o /tmp/sinidu_tls_meta.json -w "%{http_code}" --max-time 15 "$BASE/health/tls" 2>/dev/null || echo "000")
if [[ "$code" == "200" ]]; then
  tls_status=$(python3 -c "import json; d=json.load(open('/tmp/sinidu_tls_meta.json')); print(d.get('status','?'))" 2>/dev/null || echo "?")
  days=$(python3 -c "import json; d=json.load(open('/tmp/sinidu_tls_meta.json')); print(d.get('days_until_expiry','?'))" 2>/dev/null || echo "?")
  echo "[OK] health/tls status=$tls_status dias_restantes=$days"
elif [[ "$code" == "503" ]]; then
  echo "[WARN] health/tls — certificado inválido ou expirado"
  FAIL=1
else
  echo "[INFO] health/tls HTTP $code (TLS pode estar no balanceador)"
fi

# Login OIDC deve redirecionar (302) quando configurado
code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 15 "$BASE/api/v1/auth/oidc/login" 2>/dev/null || echo "000")
if [[ "$code" == "302" || "$code" == "307" ]]; then
  echo "[OK] auth/oidc/login redireciona (HTTP $code)"
elif [[ "$code" == "503" || "$code" == "400" ]]; then
  echo "[INFO] auth/oidc/login HTTP $code — OIDC não configurado ou IdP offline"
else
  echo "[WARN] auth/oidc/login HTTP $code"
fi

check "API docs" "$BASE/api/v1/docs" "200"

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "Resultado: OK — stack pronta para teste SSO manual no frontend."
  echo "Próximo: login via botão SSO e validar role/tenant em /auditoria (admin)."
  exit 0
fi
echo "Resultado: $FAIL falha(s). Verifique homolog-up.sh ou .env.govbr."
exit 1
