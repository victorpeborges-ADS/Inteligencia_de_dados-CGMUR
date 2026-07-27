"""Servidor MCP Sinidu — adapter read-only para a equipe (Fase 20c).

Uso (stdio):
  cd backend && SINIDU_MCP_TOKEN=... DATABASE_URL=... python -m app.mcp.server

Ver docs/MCP_EQUIPE.md.
"""

from __future__ import annotations

import logging
import sys

from app.mcp.tools_impl import TOOL_NAMES, run_tool, tool_result_text

logger = logging.getLogger("sinidu.mcp")


def build_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Pacote 'mcp' não instalado. Rode: pip install -r requirements-mcp.txt"
        ) from exc

    mcp = FastMCP("sinidu")

    @mcp.tool()
    def municipio_overview(codigo_ibge: str, token: str | None = None) -> str:
        """Painel de risco unificado + perfil do município (read-only)."""
        return tool_result_text(
            run_tool("municipio_overview", {"codigo_ibge": codigo_ibge, "token": token})
        )

    @mcp.tool()
    def layers_catalog_summary(codigo_ibge: str, token: str | None = None) -> str:
        """Resumo de cobertura/catálogo de dados do município (read-only)."""
        return tool_result_text(
            run_tool(
                "layers_catalog_summary",
                {"codigo_ibge": codigo_ibge, "token": token},
            )
        )

    @mcp.tool()
    def diagnostic_latest(codigo_ibge: str, token: str | None = None) -> str:
        """Último diagnóstico executivo já gerado — não cria novo (read-only)."""
        return tool_result_text(
            run_tool("diagnostic_latest", {"codigo_ibge": codigo_ibge, "token": token})
        )

    @mcp.tool()
    def monitoring_snapshot(codigo_ibge: str, token: str | None = None) -> str:
        """Monitor: chuva, selo de previsão 20e.3 e alerta vivo (read-only)."""
        return tool_result_text(
            run_tool("monitoring_snapshot", {"codigo_ibge": codigo_ibge, "token": token})
        )

    @mcp.tool()
    def flood_model_status(codigo_ibge: str | None = None, token: str | None = None) -> str:
        """Status dos modelos ML de alagamento (não treina/bootstrap)."""
        args: dict = {"token": token}
        if codigo_ibge:
            args["codigo_ibge"] = codigo_ibge
        return tool_result_text(run_tool("flood_model_status", args))

    @mcp.tool()
    def catalog_gaps(codigo_ibge: str, token: str | None = None) -> str:
        """Maturidade informacional e lacunas do catálogo (read-only)."""
        return tool_result_text(
            run_tool("catalog_gaps", {"codigo_ibge": codigo_ibge, "token": token})
        )

    @mcp.tool()
    def live_alert(codigo_ibge: str, token: str | None = None) -> str:
        """Alerta vivo 24h. VERDE sem alerta ≠ município seguro."""
        return tool_result_text(
            run_tool("live_alert", {"codigo_ibge": codigo_ibge, "token": token})
        )

    @mcp.resource("sinidu://limits")
    def limits() -> str:
        """Limites do adapter MCP Sinidu."""
        return (
            "Sinidu MCP — somente leitura.\n"
            f"Tools: {', '.join(TOOL_NAMES)}\n"
            "Não ativa contingência, não dissemina alerta, não sincroniza fontes, "
            "não gera diagnóstico novo, não treina ML.\n"
            "Auth: SINIDU_MCP_TOKEN ou JWT (SINIDU_MCP_JWT / arg token).\n"
            "Rate limit: SINIDU_MCP_RATE_LIMIT_PER_MIN (default 60).\n"
            "Simulações = triagem (selo Derivado/Estimado), não laudo."
        )

    return mcp


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    mcp = build_mcp()
    logger.info("Sinidu MCP starting (stdio) tools=%s", ",".join(TOOL_NAMES))
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
