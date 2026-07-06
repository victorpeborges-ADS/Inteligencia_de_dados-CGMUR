# Sinidu+Clima — Roadmap Priorizado

**Atualizado:** julho/2026  
**Referência:** avaliação técnica de maturidade + documentação em `documentacao/DOCUMENTACAO_TECNICA_COMPLETA.md`

---

## Legenda

| Prioridade | Significado |
|------------|-------------|
| P0 | Bloqueador — antes de demo externa ou acesso MCID |
| P1 | Alta — credibilidade operacional |
| P2 | Média — qualidade e escala |
| P3 | Estratégica — produto institucional |

| Status | Significado |
|--------|-------------|
| ✅ | Concluído |
| 🔄 | Em andamento |
| ⬜ | Pendente |
| ➖ | Fora de escopo — coberto por sistema dedicado |

---

## Fase 1 — Desbloqueadores (P0)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 1.1 | **Auth JWT + roles** (`admin`, `gestor_municipal`, `leitor`) | ✅ | `AUTH_ENABLED`, middleware, `POST /api/v1/auth/login` |
| 1.2 | **CORS restrito** via `CORS_ORIGINS` | ✅ | Padrão `http://localhost:3000` |
| 1.3 | **Health checks** `/health`, `/health/live`, `/health/ready`, `/health/db`, `/health/ollama` | ✅ | Readiness exige DB |
| 1.4 | **Boot resiliente** — API sobe mesmo se sync IBGE falhar | ✅ | `app/boot.py` + lifespan |
| 1.5 | **Frontend produção** — Dockerfile multi-stage (`Dockerfile.prod`) | ✅ | `next build` + `next start` |
| 1.6 | **Login UI** no frontend | ✅ | Modal + token em sessionStorage |
| 1.7 | **CI smoke test** mínimo | ✅ | `.github/workflows/ci.yml` |
| 1.8 | **docker-compose.prod.yml** | ✅ | Auth on, frontend prod, secrets via env file |

---

## Fase 2 — Credibilidade territorial (P1)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 2.1 | **OSRM multi-região** ou serviço nacional | ✅ | `OSRM_REGION=nordeste` default + `OSRM_COVERED_UFS` |
| 2.2 | **Rotular rotas aproximadas** fora de PE no UI | ✅ | Badge "sem malha viária" |
| 2.3 | **Badge de qualidade em cada KPI** do painel | ✅ | Oficial / Derivado / Demo / Lacuna |
| 2.4 | **Bloquear PDF formal** se maturidade &lt; Prata | ✅ | Com override admin |
| 2.5 | **ETL S2ID + MapBiomas** no onboarding | ✅ | Disparar após carga municipal |
| 2.6 | **CAPAG** — testes de regressão do parser | ✅ | `tests/test_capag_collector.py` |
| 2.7 | **Integração real SNIS/SINISA** | ✅ | `municipios_saneamento` + conector + camada híbrida |

---

## Fase 3 — Qualidade e escala (P2)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 3.1 | **CI/CD** — pytest, cobertura mínima 60% serviços críticos | ✅ | `pytest.ini` + CI ampliado |
| 3.2 | **Refator frontend** — App Router por módulo | ✅ | `/painel`, `/municipios`, `/simulacoes`… |
| 3.3 | **Estado global** — Zustand ou React Context | ✅ | `stores/useAppStore.ts` |
| 3.4 | **RAG eval set** — perguntas-resposta esperadas | ✅ | `rag/eval/dataset.yaml` + `/assistant/eval/retrieval` |
| 3.5 | **Limite tokens / OOM Ollama** — health memória + fallback Gemini | ✅ | `/health/ollama` + fallback automático |
| 3.6 | **ML alagamento** — expandir além de 5 municípios | ✅ | Baseline on-demand + terreno derivado |
| 3.7 | **Observabilidade** — logs JSON, métricas Prometheus | ✅ | `LOG_FORMAT=json` + `/metrics` |
| 3.8 | **Backup PostGIS** — pg_dump agendado | ✅ | Job 02:30 + `scripts/backup_postgis.sh` |

