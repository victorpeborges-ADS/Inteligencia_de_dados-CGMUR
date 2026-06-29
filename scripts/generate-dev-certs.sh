#!/usr/bin/env bash
# Certificado autoassinado para homologação local com TLS (não usar em produção MCID).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="$ROOT/deploy/nginx/certs"
mkdir -p "$CERT_DIR"

if [[ -f "$CERT_DIR/fullchain.pem" && -f "$CERT_DIR/privkey.pem" ]]; then
  echo "Certificados já existem em $CERT_DIR — remova manualmente para regenerar."
  exit 0
fi

openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout "$CERT_DIR/privkey.pem" \
  -out "$CERT_DIR/fullchain.pem" \
  -subj "/CN=localhost/O=Sinidu Clima Homolog/C=BR" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "$CERT_DIR/privkey.pem"
echo "Certificados gerados em $CERT_DIR"
echo "  fullchain.pem / privkey.pem"
