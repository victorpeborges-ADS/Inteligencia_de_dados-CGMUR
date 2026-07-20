"""Fixtures globais — paths graváveis fora do volume Docker /data."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def pytest_configure(config) -> None:  # noqa: ARG001
    root = Path(tempfile.mkdtemp(prefix="sinidu_pytest_"))
    dem = root / "dem"
    local = dem / "local"
    reports = root / "reports"
    dem.mkdir(parents=True, exist_ok=True)
    local.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DEM_DIR", str(dem))
    os.environ.setdefault("LOCAL_DEM_DIR", str(local))
    os.environ.setdefault("REPORTS_DIR", str(reports))
    os.environ.setdefault("MODELS_DIR", str(root / "models"))
    os.environ.setdefault("ML_DATA_DIR", str(root / "ml"))
    os.environ.setdefault("BACKUP_DIR", str(root / "backups"))
    for sub in ("models", "ml", "backups"):
        (root / sub).mkdir(exist_ok=True)


def _postgres_available() -> bool:
    try:
        import psycopg2

        dsn = os.environ.get(
            "DATABASE_URL",
            "postgresql://sinidu_user:sinidu_pass@localhost:5432/sinidu_db",
        )
        conn = psycopg2.connect(dsn, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


requires_postgres = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL indisponível (suba o stack Docker ou rode no CI)",
)