---

## Fase 4 — Produto MCID (P3)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 4.1 | **Módulo Pro-Cidades** — parecer de mérito automatizado | ➖ | **N/A no Sinidu** — sistema dedicado em `Pro-cidades/automacao/` (Streamlit, `motor.py`, crivo IN 18/2025, export SEI/HTML). Sinidu permanece como inteligência territorial; não duplicar o gerador de parecer. |
| 4.2 | **Export SEI** — PDF + metadados + hash | ✅ | `GET /api/v1/reports/{id}/sei-export` + SHA-256 em `relatorios_municipais` |
| 4.3 | **Multi-tenant** — isolamento por município/UF | ✅ | `MULTI_TENANT_ENABLED` + escopo UF/IBGE no JWT |
| 4.4 | **OIDC gov.br / Keycloak** | ✅ | `/auth/oidc/login` + callback → JWT Sinidu; grupos → roles |
| 4.5 | **Reverse proxy** — nginx/Caddy + TLS + rate limit | ✅ | `docker-compose.proxy.yml` + `deploy/nginx/nginx.conf` |
| 4.6 | **Auditoria** — log de ações (quem gerou PDF, ativou contingência) | ✅ | Tabela `audit_log` + `GET /api/v1/audit` (admin) + aba **Auditoria** no frontend |

---

## Fase 5 — Operação e homologação MCID (P3)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 5.1 | **Painel admin auditoria** no frontend | ✅ | `/auditoria` — filtros por ação/usuário, role `admin` |
| 5.2 | **CI frontend build** — validar `next build` standalone | ✅ | Job `frontend-build` no GitHub Actions |
| 5.3 | **Entrypoint frontend dev** — sync `node_modules` no Docker | ✅ | `frontend/docker-entrypoint.sh` |
| 5.4 | **Deploy staging** — script + vars documentadas | ✅ | `scripts/deploy-staging.sh` + seção no ROADMAP |
| 5.5 | **Homologação OIDC** Keycloak/gov.br real | ✅ local | Keycloak em `docker-compose.oidc.yml` + realm import; gov.br real = trocar env |
| 5.6 | **TLS** no proxy ou balanceador | ✅ local | `nginx-tls.conf` + `docker-compose.proxy-tls.yml` + cert MCID em produção |

---

## Fase 6 — Evolução operacional (P2/P3)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 6.1 | **Painel operacional** `/sistema` (admin) | ✅ | `GET /api/v1/system/overview` — saúde, boot, ETL, onboarding, auditoria |
| 6.2 | **Sync ETL manual** no painel Sistema | ✅ | Botão dispara `POST /api/v1/integrations/sync` |
| 6.3 | **CORS dual** `:3000` + `https://localhost` | ✅ | Default em `docker-compose.proxy-tls.yml` |
| 6.4 | **Dockerfile backend** — build Debian trixie | ✅ | Removido `wkhtmltopdf` (fallback matplotlib no PDF) |
| 6.5 | **Template homologação** | ✅ | `.env.homolog.example` |
| 6.6 | **Integração MapBiomas** territorial completa | ✅ | `mapbiomas_collector.py` + stats anuais + `/integrations/mapbiomas` |
| 6.7 | **Onboarding em lote** — 61 prioritários | ✅ | `POST /api/v1/onboarding/run-batch` + botão no painel Sistema |
| 6.8 | **Certificado MCID** em produção | ✅ | `prod-up.sh` + `validate-tls-certs.sh` + `/health/tls` |
| 6.9 | **MapBiomas sync lote** (61 municípios) | ✅ | `POST /integrations/mapbiomas/sync-batch` |

---

