# MCP Sinidu — uso pela equipe (Fase 20c)

Adapter **read-only** para Cursor / Claude Desktop. **Não** é o runtime do painel web do município.

## O que expõe

| Tool | Função |
|------|--------|
| `municipio_overview` | Painel de risco unificado + perfil |
| `layers_catalog_summary` | Cobertura/catálogo (leve) |
| `diagnostic_latest` | Último diagnóstico **já gerado** (não cria) |
| `monitoring_snapshot` | Clima + selo de previsão + alerta vivo |
| `flood_model_status` | Status ML (não treina/bootstrap) |
| `catalog_gaps` | Maturidade e lacunas |
| `live_alert` | Alerta 24h (VERDE ≠ “seguro”) |

Resource: `sinidu://limits` — limites e política.

## O que **não** faz

- Ativar contingência / disseminar alerta / sync de fontes
- Gerar diagnóstico novo / treinar ML / exportar writes
- Substituir a UI do Sinidu para o gestor municipal

## Instalação (host da equipe)

```bash
cd backend
python3 -m venv .venv-mcp
source .venv-mcp/bin/activate
pip install -r requirements.txt -r requirements-mcp.txt
```

Requer `DATABASE_URL` apontando para o Postgres do ambiente (local Docker ou remoto).

## Auth (20c.2)

| Variável | Uso |
|----------|-----|
| `SINIDU_MCP_TOKEN` | Secret compartilhado da equipe (recomendado no Cursor) |
| `SINIDU_MCP_JWT` | JWT emitido por `POST /api/v1/auth/login` |
| `token` (arg da tool) | Mesmo JWT/secret por chamada |
| `SINIDU_MCP_RATE_LIMIT_PER_MIN` | Default `60` |
| `SINIDU_MCP_ALLOW_ANON=1` | **Só testes** — sem auth |

Com multi-tenant ligado, JWT respeita `tenant_uf` / `tenant_ibge`.

## Cursor (`mcp.json`)

```json
{
  "mcpServers": {
    "sinidu": {
      "command": "python3",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/ABS/PATH/sinidu mvp/backend",
      "env": {
        "DATABASE_URL": "postgresql://sinidu_user:sinidu_pass@localhost:5432/sinidu_db",
        "SINIDU_MCP_TOKEN": "troque-este-secret",
        "AUTH_JWT_SECRET": "mesmo-secret-do-backend-se-usar-JWT",
        "PYTHONPATH": "/ABS/PATH/sinidu mvp/backend"
      }
    }
  }
}
```

Substitua o path absoluto. No macOS, se usar o venv:

```json
"command": "/ABS/PATH/sinidu mvp/backend/.venv-mcp/bin/python",
"args": ["-m", "app.mcp.server"]
```

## Teste rápido

```bash
cd backend
SINIDU_MCP_ALLOW_ANON=1 PYTHONPATH=. python3 -c "
from app.mcp.tools_impl import run_tool
print(run_tool('flood_model_status', {}))
"
```

## Honestidade

Simulações e scores heuristicos = **triagem** (selo Estimado/Derivado/Observado). Não são laudo, HEC-RAS nem alerta oficial CEMADEN. Ver `docs/CHECKLIST_LINGUAGEM_HONESTIDADE.md`.
