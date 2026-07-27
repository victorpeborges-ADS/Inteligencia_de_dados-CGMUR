"""Testes do adapter MCP (20c) — sem depender do pacote mcp instalado."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.mcp.auth_gate import McpAuthError, assert_read_only_tool, resolve_mcp_user
from app.mcp.tools_impl import TOOL_NAMES, run_tool


def test_tool_names_are_read_only():
    assert len(TOOL_NAMES) >= 6
    for name in TOOL_NAMES:
        assert_read_only_tool(name)
        assert not name.startswith(("activate_", "sync_", "generate_", "bootstrap_"))


def test_assert_read_only_blocks_writes():
    with pytest.raises(McpAuthError):
        assert_read_only_tool("activate_contingency")
    with pytest.raises(McpAuthError):
        assert_read_only_tool("generate_diagnostic")


def test_resolve_user_requires_auth(monkeypatch):
    monkeypatch.delenv("SINIDU_MCP_TOKEN", raising=False)
    monkeypatch.delenv("SINIDU_MCP_JWT", raising=False)
    monkeypatch.delenv("SINIDU_MCP_ALLOW_ANON", raising=False)
    with pytest.raises(McpAuthError):
        resolve_mcp_user()


def test_resolve_user_static_token(monkeypatch):
    monkeypatch.setenv("SINIDU_MCP_TOKEN", "secret-team")
    monkeypatch.delenv("SINIDU_MCP_ALLOW_ANON", raising=False)
    user = resolve_mcp_user(token="secret-team")
    assert user.username == "mcp_team"


def test_resolve_user_anon_for_tests(monkeypatch):
    monkeypatch.delenv("SINIDU_MCP_TOKEN", raising=False)
    monkeypatch.delenv("SINIDU_MCP_JWT", raising=False)
    monkeypatch.setenv("SINIDU_MCP_ALLOW_ANON", "1")
    user = resolve_mcp_user()
    assert user.username == "mcp_anon"


def test_run_tool_unknown(monkeypatch):
    monkeypatch.setenv("SINIDU_MCP_ALLOW_ANON", "1")
    out = run_tool("totally_unknown_tool", {})
    assert out["error_code"] == "unknown_tool"


def test_run_tool_forbidden_write(monkeypatch):
    monkeypatch.setenv("SINIDU_MCP_ALLOW_ANON", "1")
    out = run_tool("write_something", {})
    assert out["error_code"] == "forbidden_tool"


def test_run_tool_auth_error(monkeypatch):
    monkeypatch.delenv("SINIDU_MCP_TOKEN", raising=False)
    monkeypatch.delenv("SINIDU_MCP_JWT", raising=False)
    monkeypatch.delenv("SINIDU_MCP_ALLOW_ANON", raising=False)
    out = run_tool("live_alert", {"codigo_ibge": "2611606"})
    assert out["error_code"] == "auth_error"


@patch("app.mcp.tools_impl.live_alert")
def test_run_tool_dispatches(mock_live, monkeypatch):
    monkeypatch.setenv("SINIDU_MCP_ALLOW_ANON", "1")
    mock_live.return_value = {
        "codigo_ibge": "2611606",
        "nivel_alerta": "VERDE",
        "interpretacao": "sem_alerta_monitorado",
        "read_only": True,
    }
    out = run_tool("live_alert", {"codigo_ibge": "2611606"})
    assert out["nivel_alerta"] == "VERDE"
    assert out.get("error_code") is None
    mock_live.assert_called_once()


@patch("app.mcp.tools_impl._with_access")
def test_flood_status_no_bootstrap(mock_access, monkeypatch):
    monkeypatch.setenv("SINIDU_MCP_ALLOW_ANON", "1")
    # flood_model_status uses resolve + SessionLocal, not always _with_access
    with patch("app.mcp.tools_impl.resolve_mcp_user") as mock_user, patch(
        "app.mcp.tools_impl._session"
    ) as mock_sess, patch("ml.paths.model_path") as mock_path, patch(
        "ml.model_policy.load_model_meta", return_value={}
    ):
        mock_user.return_value = MagicMock(username="t", role="leitor")
        db = MagicMock()
        mock_sess.return_value = db
        mock_path.return_value.exists.return_value = False
        out = run_tool("flood_model_status", {})
    assert out["read_only"] is True
    assert "bootstrap" not in (out.get("note") or "").lower() or "não" in (out.get("note") or "").lower()
    assert out["protocol"] == "20c1_mcp_flood_status"
