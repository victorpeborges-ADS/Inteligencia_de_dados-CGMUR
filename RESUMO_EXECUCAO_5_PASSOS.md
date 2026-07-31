# Execução dos 5 Passos — jul/2026

## Passo 1 — Validação UI Recife ✅

| Check | Resultado |
|-------|-----------|
| Malha/badges | OK — malha disponível |
| Apresentação 8 slides | OK |
| Catálogo ~61% maturidade | OK |
| Agente contextual (pergunta simples) | OK — ~3s com cache / bundle leve |
| Contexto assistente (`GET .../context`) | OK — prewarm boot + cache Redis (~instantâneo na 2ª chamada) |
| Simulação 120mm | OK — ~4s com prewarm + cache Redis |
| OSRM contingência (pe-se) | OK — rotas reais PE/SE (`scripts/validacao_osrm.py`) |

Script: `python3 scripts/validacao_recife_ui.py`

Melhorias aplicadas: prewarm pluvial no boot/troca de município, agente sem `executive_snapshot`, malha priorizada no mapa, contexto municipal em cache (sem `executive_snapshot`).

---

## Passo 2 — Diagnostics-batch + PDFs (62) ✅

- **62/62** municípios com diagnóstico executivo
- **62/62** com pelo menos um PDF municipal
- Painel **Sistema → Homologação** exibe cobertura e botão **Gerar PDFs pendentes**
- Jobs zumbis expiram após 6h (`STALE_JOB_HOURS`)

Últimos gaps fechados: Londrina (`4113700`) diagnóstico + PDF; São Luiz Gonzaga (`4318903`) PDF.

---

## Passo 3 — Onboarding 61/61 ✅

- Banco: **61/61 concluído** (seed prioritários)
- Auditoria: confiabilidade ALTA nos prioritários de boot (Recife, Aracaju)

---

## Passo 4 — Lacunas institucionais ✅

Documento: **`PLANO_LACUNAS_INSTITUCIONAIS.md`**

Prioridades: GeoSGB/CPRM → Brasil MAIS → SIRENE → AdaptaBrasil → SINTER

---

## Passo 5 — Homologação MCID ✅

- `.env.homolog` com `AUTH_ENABLED=true`, `MULTI_TENANT_ENABLED=true`
- Stack: `./scripts/homolog-up.sh .env.homolog`
- HTTPS: `curl -sk https://localhost/health/ready` → OK

| URL | Uso |
|-----|-----|
| https://localhost | App prod + TLS |
| https://localhost/api/v1/ | API (auth obrigatória) |
| http://localhost:8080 | Keycloak (admin/admin) |

---

## A.6 CTM — expansão jul/2026 ✅

| Métrica | Valor |
|---------|-------|
| Fontes cadastradas | **24/24** |
| Malha operacional | **24/24** (8 oficial + 16 IBGE) |
| Lacunas | **0** |

Tipos: `arcgis`, `geoserver_wfs`, `geojson_file`, `ibge_setores_agreg`, `ibge_setores_individuais` + fallback automático CONDER→setores.

---

## C.1 — DEM + simulação (jul/2026) ✅

- `DEM_PREWARM_ENABLED` — processa DEM (LiDAR local → SRTM) no boot prioritário **antes** da simulação
- Prewarm pluvial também chama `_ensure_dem_ready` ao trocar município
- **Bind** `./data/dem:/data/dem` no compose (LiDAR Recife visível no container)
- OpenTopography: só com `OPENTOPOGRAPHY_API_KEY` (ou `OPENTOPOGRAPHY_ENABLED=true`); timeout padrão **12s**
- Hidro: lê `dem.tif` processado primeiro; downsample ≤ `HYDRO_MAX_GRID_DIM` (512); suavização vetorizada

## D.2 — Prontidão homologação (jul/2026)

