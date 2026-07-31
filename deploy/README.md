# Deploy e homologação — Sinidu+Clima

Guia para subir o sistema em modo **staging/homologação MCID**, com autenticação, multi-tenant, TLS e SSO OIDC.

## Perfis de execução

| Perfil | Comando | Uso |
|--------|---------|-----|
| **Dev** | `docker compose up -d` | Auth off, acesso direto `:3000` / `:8000` |
| **Staging** | `./scripts/deploy-staging.sh` | Auth on, multi-tenant, frontend prod |
| **Proxy HTTP** | `docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.proxy.yml up -d` | Entrada única `:80` |
| **Homologação completa** | `./scripts/homolog-up.sh` | TLS `:443` + Keycloak OIDC local |
| **Produção MCID** | `./scripts/prod-up.sh .env` | Certificado institucional + auth + OIDC |

## Homologação completa (recomendado antes de MCID)

```bash
chmod +x scripts/*.sh
./scripts/homolog-up.sh
```

Isso faz:

1. Gera certificado TLS autoassinado (`deploy/nginx/certs/`)
2. Sobe stack com auth, multi-tenant, nginx HTTPS e Keycloak
3. Importa realm `sinidu` com usuários de teste

### URLs

| Serviço | URL |
|---------|-----|
| Aplicação | https://localhost |
| API | https://localhost/api/v1/ |
| Health OIDC | https://localhost/health/oidc |
| Keycloak Admin | http://localhost:8080 (admin / admin) |

Aceite o aviso de certificado autoassinado no browser.

### Usuários OIDC (realm `sinidu`)

| Usuário | Senha | Role Sinidu | Escopo |
|---------|-------|-------------|--------|
| `admin.sinidu` | `admin` | admin | nacional |
| `gestor.pe` | `gestor` | gestor_municipal | UF PE |
| `leitor.pe` | `leitor` | leitor | UF PE |

Login: botão **Entrar com SSO (OIDC / gov.br)** na modal de autenticação.

### Variáveis (opcional `.env.homolog`)

```bash
AUTH_JWT_SECRET=trocar-min-32-chars
OIDC_CLIENT_SECRET=sinidu-local-secret-change-me
MULTI_TENANT_ENABLED=true
AUTH_GESTOR_TENANT_UF=PE
```

## TLS em produção MCID

### Deploy com certificado institucional

```bash
cp .env.production.example .env
# Edite secrets, URLs e OIDC gov.br

# Instale certificado MCID (ICP-Brasil ou Let's Encrypt via infra)
install -m 644 fullchain.pem deploy/nginx/certs/fullchain.pem
install -m 600 privkey.pem deploy/nginx/certs/privkey.pem

./scripts/prod-up.sh .env
```

O script `validate-tls-certs.sh` verifica:
- Par fullchain + privkey válido
- Expiração mínima (14 dias)
- Rejeita certificado autoassinado de homologação (use `ALLOW_DEV_CERT=true` só em dev)

Monitoramento: `GET /health/tls` e painel **Sistema** → bloco Certificado TLS.

### Homologação local (autoassinado)

```bash
./scripts/generate-dev-certs.sh
ALLOW_DEV_CERT=true ./scripts/validate-tls-certs.sh
./scripts/homolog-up.sh
```

### Balanceador institucional