## Fase 7 — Escala territorial e gov.br (P2/P3)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 7.1 | **Jobs em background** (onboarding/MapBiomas/pipeline) | ✅ | `POST /api/v1/system/jobs/*` + polling no painel Sistema |
| 7.2 | **Pipeline territorial** ETL → onboarding → MapBiomas | ✅ | `POST /system/jobs/pipeline` |
| 7.3 | **Catálogo de dados dinâmico** | ✅ | `data_catalog_engine.py` — status real do PostGIS |
| 7.4 | **OIDC gov.br** — resource_access + template | ✅ | `.env.govbr.example` + claims Keycloak |
| 7.5 | **Scheduler no painel Sistema** | ✅ | Status APScheduler em `/system/overview` |
| 7.6 | **Onboarding 61 municípios** em background | ✅ | Botão Onboarding (61) no painel |
| 7.7 | **Link informativo Pro-Cidades** no painel | ✅ | Card ecossistema MCID em `/sistema` |

---

## Fase 8 — Operação contínua e transparência (P2)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 8.1 | **Notificação Gotify** ao concluir jobs | ✅ | `JOB_GOTIFY_NOTIFY` + `push_job_status` |
| 8.2 | **Pipeline agendado** (domingo 04:30) | ✅ | `SCHEDULED_PIPELINE_ENABLED` no scheduler |
| 8.3 | **Panorama nacional do catálogo** | ✅ | `GET /data-catalog/national` |
| 8.4 | **Painel Catálogo** `/catalogo` | ✅ | Maturidade municipal + ranking 61 prioritários |
| 8.5 | **Testes API jobs + catálogo nacional** | ✅ | `test_system.py` ampliado |

---

## Fase 9 — Malha viária, produto, integrações e docs (P2)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 9.1 | **OSRM multi-região** (sudeste/sul/…) + status API | ✅ | `GET /routing/status` + `OSRM_REGION` |
| 9.2 | **Fallback geodésico** com distância/duração estimada | ✅ | Haversine + 40 km/h |
| 9.3 | **UI rotas** — UFs do backend + tracejado no mapa | ✅ | ContingencyWizard + DrawMap |
| 9.4 | **Export lote** diagnósticos + PDFs (61) | ✅ | Jobs `diagnostics-batch` / `reports-batch` |
| 9.5 | **Fontes externas** Adapta/GeoSGB/SIRENE/Brasil MAIS | ✅ | `external_sources_collector` + migration 012 |
| 9.6 | **Orchestrator** sync fontes externas | ✅ | `fontes_externas` no `sync_all` |
| 9.7 | **Testes** OSRM, batch export, fontes externas | ✅ | `test_osrm_router`, `test_batch_export`, … |
| 9.8 | **Documentação técnica** atualizada | ✅ | Auth, OSRM, batch, integrações, Fase A 3D (jul/2026) |

---

## Fase 10 — Escala operacional 61 municípios (P1)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 10.1 | **Correção diagnóstico Belém** — lacunas dict no catálogo | ✅ | `_merge_lacunas()` em `executive_diagnostic_engine.py` |
| 10.2 | **Onboarding batch até 61** (antes cap 20) | ✅ | `run_batch_onboarding` limit 61 |
| 10.3 | **Pipeline** — onboarding antes do ETL | ✅ | Geometria PostGIS liberada mais cedo |
| 10.4 | **Pipeline completo 61** em execução | ✅ | `POST /system/jobs/homologation-full` — onboarding + ETL + MapBiomas + DEM + diagnósticos |
| 10.5 | **Batch diagnósticos/PDFs** pós-onboarding | ✅ | `ensure_dem=true` + jobs `diagnostics-batch` / `reports-batch` |
| 10.6 | **DEM LiDAR local + batch** | ✅ | `LOCAL_DEM_DIR`, upload `POST /terrain/{ibge}/import-local-dem`, job `dem-batch` |
| 10.7 | **OSRM malha real** para demo | ➖ | Adiar — fallback Haversine ativo; subir com `setup-osrm.sh` quando necessário |

