#!/bin/sh
set -e

# Volume anônimo de node_modules pode ficar desatualizado após mudanças no package.json.
if [ ! -f node_modules/.package-lock.sha ] || ! cmp -s package-lock.json node_modules/.package-lock.sha 2>/dev/null; then
  echo "[frontend] Sincronizando dependências npm…"
  npm install
  cp package-lock.json node_modules/.package-lock.sha 2>/dev/null || true
fi

exec npm run dev -- -H 0.0.0.0 -p 3000