Alternativa: TLS no balanceador e nginx só na porta 80 — `TRUST_PROXY_HEADERS=true`.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.proxy.yml up -d
```

Headers de segurança (HSTS, X-Frame-Options) em `deploy/nginx/nginx-tls.conf`.

## MapBiomas em produção

1. CSV dos 6 pilotos já vem em `scripts/mapbiomas_stats/municipios_cobertura_pilotos.csv` (Coleção 10.1, DOI SJZOLT).
2. Opcional — XLSX completo em `mapbiomas/` + `python3 scripts/mapbiomas_stats/extrair_pilotos.py`.
3. Monte `./mapbiomas:/data/mapbiomas` (já no compose) e/ou `MAPBIOMAS_STATS_CSV`.
4. Force sync: `POST /api/v1/system/jobs/mapbiomas-batch?force=true`.

## Dev Tunnel / URL pública (20a.2)

Nunca exponha o backend com `AUTH_ENABLED=false`. Checklist:

```bash
AUTH_ENABLED=true
AUTH_JWT_SECRET=<aleatório >=32 chars>
AUTH_ADMIN_PASSWORD=<não-admin>
AUTH_GESTOR_PASSWORD=<não-gestor>
AUTH_LEITOR_PASSWORD=<não-leitor>
CORS_ORIGINS=https://<sua-url-frontend-tunnel>
PUBLIC_BASE_URL=https://<sua-url-api-tunnel>
ENVIRONMENT=development   # production exige os mesmos cuidados + compose.prod
```

Ações sensíveis (`POST .../contingency/{id}/activate`, `POST .../monitoring/disseminate/{ibge}`)
exigem `confirm=true` (policy gate 20a.3).

## OIDC com Keycloak/gov.br real

Substitua o serviço Keycloak local pelas credenciais institucionais:

```bash
cp .env.govbr.example .env
# Edite OIDC_CLIENT_SECRET, URLs e grupos
```

Variáveis principais:

```bash
OIDC_ENABLED=true
OIDC_ISSUER_URL=https://keycloak.mcid.gov.br/realms/mcid
OIDC_CLIENT_ID=sinidu-clima
OIDC_CLIENT_SECRET=...
OIDC_SCOPES=openid profile email govbr_confiabilidades
OIDC_REDIRECT_URI=https://sinidu.mcid.gov.br/api/v1/auth/oidc/callback
OIDC_FRONTEND_REDIRECT=https://sinidu.mcid.gov.br/
AUTH_PASSWORD_LOGIN_ENABLED=false   # opcional — só SSO
```

Grupos IdP → roles: `OIDC_ADMIN_GROUPS`, `OIDC_GESTOR_GROUPS`, `OIDC_LEITOR_GROUPS`.

Claims de tenant: `tenant_uf`, `tenant_ibge` (configuráveis via env).

Verifique conectividade: `GET /health/oidc`  
Checklist completo gov.br: [CHECKLIST_OIDC_GOVBR.md](../CHECKLIST_OIDC_GOVBR.md)  
Smoke: `./scripts/validacao_oidc_govbr.sh https://<dominio>`

## Jobs em background (Fase 7)

Operações longas (onboarding 61 municípios, MapBiomas, pipeline ETL) rodam em thread no backend:

| Endpoint | Descrição |
|----------|-----------|
| `POST /api/v1/system/jobs/pipeline` | ETL + onboarding + MapBiomas |
| `POST /api/v1/system/jobs/onboarding-batch` | Onboarding em lote |
| `POST /api/v1/system/jobs/mapbiomas-batch` | Sync MapBiomas |
| `GET /api/v1/system/jobs/{id}` | Status do job |
| `GET /api/v1/system/jobs` | Lista jobs recentes |

No painel **Sistema** (`/sistema`), os botões Pipeline / Onboarding / MapBiomas disparam jobs async com polling. Requer role `admin` quando `AUTH_ENABLED=true`.

## Pipeline agendado e notificações (Fase 8)

```bash
SCHEDULED_PIPELINE_ENABLED=true
SCHEDULED_PIPELINE_LIMIT=61
JOB_GOTIFY_NOTIFY=true
GOTIFY_URL=http://gotify:80
GOTIFY_TOKEN=...
```

- Cron APScheduler: domingo 04:30 — pipeline territorial (ETL + onboarding + MapBiomas)
- Push Gotify ao concluir ou falhar jobs administrativos

## Catálogo de dados (`/catalogo`)

| Endpoint | Descrição |
|----------|-----------|
| `GET /api/v1/data-catalog/coverage` | Maturidade por base — município selecionado |
| `GET /api/v1/data-catalog/national` | Panorama agregado dos 61 prioritários (gestor+) |

## Malha viária e exportação em lote (Fase 9)

- OSRM multi-região: `docker/osrm/README.md` + `GET /api/v1/routing/status`
- Jobs: `diagnostics-batch`, `reports-batch`, `fontes-externas-batch` — painel `/sistema`

## Estrutura

```
deploy/
  nginx/
    nginx.conf          # HTTP (porta 80)
    nginx-tls.conf      # HTTPS + redirect + headers segurança
    certs/              # TLS (gitignored)
  keycloak/
    realm-sinidu.json   # Realm import para homologação local
scripts/
  homolog-up.sh         # Stack completa homolog
  prod-up.sh            # Produção MCID (cert institucional)
  deploy-staging.sh     # Staging sem TLS/OIDC
  validate-tls-certs.sh # Valida fullchain/privkey antes do deploy
  import_mapbiomas_csv.py
  generate-dev-certs.sh # Certificado autoassinado local
```

## Ecossistema

Parecer de mérito Pro-Cidades permanece no sistema dedicado `Pro-cidades/automacao/`. Sinidu foca inteligência territorial, export SEI de relatórios e auditoria.