**Comandos operacionais:**

```bash
# Pipeline territorial (onboarding + ETL + MapBiomas)
curl -X POST "http://localhost:8000/api/v1/system/jobs/pipeline?onboarding_limit=61"

# Pipeline MCID completo (+ DEM + diagnósticos executivos)
curl -X POST "http://localhost:8000/api/v1/system/jobs/homologation-full?onboarding_limit=61"

# Batch DEM (LiDAR local ou SRTM/refinado piloto)
curl -X POST "http://localhost:8000/api/v1/system/jobs/dem-batch?limit=61"

# Diagnósticos em lote (garante DEM se ausente)
curl -X POST "http://localhost:8000/api/v1/system/jobs/diagnostics-batch?limit=61"

# LiDAR Recife — upload GeoTIFF
curl -X POST "http://localhost:8000/api/v1/terrain/2611606/import-local-dem" -F "file=@recife_lidar.tif"

# OSRM — somente para demo com rotas reais
OSRM_REGION=nordeste bash docker/osrm/setup-osrm.sh && docker compose up -d osrm
```

---

## Fase 11 — Produto territorial avançado (Steps 8–9 + Fase A 3D)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 11.1 | **PDF completo 8+ págs** — gráficos Python, narrativa IA, mapa estático | ✅ | `report_completo_service.py`, `municipal_report_completo.html` |
| 11.2 | **Polimento UX Step 9** — loading states, tooltips, Central da Oficina | ✅ | `RotatingLoader`, `TermTooltip`, `WorkshopCenter` |
| 11.3 | **Comparação de municípios** — tabela, radar, IA, export PDF | ✅ | `CompareModal.tsx` + `compare.analytics` na auditoria |
| 11.4 | **Trilha de auditoria expandida** — diagnóstico, PDF, comparação, onboarding | ✅ | Aba `/auditoria` + filtros por ação/IBGE |
| 11.5 | **Simulação 3D Fase A** — extrusão de manchas + inspeção por clique | ✅ | MapLibre + Terrarium; **sem** Google Street View |
| 11.6 | **Auto 3D** após simulação pluvial ou ilha de calor | ✅ | `PlatformApp.handleSimulate` → `setMapMode('3d')` |
| 11.7 | **Inspeção de profundidade** — solo, água (cm), cota | ✅ | `floodInspect.ts` + `queryTerrainElevation` |
| 11.8 | **Google Street View 3D** | ➖ | `Map3DGoogleContainer.tsx` existe mas não está no fluxo principal (custo de API) |

**Arquivos frontend (Fase A 3D):**

| Arquivo | Função |
|---------|--------|
| `Map3DMapLibreContainer.tsx` | Terreno 3D, painel de inspeção, voo oblíquo pós-simulação |
| `maplibreLayers.ts` | `fill-extrusion`, marcador de clique, camadas de simulação |
| `layerStyles.ts` | `_extrusionHeightM` (água e calor) |
| `floodInspect.ts` | Cálculo de profundidade/cota no ponto clicado |

**Smoke test Fase A (Recife 2611606):**

```bash
# Backend — compare 120 mm vs 80 mm (~60 s)
curl -X POST "http://localhost:8000/api/v1/simulations/extreme-rainfall/compare" \
  -H "Content-Type: application/json" \
  -d '{"codigo_ibge":"2611606","scenario_mm":120,"baseline_mm":80}'
```

Frontend: Simulações → Rodar → Terreno 3D ativo → clicar na mancha azul.

---

## Fase 12 — Performance simulação e UX oficina (P1)

