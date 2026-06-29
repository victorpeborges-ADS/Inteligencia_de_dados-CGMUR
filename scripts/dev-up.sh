#!/usr/bin/env bash
# Dev local — auth off, hot-reload, http://localhost:3000
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
echo "Dev: http://localhost:3000  |  API: http://localhost:8000"
