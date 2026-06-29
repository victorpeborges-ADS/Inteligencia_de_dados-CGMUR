#!/usr/bin/env bash
# Valida certificados TLS institucionais antes do deploy MCID.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="${TLS_CERT_DIR:-$ROOT/deploy/nginx/certs}"
FULLCHAIN="${TLS_FULLCHAIN:-$CERT_DIR/fullchain.pem}"
PRIVKEY="${TLS_PRIVKEY:-$CERT_DIR/privkey.pem}"
MIN_DAYS="${TLS_MIN_DAYS:-14}"

fail() {
  echo "TLS: $1" >&2
  exit 1
}

[[ -f "$FULLCHAIN" ]] || fail "fullchain não encontrado: $FULLCHAIN"
[[ -f "$PRIVKEY" ]] || fail "privkey não encontrado: $PRIVKEY"

if ! openssl x509 -in "$FULLCHAIN" -noout >/dev/null 2>&1; then
  fail "fullchain.pem inválido"
fi

if ! openssl rsa -in "$PRIVKEY" -check -noout >/dev/null 2>&1 \
  && ! openssl ec -in "$PRIVKEY" -check -noout >/dev/null 2>&1; then
  fail "privkey.pem inválido ou senha protegida (use PEM sem passphrase)"
fi

# Certificado deve corresponder à chave
PUB1=$(openssl x509 -in "$FULLCHAIN" -noout -pubkey 2>/dev/null | openssl md5)
PUB2=$(openssl pkey -in "$PRIVKEY" -pubout 2>/dev/null | openssl md5)
[[ "$PUB1" == "$PUB2" ]] || fail "fullchain e privkey não formam par válido"

SUBJECT=$(openssl x509 -in "$FULLCHAIN" -noout -subject 2>/dev/null | sed 's/subject=//')
NOT_AFTER=$(openssl x509 -in "$FULLCHAIN" -noout -enddate 2>/dev/null | cut -d= -f2)
EXPIRY_EPOCH=$(date -j -f "%b %d %T %Y %Z" "$NOT_AFTER" +%s 2>/dev/null || date -d "$NOT_AFTER" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

echo "Certificado OK"
echo "  Subject: $SUBJECT"
echo "  Expira:  $NOT_AFTER ($DAYS_LEFT dias)"

if [[ "$DAYS_LEFT" -lt "$MIN_DAYS" ]]; then
  fail "certificado expira em menos de $MIN_DAYS dias"
fi

if openssl x509 -in "$FULLCHAIN" -noout -issuer 2>/dev/null | grep -qi "Sinidu Clima Homolog"; then
  echo "AVISO: certificado autoassinado de homologação — não use em produção MCID." >&2
  if [[ "${ALLOW_DEV_CERT:-false}" != "true" ]]; then
    fail "defina ALLOW_DEV_CERT=true para homolog local ou instale certificado MCID"
  fi
fi