- `GET /system/overview` → bloco `homologation` (score %, SSO testável, checklist)
- Painel **Sistema → Prontidão homologação MCID** com itens ok/warn/fail
- Checklist ampliado: **OSRM**, **backup PostGIS** (`latest_backup_status`), **Gotify**, DEM boot via `dem_summary`
- Flags `ready_for_sso_test` e `ready_for_production` (senha off + dados + DEM; OSRM/Gotify/backup podem warn)
- Script: `./scripts/validacao_oidc_govbr.sh https://localhost`
- Smoke completo com JWT: `./scripts/demo-smoke.sh https://localhost` (OIDC + overview + amostra 6 municípios)
- Piloto Recife+Aracaju+OSRM: `RUN_PILOTO_VALIDATION=1 RUN_OSRM_VALIDATION=1 ./scripts/demo-smoke.sh https://localhost` → **0 falhas**
- Agente contextual em homolog **sem MISTRAL_API_KEY**: resposta offline com Score Sinidu (modo demo)
- `homolog-up.sh` usa `--no-build` por padrão (`FORCE_BUILD=1` para rebuild)
- Acesso UI: preferir **https://localhost** (http://localhost:3000 direto pode falhar no fetch da API TLS)
- **gov.br REAL:** ➖ fora do protótipo (decisão jul/2026) — usar Keycloak local ou login por senha

---

## Próximo no roadmap

| Prioridade | Item |
|------------|------|
| P2 | **A.6 CTM** — bloqueado: Palmas/São Luís sem REST público; CONDER intermitente (sondagem jul/2026) |
| P3 | Integrações A.1–A.5 (convênios MCID) — só com trâmite institucional |
| ➖ | **D.2 gov.br** — adiado; não é requisito do protótipo |

### Polish viz + contingência (jul/2026)
- 3D: opacidade do store, toggles de overlays de simulação, `ActiveLayersPanel`, basemap Claro
- Chip “Vivo” no header abre Contingência; Monitor mostra card alerta vivo + CTA
- `ContingencyDrawMap`: race do Leaflet.Draw corrigida (`drawReady` state)
- Plano ativo no mapa 2D/3D (`contingencyGeo` + toggle “Plano”); wizard hidrata plano ativo
- Basemap 2D: Escuro / Claro / Satélite (`MAP_TILE_URLS`)

### Tema light (jul/2026)
- Contraste botões/alertas/nav; overlays do mapa com `.map-ui-chrome`
- Checklist homologação inclui **ML alagamento** (`ml_flood_models`)

### ML alagamento — 10 alvos (jul/2026)
- `ML_TARGET_IBGE_CODES`: Recife, Salvador, POA, JP, Londrina + **Aracaju, Fortaleza, Belém, Curitiba, Rio**
- Artefatos baseline em `backend/ml/artifacts/`; painel Sistema → Bootstrap ML

### Infra / homolog — ready_for_demo (jul/2026)
- Gate `ready_for_demo` (JWT + multi-tenant + diag/PDF + DEM); CTM e senha = `na` no protótipo
- Checklist: `jwt_secret`, `redis_cache`, `scheduler_running`
- Boot valida JWT fraco em `ENVIRONMENT=production`; smoke/prod-up assertam prontidão
- UI Sistema: badge “Demo OK”

### Análise / índices — meta 88% (jul/2026)
- Preditiva UI: envia IBGE direto (removido limite stale de 5 slugs)
- Monitor: risco via ML quando alvo/artefato existe (`risk_source`); badge ML
- Sistema: lista dos 10 modelos (kind / limiar / AUC)
- Explicabilidade: `mm_acima_limiar` + top-3 features no predictor e na UI

### Contingência ← CEMADEN (jul/2026)
- `GET /contingency/municipio/{ibge}/alerta-vivo` + serviço `live_alert_level`
- Wizard pré-preenche nível e mostra badge “Alerta vivo”
- Header da plataforma sincroniza chip “Vivo {nível}” e `contingencyNivel` ao trocar município
- Geração a partir da simulação respeita `nivel_alerta` / alerta vivo

### IA/RAG — tools + eval (jul/2026)
- Agente: **13 tools** (+ alerta vivo CEMADEN, risco ML alagamento; contingência, calor/LST, maturidade)
- Corpus: `sinidu_modulos_operacionais.md` no manifest RAG
- Eval: **16 casos** em `rag/eval/dataset.yaml` (contingência, LST, maturidade, alerta vivo, ML)
- Meta dimensão IA (~82%) atingida no protótipo

### Dimensão E — testes (jul/2026)
- Meta **70%** atingida no escopo CI (`data_connectors` + maturity/onboarding/postgis_backup/observability)
- Medido **~76%**; gate `--cov-fail-under=70` em `pytest.ini` e `.github/workflows/ci.yml`
- Novos testes: SINESP, SICONFI, Ipeadata, S2ID, maturity/orchestrator/scheduler
- Testes de integração API marcados com `requires_postgres` (skip local sem DB); registry/catálogo/agent alinhados ao código
