#!/usr/bin/env bash
# Backup manual do PostGIS — usa DATABASE_URL ou argumentos padrão Docker.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql://sinidu_user:sinidu_pass@localhost:5432/sinidu_db}"
export BACKUP_DIR="${BACKUP_DIR:-${ROOT}/data/backups}"
export BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

mkdir -p "$BACKUP_DIR"

cd "${ROOT}/backend"
python3 - <<'PY'
from app.services.postgis_backup import run_postgis_backup
import json
print(json.dumps(run_postgis_backup(), ensure_ascii=False, indent=2))
PY

echo "Backup salvo em: $BACKUP_DIR"