| # | Item | Status | Notas |
|---|------|--------|-------|
| 12.1 | **Cache Redis** simulação pluvial | ✅ | `simulation_cache.py`, TTL 24 h |
| 12.2 | **Compare paralelo** baseline + cenário | ✅ | `ThreadPoolExecutor` |
| 12.3 | **Jobs async** + polling UI | ✅ | `/extreme-rainfall/async`, `/compare/async`, `/jobs/{id}` |
| 12.4 | **Barra de progresso** na aba Chuva | ✅ | `stage_label` + % |
| 12.5 | **Legenda 3D** faixas de profundidade | ✅ | Painel MapLibre |
| 12.6 | **CompareModal** par mesma UF | ✅ | Fallback inteligente |
| 12.7 | **Testes cache** | ✅ | `test_simulation_cache.py` |

Ver `CHECKLIST_FASE_12.md`.

---

## Fase 12b — Operacional oficina ✅

| # | Item | Status | Notas |
|---|------|--------|-------|
| 12b.1 | **Banner OSRM** contingência | ✅ | Status Nordeste + setup script |
| 12b.2 | **Cache interpretação IA** | ✅ | `simulation_interpret_cache.py`, TTL 6 h |
| 12b.3 | **Pré-aquecimento DEM** | ✅ | Badge "DEM aquecido" na aba Simulações |
| 12b.4 | **Testes floodInspect** | ✅ | `npm run test:floodInspect` |

---

## Fase 13 — Experiência institucional (UX/UI, plano 06/07)

Roteiro incremental **frontend-only** (sem alterar API), derivado do plano de melhoria Sinidu 06/07.

| # | Prompt / item | Status | Notas |
|---|---------------|--------|-------|
| 13.0 | **Design System** (tokens + componentes base) | ✅ | `KpiCard`, `PanelSection`, `Badge` |
| 13.1 | **Modo Focus** (tecla F) | ✅ | Sidebar/camadas recolhidas; mapa + WorkshopCenter |
| 13.2 | Hierarquia visual painéis | ✅ | KPIs primários vs secundários no painel executivo |
| 13.3 | Sidebar camadas agrupada | ✅ | `LayerPanel` colapsável + ícones por grupo |
| 13.4 | Estados vazios e loading | ✅ | `EmptyState`, `Skeleton*` + painéis chave |
| 13.5 | Fluxo simulação guiado | ✅ | `SimulationNextSteps` pós-cenário |
| 13.6 | Painel executivo narrativo | ✅ | `ExecutiveNarrative` + `executiveNarrative.ts` |
| 13.7 | Motor de recomendações | ➖ | Prompt 08 — adiar até explicabilidade IA |
| 13.8 | Onboarding contextual | ✅ | `TabContextHint` por aba (dismissível) |
| 13.9 | Comparador territorial | ✅ | Pares sugeridos, deltas, veredicto, bullets |
| 13.10 | Apresentação executiva | ✅ | Prompt 11 — `/apresentacao/{ibge}` 8 slides |
| 13.11 | Auditoria legível | ✅ | Prompt 12 — `AuditPanel` |
| 13.12 | Agente proativo | ✅ | Prompt 13 — `AgenteSinidu` + `useAgenteProativo` |
| 13.13 | Glossário inline | ✅ | Prompt 14 — `TermTooltip` |
| 13.14 | Remover rótulos MVP | ➖ | Prompt 15 — adiar pós-homologação |

**Já existente (não refazer):** `WorkshopCenter`, `/apresentacao/{ibge}`, `ExecutiveDashboard`, `AgenteSinidu`, `AuditPanel`, `TermTooltip`.

**Ordem sugerida:** 13.0 → 13.1 → 13.2 → 13.3 → 13.5 → 13.6 → 13.9 → demais.

Ver `CHECKLIST_FASE_13.md`.

---

## Ecossistema MCID — Sinidu vs Pro-Cidades

Dois produtos complementares, repositórios separados:

| | **Sinidu+Clima** (este repo) | **Pro-Cidades** (`Pro-cidades/automacao/`) |
|---|------------------------------|--------------------------------------------|
| Foco | Território: clima, risco, saneamento, maturidade de dados, mapa 3D | Processo SEI: parecer de mérito FGTS (IN MCID 18/2025) |
| Saída | KPIs, plano de mitigação, PDF municipal | Parecer de mérito HTML/Word/PDF, checklist Anexo II |
| Usuário | Gestor municipal, equipe técnica territorial | Analista CGMUR/DAC (intranet Streamlit) |

Integração entre os dois **não é requisito** do Sinidu. Se desejável no futuro: link externo com IBGE pré-preenchido ou card informativo no catálogo de financiamento federal — sem incorporar `motor.py` neste backend.

Referência Pro-Cidades: `Pro-cidades/README.md`, `Pro-cidades/automacao/README_INTRANET.md`.

---

## Maturidade por dimensão (baseline → meta)

| Dimensão | Baseline | Meta Fase 1 | Meta Fase 3 |
|----------|----------|-------------|-------------|
| Infraestrutura | 88% | 92% | 95% |
| API e backend | 85% | 90% | 93% |
| Integrações externas | 72% | 72% | 85% |
| Análise e índices | 78% | 78% | 88% |
| IA e RAG | 70% | 72% | 82% |
| Visualização 2D/3D | 75% | 80% | 88% |
| Contingência e alerta | 80% | 80% | 88% |
| **Segurança e auth** | **8%** | **55%** | **80%** |
| **Testes automatizados** | **40%** | **45%** | **70%** |
| **Produção / deploy** | **20%** | **45%** | **75%** |

---

## Decisões técnicas registradas

### Boot monolítico → separado (✅ Fase 1)
- Migrations e seeds: best-effort, não bloqueiam Uvicorn
- Sync IBGE/SICONFI/CAPAG: thread daemon + scheduler
- Status exposto em `/health/ready`

### SPA única → rotas (✅ Fase 3)
- App Router por módulo: `/painel`, `/municipios`, `/simulacoes`, `/auditoria`…
- `PlatformApp` compartilhado com estado Zustand

### Ollama 12 GB (✅ Fase 3)
- Healthcheck memória no container
- Truncar contexto municipal no assistente
- Gemini como fallback cloud quando `GEMINI_API_KEY` presente

### Pro-Cidades fora do Sinidu (➖ Fase 4.1)
- Parecer de mérito FGTS: sistema dedicado `Pro-cidades/automacao/` (já em produção na intranet)
- Sinidu não reimplementa crivo normativo nem template de parecer MCID
- Fase 4 do Sinidu concentra-se em auth institucional, multi-tenant, deploy e auditoria dos relatórios territoriais

### Multi-tenant por UF/IBGE (✅ Fase 4.3)
- Escopo no JWT (`tenant_uf`, `tenant_ibge`)
- Filtro em listagens (`/indicators/municipalities`, `/seeds`, monitoramento)
- Bloqueio 403 em endpoints por `codigo_ibge` fora do perfil
- Admin nacional sem restrição

### OIDC + proxy produção (✅ Fase 4.4 / 4.5)
- Login federado emite o mesmo JWT interno (multi-tenant preservado)
- Nginx na borda com rate limit; headers `X-Forwarded-*` confiáveis no backend

---

## Como usar auth (Fase 1)

```bash
# Desenvolvimento — auth desligado (padrão)
AUTH_ENABLED=false

# Demonstração / staging
AUTH_ENABLED=true
AUTH_JWT_SECRET=trocar-em-producao-min-32-chars
AUTH_ADMIN_PASSWORD=...
AUTH_GESTOR_PASSWORD=...
AUTH_LEITOR_PASSWORD=...
CORS_ORIGINS=http://localhost:3000
```

Login: `POST /api/v1/auth/login` com `{ "username", "password" }`  
Roles: `admin` > `gestor_municipal` > `leitor`

### Multi-tenant (Fase 4.3)

```bash
MULTI_TENANT_ENABLED=true
AUTH_GESTOR_TENANT_UF=PE          # gestor vê só municípios desta UF
AUTH_LEITOR_TENANT_UF=PE
# Ou lista explícita por usuário:
AUTH_TENANT_gestor_IBGE=2611606,2806701
AUTH_TENANT_gestor_UF=PE          # override por username
```

