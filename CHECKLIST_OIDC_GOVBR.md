# Checklist — OIDC gov.br produção (D.2)

> **Status no protótipo (jul/2026):** ➖ **fora de escopo**. O MVP usa Keycloak local e/ou login por senha.  
> Este checklist só vale se o MCID pedir gov.br depois — não bloqueia demo.

**Objetivo (futuro):** migrar de Keycloak local para **gov.br / IdP institucional MCID**.  
**Pré-requisito:** homologação local validada com `./scripts/homolog-up.sh` + `./scripts/validacao_oidc_govbr.sh`.

## 1. Credenciais e cadastro no IdP

- [ ] Solicitar **client OAuth2/OIDC** no ambiente gov.br (staging → produção)
- [ ] Registrar **redirect URI** exata: `https://<dominio>/api/v1/auth/oidc/callback`
- [ ] Obter `client_id` e `client_secret` (armazenar em cofre — nunca no git)
- [ ] Confirmar scopes: `openid profile email govbr_confiabilidades`
- [ ] Mapear grupos/claims → roles Sinidu (`admin`, `gestor_municipal`, `leitor`)

## 2. Variáveis de ambiente (`.env` produção)

Copie `.env.govbr.example` e ajuste:

```bash
OIDC_ENABLED=true
OIDC_ISSUER_URL=https://sso.acesso.gov.br   # confirmar URL vigente com DTI
OIDC_CLIENT_ID=...
OIDC_CLIENT_SECRET=...
OIDC_REDIRECT_URI=https://sinidu.cidades.gov.br/api/v1/auth/oidc/callback
OIDC_FRONTEND_REDIRECT=https://sinidu.cidades.gov.br/
OIDC_SCOPES=openid profile email govbr_confiabilidades
AUTH_PASSWORD_LOGIN_ENABLED=false
MULTI_TENANT_ENABLED=true
TRUST_PROXY_HEADERS=true
```

Claims de tenant (se o IdP expuser):

```bash
OIDC_TENANT_UF_CLAIM=tenant_uf
OIDC_TENANT_IBGE_CLAIM=tenant_ibge
```

## 3. TLS e certificado MCID

- [ ] Instalar par `fullchain.pem` + `privkey.pem` em `deploy/nginx/certs/`
- [ ] Rodar `./scripts/validate-tls-certs.sh` (sem `ALLOW_DEV_CERT`)
- [ ] Subir: `./scripts/prod-up.sh .env`
- [ ] Validar `GET /health/tls` — status `ok`, expiração > 14 dias

## 4. Smoke automatizado pós-deploy

```bash
chmod +x scripts/validacao_oidc_govbr.sh
./scripts/validacao_oidc_govbr.sh https://sinidu.cidades.gov.br

# Piloto territorial (com API no ar)
RUN_PILOTO_VALIDATION=1 RUN_OSRM_VALIDATION=1 ./scripts/demo-smoke.sh https://sinidu.cidades.gov.br
```

## 5. Teste manual SSO

| # | Ação | Esperado |
|---|------|----------|
| 1 | Abrir app → **Entrar com SSO** | Redirect gov.br / IdP MCID |
| 2 | Login com conta gestor PE | JWT emitido; municípios PE visíveis |
| 3 | Login com conta leitor | Escopo restrito por UF/IBGE |
| 4 | `/auditoria` (admin) | Evento `auth.oidc_login` registrado |
| 5 | Logout / nova sessão | Token renovado sem erro CORS |

## 6. Rollback

- Manter `AUTH_PASSWORD_LOGIN_ENABLED=true` temporariamente em staging
- Keycloak local: `docker compose -f docker-compose.oidc.yml up -d` para homologação offline
- Documentar issuer anterior em runbook de incidente

## Referências

- [deploy/README.md](deploy/README.md) — perfis homolog/produção
- [.env.govbr.example](.env.govbr.example) — template de variáveis
- [ROADMAP.md](ROADMAP.md) — item **D.2**
- Gov.br Identidade: https://www.gov.br/governodigital/pt-br/identidade
