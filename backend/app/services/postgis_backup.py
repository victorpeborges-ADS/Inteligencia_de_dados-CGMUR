from __future__ import annotations

import gzip
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.observability.metrics import record_backup

logger = logging.getLogger(__name__)


def _parse_database_url(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "sinidu_user",
        "password": parsed.password or "",
        "dbname": (parsed.path or "/sinidu_db").lstrip("/"),
    }


def run_postgis_backup(
    *,
    database_url: str | None = None,
    backup_dir: str | None = None,
    retention_days: int | None = None,
) -> dict[str, Any]:
    db_url = database_url or os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL não configurada.")

    target_dir = Path(backup_dir or os.getenv("BACKUP_DIR", "/data/backups"))
    target_dir.mkdir(parents=True, exist_ok=True)
    keep_days = retention_days or int(os.getenv("BACKUP_RETENTION_DAYS", "7"))

    params = _parse_database_url(db_url)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    outfile = target_dir / f"sinidu_postgis_{stamp}.sql.gz"

    env = os.environ.copy()
    if params["password"]:
        env["PGPASSWORD"] = params["password"]

    cmd = [
        "pg_dump",
        "-h",
        params["host"],
        "-p",
        params["port"],
        "-U",
        params["user"],
        "-d",
        params["dbname"],
        "--no-owner",
        "--no-acl",
        "-F",
        "p",
    ]

    try:
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) as proc:
            assert proc.stdout is not None
            with gzip.open(outfile, "wb") as gz:
                gz.writelines(proc.stdout)
            stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            code = proc.wait(timeout=600)
        if code != 0:
            outfile.unlink(missing_ok=True)
            record_backup(False)
            raise RuntimeError(f"pg_dump falhou ({code}): {stderr.strip()}")

        removed = _cleanup_old_backups(target_dir, keep_days)
        size_bytes = outfile.stat().st_size
        record_backup(True)
        logger.info(
            "Backup PostGIS concluído: %s (%s bytes, %s arquivo(s) removido(s))",
            outfile,
            size_bytes,
            removed,
        )
        return {
            "status": "ok",
            "path": str(outfile),
            "size_bytes": size_bytes,
            "removed_old": removed,
        }
    except FileNotFoundError as exc:
        record_backup(False)
        raise RuntimeError("pg_dump não encontrado no PATH.") from exc
    except Exception:
        record_backup(False)
        raise


def _cleanup_old_backups(directory: Path, retention_days: int) -> int:
    if retention_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc).timestamp() - (retention_days * 86400)
    removed = 0
    for path in directory.glob("sinidu_postgis_*.sql.gz"):
        if path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed
