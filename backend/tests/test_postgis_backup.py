"""Testes do serviço de backup PostGIS."""

from __future__ import annotations

import gzip
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.postgis_backup import _cleanup_old_backups, _parse_database_url, run_postgis_backup


def test_parse_database_url():
    params = _parse_database_url("postgresql://user:pass@db:5432/sinidu_db")
    assert params["host"] == "db"
    assert params["port"] == "5432"
    assert params["user"] == "user"
    assert params["password"] == "pass"
    assert params["dbname"] == "sinidu_db"


def test_cleanup_old_backups(tmp_path: Path):
    old = tmp_path / "sinidu_postgis_20200101_000000.sql.gz"
    new = tmp_path / "sinidu_postgis_20990101_000000.sql.gz"
    old.write_bytes(b"x")
    new.write_bytes(b"y")
    import os
    import time

    old_time = time.time() - (10 * 86400)
    os.utime(old, (old_time, old_time))
    removed = _cleanup_old_backups(tmp_path, retention_days=7)
    assert removed == 1
    assert not old.exists()
    assert new.exists()


@patch("app.services.postgis_backup.subprocess.Popen")
def test_run_postgis_backup_success(mock_popen, tmp_path: Path):
    sql = b"-- PostgreSQL dump\nCREATE TABLE test (id int);\n"
    proc = MagicMock()
    proc.stdout = iter([sql])
    proc.stderr = MagicMock()
    proc.stderr.read.return_value = b""
    proc.wait.return_value = 0
    mock_popen.return_value.__enter__ = MagicMock(return_value=proc)
    mock_popen.return_value.__exit__ = MagicMock(return_value=False)

    result = run_postgis_backup(
        database_url="postgresql://sinidu_user:sinidu_pass@localhost:5432/sinidu_db",
        backup_dir=str(tmp_path),
        retention_days=0,
    )
    assert result["status"] == "ok"
    outfile = Path(result["path"])
    assert outfile.exists()
    with gzip.open(outfile, "rb") as gz:
        assert b"PostgreSQL dump" in gz.read()


@patch("app.services.postgis_backup.subprocess.Popen")
def test_run_postgis_backup_pg_dump_failure(mock_popen, tmp_path: Path):
    proc = MagicMock()
    proc.stdout = iter([b""])
    proc.stderr = MagicMock()
    proc.stderr.read.return_value = b"connection refused"
    proc.wait.return_value = 1
    mock_popen.return_value.__enter__ = MagicMock(return_value=proc)
    mock_popen.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(RuntimeError, match="pg_dump falhou"):
        run_postgis_backup(
            database_url="postgresql://u:p@localhost:5432/db",
            backup_dir=str(tmp_path),
        )
