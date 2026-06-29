"""Testes de auditoria e export SEI (Fase 4.2 / 4.6)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.security.auth import Role, User
from app.services.audit_service import log_audit, resolve_actor
from app.services.sei_export import build_municipal_sei_package, sha256_file


def test_sha256_file(tmp_path):
    target = tmp_path / "relatorio.pdf"
    target.write_bytes(b"conteudo-teste")
    expected = hashlib.sha256(b"conteudo-teste").hexdigest()
    assert sha256_file(target) == expected


def test_build_municipal_sei_package_with_hash():
    record = MagicMock()
    record.id = 42
    record.codigo_ibge = "2611606"
    record.nome_arquivo = "2611606_20260624.pdf"
    record.tamanho_bytes = 1024
    record.status = "concluido"
    record.sha256_hash = "abc123"
    record.caminho_arquivo = "/data/reports/inexistente.pdf"
    record.gerado_em = datetime(2026, 6, 24, 12, 0, 0)

    muni = MagicMock()
    muni.nome = "Recife"
    muni.uf = "PE"

    package = build_municipal_sei_package(record, muni, base_url="http://localhost:8000")

    assert package["documento_tipo"] == "relatorio_territorial_sinidu"
    assert package["municipio"]["nome"] == "Recife"
    assert package["integridade"]["hash"] == "abc123"
    assert package["urls"]["download_pdf"].endswith("/api/v1/reports/42/download")


def test_resolve_actor_dev_mode(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", False)
    user = resolve_actor(None)
    assert user.username == "dev"
    assert user.role == Role.ADMIN


def test_log_audit_persists(monkeypatch):
    db = MagicMock()
    db.refresh.side_effect = lambda entry: entry

    user = User(username="gestor", role=Role.GESTOR)
    entry = log_audit(
        db,
        user=user,
        action="report.generate",
        resource_type="relatorio_municipal",
        resource_id=7,
        codigo_ibge="2611606",
        metadata={"force": False},
    )

    db.add.assert_called_once()
    db.commit.assert_called_once()
    assert entry.username == "gestor"
    assert entry.action == "report.generate"
    assert entry.codigo_ibge == "2611606"