Com `MULTI_TENANT_ENABLED=false` (padrão dev), todos os municípios permanecem visíveis.

### OIDC / SSO (Fase 4.4)

```bash
OIDC_ENABLED=true
OIDC_ISSUER_URL=https://keycloak.exemplo.gov.br/realms/mcid
OIDC_CLIENT_ID=sinidu-clima
OIDC_CLIENT_SECRET=...
OIDC_REDIRECT_URI=https://sinidu.exemplo.gov.br/api/v1/auth/oidc/callback
OIDC_FRONTEND_REDIRECT=https://sinidu.exemplo.gov.br/
AUTH_PASSWORD_LOGIN_ENABLED=false   # opcional — só SSO
```

Grupos Keycloak → roles: `OIDC_ADMIN_GROUPS`, `OIDC_GESTOR_GROUPS`, `OIDC_LEITOR_GROUPS`.

Template completo gov.br: copie `.env.govbr.example` para `.env` e ajuste issuer, client e scopes (`govbr_confiabilidades`).

### Jobs administrativos (Fase 7)

```bash
# Pipeline completo (background)
curl -X POST "https://localhost/api/v1/system/jobs/pipeline?onboarding_limit=61" \
  -H "Authorization: Bearer $TOKEN"

# Acompanhar
curl "https://localhost/api/v1/system/jobs/{job_id}" -H "Authorization: Bearer $TOKEN"
```

No painel **Sistema** (`/sistema`): botões Pipeline MCID (61), DEM (61), LiDAR piloto, Onboarding e MapBiomas com polling automático.

### Pipeline agendado + Gotify (Fase 8)

```bash
SCHEDULED_PIPELINE_ENABLED=true
SCHEDULED_PIPELINE_LIMIT=61
JOB_GOTIFY_NOTIFY=true
GOTIFY_TOKEN=...   # app Gotify local ou institucional
```

Domingo 04:30 (America/Sao_Paulo): ETL + onboarding + MapBiomas. Notificação push ao concluir ou falhar.

Painel **Catálogo** (`/catalogo`): maturidade por base de dados e panorama dos 61 prioritários (gestor/admin).

### Reverse proxy (Fase 4.5)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.proxy.yml up -d
```

- Entrada única na porta **80** (`PROXY_HTTP_PORT`)
- Rate limit: **30 req/s** na API, **10 req/min** em `/auth/`
- Com proxy: `TRUST_PROXY_HEADERS=true`, `NEXT_PUBLIC_API_URL=http://localhost`

TLS: terminar no balanceador institucional ou adicionar certificados em `deploy/nginx/` (Let's Encrypt / certificado MCID).

---

### Deploy staging (Fase 5.4)

```bash
chmod +x scripts/*.sh
./scripts/deploy-staging.sh .env   # staging sem TLS/OIDC
./scripts/homolog-up.sh            # homologação completa TLS + Keycloak
```

Documentação detalhada: [`deploy/README.md`](deploy/README.md)

Variáveis mínimas para `.env` de homologação (ver também seção OIDC/multi-tenant acima):

```bash
AUTH_ENABLED=true
AUTH_JWT_SECRET=...
MULTI_TENANT_ENABLED=true
NEXT_PUBLIC_API_URL=https://localhost
CORS_ORIGINS=http://localhost:3000,https://localhost
TRUST_PROXY_HEADERS=true
OIDC_ENABLED=true
OIDC_ISSUER_URL=http://host.docker.internal:8080/realms/sinidu
OIDC_CLIENT_SECRET=sinidu-local-secret-change-me
```

### Health OIDC (Fase 5.5)

```bash
curl -sk https://localhost/health/oidc
```

```bash
# Health
curl http://localhost:8000/health
curl http://localhost:8000/health/ready

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}'

# Frontend produção
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d frontend
```
