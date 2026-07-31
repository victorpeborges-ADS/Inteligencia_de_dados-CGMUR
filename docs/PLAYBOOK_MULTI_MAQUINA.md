# Playbook multi-máquina — Mac ↔ Windows ↔ Dev Tunnel (Fase 20f.3)

Guia curto para a equipe manter o mesmo ambiente entre máquinas e expor a API via Dev Tunnel.

## 1. Pré-requisitos

| Item | Mac | Windows |
|------|-----|---------|
| Docker Desktop | ✅ | ✅ (WSL2 backend) |
| Git | ✅ | ✅ |
| Porta livre | `3000`, `8000`, `5432` | idem |
| RAM sugerida | ≥ 8 GB para compose completo | idem |

Clone:

```bash
git clone <repo-url> "sinidu mvp"
cd "sinidu mvp"
```

## 2. Subir o stack (dev)

```bash
git pull
docker compose down
docker compose up -d --build
```

Cheque:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/integrations/status
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
```

Esperado: `200` (ou `401` se auth ligada — ainda assim API viva).

Logs:

```bash
docker compose logs -f backend --tail=80
```

## 3. Após `git pull` (checklist)

1. `docker compose up -d --build` se `Dockerfile`, `requirements.txt` ou `frontend/package.json` mudaram
2. Rodar migrações se o entrypoint não rodou: ver logs do backend
3. No browser: hard refresh (`Cmd/Ctrl+Shift+R`)
4. Confirmar município piloto (ex.: Recife `2611606`) carrega mapa + Monitor

## 4. Dev Tunnel (API pública temporária)

Objetivo: outro membro / demo acessar a API sem VPN.

### Mac / Linux (devtunnel CLI ou VS Code)

```bash
# Exemplo com `devtunnel` (instale a CLI da Microsoft)
devtunnel host -p 8000 --allow-anonymous
```

Anote a URL HTTPS gerada (ex.: `https://xxxx.devtunnels.ms`).

### Windows

Mesmo CLI no PowerShell, ou **Ports** do VS Code/Cursor → Forward `8000` → “Port Visibility: Public”.

### Checagem da API pública

```bash
TUNNEL=https://SEU-HOST.devtunnels.ms
curl -sS "$TUNNEL/api/v1/integrations/status" | head
curl -sS -o /dev/null -w "%{http_code}\n" "$TUNNEL/docs"
```

**Cuidados (20a.2):**

- Não use senhas default em tunnel com auth ligada
- CORS: se o frontend remoto chamar o tunnel, inclua a origem em `CORS_ORIGINS`
- Desligue o tunnel após a demo

Frontend apontando para o tunnel: configure `NEXT_PUBLIC_API_URL` (ou equivalente do compose) para a URL do tunnel e rebuild do frontend.

## 5. Diff Mac ↔ Windows

| Tema | Nota |
|------|------|
| Paths | Evitar paths com espaços sem aspas (`"sinidu mvp"`) |
| Line endings | `git config core.autocrlf input` no Windows ajuda |
| Performance | WSL2: projeto preferencialmente dentro do filesystem Linux |
| File watchers | Se hot-reload falhar no Windows, restart do serviço `frontend` |

## 6. Smoke mínimo pós-tunnel

- [ ] `GET /api/v1/integrations/status`
- [ ] `GET /api/v1/monitoring/dashboard/2611606`
- [ ] Login (se `AUTH_ENABLED=true`)
- [ ] Abrir mapa no browser via frontend local ou URL publicada

## Referências

- Deploy/homologação: `deploy/README.md`
- MCP equipe (Cursor): `docs/MCP_EQUIPE.md`
- Estado do produto: `documentacao/ESTADO_ATUAL_SINIDU.md`
