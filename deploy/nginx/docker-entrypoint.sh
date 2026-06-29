#!/bin/sh
set -eu

if [ ! -f /etc/nginx/certs/fullchain.pem ] || [ ! -f /etc/nginx/certs/privkey.pem ]; then
  echo "nginx: certificados TLS ausentes em /etc/nginx/certs/" >&2
  echo "  Esperado: fullchain.pem + privkey.pem" >&2
  exit 1
fi

exec nginx -g 'daemon off;'
