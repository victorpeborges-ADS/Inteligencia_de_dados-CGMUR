# Sinidu+Clima — Documentação Técnica Completa do Sistema

**Plataforma Nacional de Inteligência Territorial**  
**Versão do documento:** julho/2026 (Fases 15–16)  
**Município piloto:** Recife/PE (IBGE `2611606`)  
**Escopo:** 61 municípios prioritários MCID

---

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Arquitetura](#2-arquitetura)
3. [Stack tecnológica](#3-stack-tecnológica)
4. [Infraestrutura Docker](#4-infraestrutura-docker)
5. [Banco de dados e modelos](#5-banco-de-dados-e-modelos)
6. [Metodologia analítica](#6-metodologia-analítica)
7. [Módulos funcionais](#7-módulos-funcionais)
8. [API REST e WebSocket](#8-api-rest-e-websocket)
9. [Interface web (frontend)](#9-interface-web-frontend)
10. [Integrações externas](#10-integrações-externas)
11. [Inteligência artificial e RAG](#11-inteligência-artificial-e-rag)
12. [ETL e pipelines de dados](#12-etl-e-pipelines-de-dados)
13. [Relatórios e documentos](#13-relatórios-e-documentos)
14. [Agendamento e jobs em background](#14-agendamento-e-jobs-em-background)
15. [Testes automatizados](#15-testes-automatizados)
16. [Variáveis de ambiente](#16-variáveis-de-ambiente)
17. [Fluxo operacional do gestor](#17-fluxo-operacional-do-gestor)
18. [Limitações e considerações](#18-limitações-e-considerações)
19. [Fase 15 — Novos indicadores e simulação climática](#19-fase-15--novos-indicadores-e-simulação-climática)
20. [Fase 16 — Complemento GeoReDUS](#20-fase-16--complemento-georedus)

---

## 1. Visão geral

O **Sinidu+Clima** é uma plataforma web para diagnóstico territorial, simulação de cenários climáticos, gestão de contingência e apoio à decisão municipal. Foi concebida para o Ministério das Cidades (MCID) e opera sobre dados geoespaciais, indicadores fiscais/demográficos e fontes públicas de clima e desastres.

### Objetivos principais

- Consolidar dados territoriais de múltiplas fontes em um único painel executivo
- Calcular índices de vulnerabilidade climática (IVC), risco de inundação (IRI) e Score Sinidu+Clima
- Simular impactos de impermeabilização, perda de vegetação, chuvas extremas e déficit de drenagem
- Gerar diagnósticos executivos, planos de ação e relatórios PDF para gestores
- Operar planos de contingência alinhados ao COBRADE com monitoramento em tempo quase real
- Oferecer assistente municipal com IA (RAG local + provedores cloud opcionais)

### Escopo territorial

- **61 municípios prioritários** definidos em `TARGET_IBGE_CODES` (`backend/app/config.py`)
- Carga sob demanda via **Onboarding Engine** (malhas IBGE + integrações)
- **5 municípios** com modelo preditivo ML de alagamento: Recife, Salvador, Porto Alegre, João Pessoa e Londrina

---

## 2. Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 13)                        │
│  Painel · Municípios · Catálogo · Simulações · Monitor ·        │
│  Contingência · Assistente · Casos · Auditoria · Sistema ·      │
│  Mapa 2D (Leaflet) / 3D (MapLibre + extrusão de simulação)      │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                   Backend (FastAPI + Uvicorn)                    │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────────────┐ │
│  │ 15 routers  │ │ 21 serviços  │ │ ETL · ML · RAG · Reports  │ │
│  │ REST API    │ │ de domínio   │ │                         │ │
│  └─────────────┘ └──────────────┘ └─────────────────────────┘ │
└───┬─────────┬──────────┬──────────┬──────────┬─────────────────┘
    │         │          │          │          │
┌───▼───┐ ┌───▼───┐ ┌────▼────┐ ┌───▼───┐ ┌────▼─────┐
│PostGIS│ │ Redis │ │ Ollama  │ │ OSRM  │ │ Gotify   │
│+vector│ │ cache │ │ LLM+RAG │ │ rotas │ │ push     │
└───────┘ └───────┘ └─────────┘ └───────┘ └──────────┘
    │
    │  Integrações externas (HTTP)
    ▼
 IBGE · SICONFI · CAPAG · CEMADEN · Open-Meteo · INMET ·
 OpenTopography · Sentinel STAC · OSM · Google Maps (opcional)
```

### Estrutura de diretórios

| Pasta | Conteúdo |
|-------|----------|
| `backend/` | API FastAPI, modelos, serviços, ETL, ML, RAG, migrations, seeds, testes |
| `frontend/` | Aplicação Next.js (App Router + `PlatformApp` compartilhado) |
| `docker/` | Configurações Docker (Postgres, Ollama, OSRM, Gotify) |
| `documentacao/` | PDFs e esta documentação |
| `scripts/` | Utilitários (geração de PDFs de documentação) |
| `ollama_data/` | Volume persistente de modelos Ollama |

---

## 3. Stack tecnológica

### Backend

| Componente | Tecnologia |
|--------------|------------|
| Linguagem | Python 3.10 |
| Framework web | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.x + GeoAlchemy2 |
| Validação | Pydantic 2 |
| Geoespacial | Shapely, PyProj, GDAL/rasterio |
| PDF/HTML | WeasyPrint, Jinja2, Folium, Matplotlib |
| Scheduler | APScheduler |
| Cache | Redis (fallback em memória) |
| HTTP client | requests, httpx, openmeteo-requests |
| ML | scikit-learn, numpy, pandas |
| RAG | langchain-community, pgvector, pypdf |

### Frontend

| Componente | Tecnologia |
|--------------|------------|
| Framework | Next.js 13.4 + React 18 + TypeScript 5 |
| Estilo | Tailwind CSS 3, clsx, tailwind-merge |
| Mapas 2D | Leaflet + react-leaflet |
| Mapas 3D | MapLibre GL 4.7 (CDN) + tiles DEM Terrarium |
| Gráficos | Recharts |
| Ícones | lucide-react |

### Banco de dados

- **PostgreSQL 15** com extensões **PostGIS 3.4** e **pgvector**
- Geometrias em SRID 4326 (WGS84)
- Embeddings RAG: vetores 768 dimensões

### Inteligência artificial

| Modo | Provedor | Modelo padrão |
|------|----------|---------------|
| Local (padrão) | Ollama | `llama3.1:8b-instruct-q4_K_M` |
| Embeddings local | Ollama | `nomic-embed-text` |
| Cloud (opcional) | OpenAI, Anthropic, Gemini, Groq, Mistral, OpenRouter | Configurável via env |

---

## 4. Infraestrutura Docker

Orquestração via `docker-compose.yml` — **8 serviços**:

| Serviço | Container | Porta | Função |
|---------|-----------|-------|--------|
| `db` | sinidu_db | 5432 | PostgreSQL + PostGIS + pgvector |
| `redis` | sinidu_redis | 6379 | Cache de integrações |
| `ollama` | sinidu_ollama | 11434 | LLM e embeddings locais (limite 12 GB RAM) |
| `backend` | sinidu_backend | 8000 | API FastAPI |
| `frontend` | sinidu_frontend | 3000 | Next.js (modo dev) |
| `osrm` | sinidu_osrm | 5000 | Roteamento para evacuação (região PE padrão) |
| `gotify` | sinidu_gotify | 8888 | Notificações push (alertas LARANJA/VERMELHO) |

### Volumes persistentes

- `pgdata` — dados PostgreSQL
- `reports_data` — PDFs gerados
- `models_data` — modelos ML serializados
- `ml_data` — datasets de treino
- `dem_data` — tiles SRTM / análise de declividade
- `gotify_data` — configuração Gotify

### Boot do backend

Na inicialização (`backend/main.py`):

1. Habilita extensões `postgis` e `vector`
2. Aplica migrations SQL 003–008
3. Executa seed dos 61 municípios prioritários
4. Cria tabelas via SQLAlchemy `create_all()`
5. Garante municípios demo (Recife e outros)
6. Dispara sync inicial IBGE/SICONFI/CAPAG
7. Inicia scheduler de integrações e monitoramento

---

## 5. Banco de dados e modelos

### Tabelas principais

| Modelo | Tabela | Descrição |
|--------|--------|-----------|
| `Municipio` | `municipios` | Limite municipal, população, área, geometria |
| `Bairro` | `bairros` | Malha de bairros com indicadores temporais |
| `SetorCensitario` | `setores_censitarios` | Setores IBGE (renda, população) |
| `HistoricoDesastreS2ID` | `historico_desastres_s2id` | Eventos de desastre (S2ID) |
| `AlertaCemaden` | `alertas_cemaden` | Alertas hidrológicos CEMADEN |
| `CoberturaVegetalMapBiomas` | `cobertura_vegetal_mapbiomas` | Uso do solo |
| `InfraestruturaUrbana` | `infraestrutura_urbana` | Equipamentos e vias (OSM) |
| `MunicipioIbge` | `municipios_ibge` | Demografia e economia IBGE |
| `MunicipioFiscal` | `municipios_fiscal` | SICONFI + nota CAPAG |
| `IntegrationRun` | `integration_runs` | Log de sincronizações |
| `CasoSucesso` | `casos_sucesso` | Casos de adaptação climática |
| `RelatorioMunicipal` | `relatorios_municipais` | Histórico de PDFs |
| `DiagnosticoExecutivo` | `diagnosticos_executivos` | Diagnósticos automáticos |
| `PlanoAcaoMunicipal` | `planos_acao_municipais` | Planos de ação territorial |
| `RagDocument` | `rag_documents` | Chunks RAG com embedding |
| `MunicipioSeed` | `municipios_seed` | 61 municípios + status onboarding |
| `EstabelecimentoSaude` | `estabelecimentos_saude` | CNES/DataSUS |
| `MunicipioSaude` | `municipios_saude` | Indicadores agregados de saúde |
| `MunicipioSeguranca` | `municipios_seguranca` | SINESP / dados.gov.br |
| `MunicipioSingedlabRs` | `municipio_singedlab_rs` | Exposição CNEFE SINGED Lab (enchentes RS 2024) |
| `MunicipioGeoportalPublicacao` | `municipio_geoportal_publicacao` | Upload/API CTM municipal |
| `ContingencyPlan` | `contingency_plans` | Planos de contingência |
| `ContingencyPlanRevision` | `contingency_plan_revisions` | Revisões e snapshots |
| `MonitoringAlert` | `monitoring_alerts` | Alertas internos |
| `WeatherForecastCache` | `weather_forecast_cache` | Cache Open-Meteo |

### Migrations

| Arquivo | Conteúdo |
|---------|----------|
| `001_integration_tables.sql` | IBGE, SICONFI, CAPAG, integration_runs |
| `002_reports_history.sql` | Histórico de relatórios |
| `003_rag_pgvector.sql` | Extensão vector, rag_documents |
| `004_municipios_expansion.sql` | Seed, saúde, segurança |
| `005_contingency_monitoring.sql` | Contingência e monitoramento |
| `006_onboarding_engine.sql` | Colunas de onboarding |
| `007_diagnosticos_executivos.sql` | Diagnósticos executivos |
| `008_planos_acao_municipais.sql` | Planos de ação |
| `009_municipios_saneamento.sql` | SNIS/SINISA saneamento |
| `010_audit_log_sei.sql` | Trilha de auditoria SEI |
| `011_mapbiomas_stats.sql` | Estatísticas MapBiomas |
| `012_fontes_externas.sql` | AdaptaBrasil, GeoSGB, SIRENE, Brasil MAIS |
| `013_rag_mistral_embeddings.sql` | Embeddings Mistral no RAG |
| `014_municipio_data_honesty.sql` | Metadados de honestidade de dados |
| `015_diagnostic_narrativa_ia.sql` | Narrativa IA no diagnóstico |
| `016_casos_sucesso_semantic.sql` | Busca semântica de casos de sucesso |
| `017_singedlab_rs.sql` | Exposição IBGE SINGED Lab RS 2024 (`municipio_singedlab_rs`) |
| `018_pib_serie.sql` | Série histórica de PIB municipal (`pib_serie` JSON em `municipio_ibge`) |
| `019_censo_deficits.sql` | Déficits domiciliares Censo 2022 por setor censitário |
| `020_educacao_inep.sql` | Matrículas INEP por setor (`educacao_setor_censitario`) |
| `021_territorios_especiais.sql` | Quilombos, TIs e aglomerados subnormais |
| `022_municipio_geoportal.sql` | Publicações CTM do geoportal municipal |

### Camadas geoespaciais (GeoJSON)

Endpoint: `GET /api/v1/indicators/layers/{layer_name}`

Camadas disponíveis: `municipio`, `bairros`, `setores`, `socioeconomico`, `vulnerabilidade`, `inundacao`, `cobertura`, `desastres`, `alertas`, `infraestrutura`, `adaptacao_climatica`, `prioridade_planejamento`, `saneamento_drenagem`, `lacunas_dados`, `saude_risco`, `seguranca_publica`, `vulnerabilidade_multidimensional`, `lst_observada`, `educacao`, `territorios_especiais`.

Cada camada possui badge de qualidade: **Oficial**, **Estimado** ou **Derivado Sinidu+Clima**.

---

## 6. Metodologia analítica

### Score Sinidu+Clima (0–100)

Fórmula municipal:

```
Score = 45% × IVC_médio + 35% × IRI_médio + 20% × (1 − capacidade_adaptação_média)
```

Interpretação: **quanto maior o score, maior a prioridade territorial** para intervenção.

| Faixa | Classificação |
|-------|---------------|
| ≥ 66 | Alta prioridade (vermelho) |
| 33–65 | Média prioridade (laranja) |
| < 33 | Baixa prioridade (azul) |

### IVC — Índice de Vulnerabilidade Climática (0–1 por bairro)

```
IVC = (Exposição + Sensibilidade) / 2 × (1 − Capacidade de Adaptação)
```

| Componente | Fatores |
|------------|---------|
| **Exposição** | Histórico S2ID (40%) + alertas CEMADEN (60%) |
| **Sensibilidade** | Densidade demográfica (50%) + renda média inversa (50%) |
| **Adaptação** | Cobertura vegetal MapBiomas (60%) + infraestrutura hospitalar (40%) |

### IRI — Índice de Risco de Inundação (0–1 por bairro)

```
IRI = 40% × histórico S2ID (inundação) + 40% × impermeabilização + 20% × proximidade de corpos d'água
```

### Score de Maturidade Municipal (0–100)

Avalia a **qualidade e completude dos dados** no banco, não o risco climático.

| Nível | Faixa |
|-------|-------|
| Platina | ≥ 76 |
| Ouro | 51–75 |
| Prata | 26–50 |
| Bronze | 0–25 |

Fontes avaliadas (8): IBGE, SICONFI, CAPAG, S2ID, MapBiomas, Bairros, Plano Diretor, Dados Climáticos.

Peso por status: Oficial (100%), Derivado (75%), Estimado (55%), Lacuna (0%).

### Outros índices derivados

- **Ilhas de calor urbanas (analytics)** — proxy por bairro a partir de capacidade de adaptação (vegetação MapBiomas inversa); endpoint `GET /analytics/heat-islands` com faixas `heat_band` no mapa
- **Simulação de ilha de calor v1.1** — modelo temperatura-driven exploratório (ver [§19.1](#191-simulação-de-ilha-de-calor-v11))
- **Vulnerabilidade multidimensional** — saúde × risco, segurança × risco, capacidade fiscal
- **Prioridade de planejamento** — combinação IVC + IRI + lacunas de dados
- **Atlas Econômico (UF)** — contexto estadual IPEA/RFB via `atlas_economico_service` (referência, não municipal)
- **Exposição SINGED Lab** — população/domicílios/estabelecimentos na área afetada (RS 2024, CNEFE)

---

## 7. Módulos funcionais

### Etapa 1 — Onboarding Engine

**Arquivo:** `onboarding_engine.py` · **API:** `/api/v1/onboarding`

- Valida código IBGE contra malha oficial
- Carrega geometria municipal, bairros e setores censitários
- Dispara integrações IBGE, SICONFI e CAPAG
- Registra status em `municipios_seed`
- Permite expansão sob demanda além dos 61 municípios seed

### Etapa 2 — Maturidade Municipal

**Arquivo:** `maturity_engine.py` · **API:** `/api/v1/maturity`

- Calcula score 0–100 e classificação Bronze→Platina
- Lista fontes presentes, faltantes e recomendações
- Recálculo sob demanda após novas integrações

### Etapa 3 — Painel Executivo e Analytics

**Arquivos:** `analytical_engine.py`, `ExecutiveDashboard.tsx` · **API:** `/api/v1/indicators`, `/api/v1/analytics`

- KPIs municipais (população, PIB, CAPAG, alertas)
- Ranking de bairros por Score
- Comparador entre municípios
- Clima urbano oficial (INMET) + timeline estimada
- Catálogo de cobertura de dados (`/data-catalog/coverage`)
- Central da Oficina: narrativa guiada e export HTML

### Etapa 4 — Diagnóstico Executivo Automático

**Arquivo:** `executive_diagnostic_engine.py` · **API:** `/api/v1/diagnostic`

Gera narrativa Markdown com 7 seções:

1. Contexto municipal (IBGE, bioma, mesorregião)
2. Situação fiscal e CAPAG (indicadores 1–3)
3. Score Sinidu+Clima e interpretação
4. Áreas críticas (top bairros)
5. Alertas e desastres recentes
6. Lacunas de dados e maturidade
7. Recomendações prioritárias

- Auto-geração após onboarding bem-sucedido
- Histórico versionado em `diagnosticos_executivos`

### Etapa 5 — Simulações Territoriais

**API:** `/api/v1/simulations`

| Simulação | Endpoint | Descrição |
|-----------|----------|-----------|
| Impermeabilização | `POST /waterproofing` | Aumento de área impermeável |
| Perda de vegetação | `POST /vegetation-loss` | Redução de cobertura verde (bidirecional: desmatar ↔ arborizar) |
| Ilha de calor | `POST /heat-island` | Temperatura de pico + UHI por bairro (modelo v1.1, °C) |
| Comparador LST × simulado | `POST /heat-lst-compare` | LST observada (GeoReDUS) vs simulação Sinidu |
| Chuva extrema | `POST /extreme-rainfall` | Cenário de precipitação intensa |
| Déficit de drenagem | `POST /drainage-deficit` | Capacidade reduzida de escoamento |

- Resultados visualizados no mapa (GeoJSON)
- Geração de plano de mitigação (`/mitigation-plan`)
- Geração de plano de contingência a partir de simulação

### Etapa 6 — Predição ML de Alagamento

**Arquivo:** `backend/ml/` · **API:** `POST /api/v1/predictions/flood-risk`

- Modelo scikit-learn treinado por ETL (`etl_flood_ml.py`)
- Disponível para 5 municípios prioritários
- Features: precipitação, impermeabilização, declividade, histórico S2ID

### Etapa 7 — Contingência e Monitoramento

**Arquivos:** `contingency_planner.py`, `cemaden_monitor.py`, `weather_monitor.py`

#### Contingência (`/api/v1/contingency`)

- CRUD de planos de contingência municipal
- Templates COBRADE por nível (VERDE→VERMELHO) e cenário
- Desenho de zonas no mapa (`ContingencyDrawMap`)
- Ativação de plano + exportação PDF
- Rotas de evacuação via OSRM (fallback geodésico)

#### Monitoramento (`/api/v1/monitoring`)

- Dashboard consolidado CEMADEN + clima + alertas internos
- Visão multi-município (`/map-overview`)
- WebSocket em tempo real: `WS /ws/alerts/{codigo_ibge}`
- Push Gotify para alertas LARANJA e VERMELHO

### Etapa 8 — Assistente Municipal

**Arquivos:** `municipal_assistant_context.py`, `backend/rag/` · **API:** `/api/v1/assistant`

- Chat com contexto municipal enriquecido (IBGE, CAPAG, Score, S2ID, maturidade, diagnóstico)
- RAG sobre corpus normativo (7 textos + 2 PDFs internos)
- Citação obrigatória de fontes: `[Fonte: …]`
- Perguntas sugeridas por município
- Multi-provedor: Ollama (padrão), Gemini, OpenAI, Anthropic, Groq, Mistral, OpenRouter
- Ponte Siconfi.IA para perguntas fiscais (`siconfi_ia_bridge.py`)

### Etapa 9 — Plano de Ação Territorial

**Arquivo:** `action_plan_engine.py` · **API:** `/api/v1/action-plan`

- Ações em curto, médio e longo prazo
- Classificação de custo: Baixo / Médio / Alto
- Vinculação a programas federais (`federal_financing_catalog.py`):
  - Pro-Cidades (MCID)
  - Fundo Clima (MMA)
  - PAC Seleções
  - SNUC / Programa Águas
  - entre outros
- Auto-geração após diagnóstico executivo
- Histórico versionado

### Terreno 3D e simulação volumétrica (Fase A)

**Backend:** `dem_processor.py`, `hydro_simulator.py` · **API:** `/api/v1/terrain`, `/api/v1/simulations`

- Download SRTM via OpenTopography; upload LiDAR local (`POST /terrain/{ibge}/import-local-dem`)
- Tiles Terrarium (encoding `terrarium`) para MapLibre GL 4.7 via CDN
- Simulação pluvial retorna GeoJSON com faixas `depth_band` (`superficial`, `moderada`, `critica`) e propriedades `depth_min_m`, `depth_max_m`, `precipitation_mm`
- Perda de vegetação retorna `temp_increase_celsius` por polígono (ilha de calor)

**Frontend 3D** (`Map3DMapLibreContainer.tsx`):

| Recurso | Implementação |
|---------|---------------|
| Terreno inclinado | `pitch` ~62–68°, `fitBounds` automático após simulação |
| Extrusão de manchas | `fill-extrusion` em `maplibreLayers.ts`; altura = média `(depth_min_m + depth_max_m) / 2` |
| Ilha de calor | Extrusão proporcional a `temp_increase_celsius × 12` |
| Inspeção por clique | `queryTerrainElevation` + painel (solo, +cm água, cota da água) via `floodInspect.ts` |
| Auto 3D | `PlatformApp` alterna para modo 3D ao concluir simulação pluvial ou de calor |
| Controles | Basemap satélite/escuro, exagero de relevo (1–4×), inclinação manual |

**Não integrado ao fluxo principal:** `Map3DGoogleContainer.tsx` (Google Street View — requer API key paga; mantido apenas como referência).

**Limitação:** DEM SRTM 30 m (±16 m vertical). Piloto Recife pode usar LiDAR local para curvas e simulação refinada; extrusão 3D ainda usa resolução do raster disponível.

### Relatórios PDF

**Arquivo:** `report_generator.py` · **API:** `/api/v1/reports`

Conteúdo do relatório municipal:

- Capa e identificação
- Mapa (Google Maps link + imagem estática opcional)
- Indicadores IBGE e fiscal (CAPAG 1–3)
- Score Sinidu+Clima com base teórica
- Ranking de bairros
- Programas federais sugeridos (órgão e contato)
- Previsão climática (Open-Meteo)
- Histórico de gerações

**Relatório completo (Step 8):** template `municipal_report_completo.html` (8+ páginas) com gráficos Python (`chart_generator.py`), radar de score, mapa estático e narrativa IA. Endpoint assíncrono: `POST /reports/municipal/codigo/{ibge}/completo?async=true`.

---

## 8. API REST e WebSocket

**Base URL:** `http://localhost:8000`  
**Prefixo:** `/api/v1`

### Resumo por router (~65 endpoints REST)

| Router | Prefixo | Principais operações |
|--------|---------|---------------------|
| `indicators` | `/indicators` | Municípios, seeds, executive (Score + Atlas), camadas GeoJSON |
| `analytics` | `/analytics` | Índices, ilhas de calor, clima, diagnóstico, comparação, Sentinel |
| `simulations` | `/simulations` | 6 simulações + mitigação + comparador LST |
| `assistant` | `/assistant` | Chat, provedores, contexto municipal, casos |
| `data_catalog` | `/data-catalog` | Cobertura, SINGED Lab, import CSV, refresh |
| `map` | `/map` | Tiles raster externos (mosaicjson) |
| `geoportal` | `/geoportal` | Upload CTM, API ArcGIS/GeoJSON, importação malha |
| `integrations` | `/integrations` | Status e sync manual |
| `reports` | `/reports` | Gerar PDF, histórico, download |
| `predictions` | `/predictions` | Risco de alagamento ML |
| `terrain` | `/terrain` | DEM, declividade, processamento |
| `contingency` | `/contingency` | CRUD planos, PDF, templates COBRADE |
| `monitoring` | `/monitoring` | Dashboard, alertas, mapa overview |
| `onboarding` | `/onboarding` | Validar, executar, status |
| `maturity` | `/maturity` | Score de maturidade |
| `diagnostic` | `/diagnostic` | Gerar e consultar diagnósticos |
| `action_plan` | `/action-plan` | Gerar e consultar planos de ação |

### WebSocket

```
WS /ws/alerts/{codigo_ibge}
```

Broadcast de alertas CEMADEN e internos para o frontend (`useAlertWebSocket`).

### Health check

```
GET /
```

Retorna status, nome da plataforma e município piloto.

---

## 9. Interface web (frontend)

**URL:** `http://localhost:3000`  
**Arquitetura:** Next.js App Router — rotas por módulo (`/painel`, `/simulacoes`, `/auditoria`…) com shell compartilhado `PlatformApp.tsx` e estado Zustand (`useAppStore`).

### Abas principais

| Aba | Rota | Componente | Funcionalidade |
|-----|------|------------|----------------|
| Painel | `/painel` | `ExecutiveDashboard` | KPIs, maturidade, diagnóstico PDF, plano de ação, relatório completo IA |
| Municípios | `/municipios` | `OnboardingPanel` | Cadastro, validação e geoportal municipal (upload CTM) |
| Catálogo | `/catalogo` | `DataCatalogPanel` | Panorama nacional, lacunas institucionais, GeoReDUS, SINGED Lab |
| Simulações | `/simulacoes` | `SimulationPanel` | Chuva, preditiva, asfalto, vegetação, ilha de calor, drenagem + comparador LST + IA |
| Monitor | `/monitor` | `MonitoringPanel` | CEMADEN, clima, timeline, ativação |
| Contingência | `/contingencia` | `ContingencyWizard` | CRUD plano, desenho de zonas, PDF |
| Assistente | `/assistente` | `AssistantPanel` | Chat IA com contexto municipal |
| Casos | `/casos` | `CaseStudiesPanel` | Busca semântica de casos de sucesso |
| Auditoria | `/auditoria` | `AuditPanel` | Trilha de ações (admin ou `AUTH_ENABLED=false`) |
| Sistema | `/sistema` | `SystemPanel` | Jobs, pipeline MCID, saúde operacional |

### Central da Oficina (Step 9)

Componente flutuante `WorkshopCenter.tsx` sobre o mapa:

- **Diagnóstico** — gera/atualiza diagnóstico executivo (tooltip com hora se gerado hoje)
- **Apresentar** — abre `/apresentacao/{ibge}` com loading rotativo
- **Relatório** — dropdown rápido / completo (8+ págs)
- **Comparar** — modal `CompareModal` (tabela Score/IVC/IRI/CAPAG, radar Recharts, narrativa IA, export PDF)

### Mapa

- **2D:** Leaflet com 18+ camadas temáticas, manchas de simulação, LST observada (raster externo), curvas de nível e vetores D8
- **3D:** MapLibre GL + DEM Terrarium (`Map3DMapLibreContainer`)
- Toggle **Mapa 2D** / **Terreno 3D** no canto superior direito
- Sincronização de camadas via `layerStyles.ts` e `maplibreLayers.ts`
- Painel **Camadas ativas (N)** com ordem e opacidade (`ActiveLayersPanel`)
- Seletor de **ano por tema** (MapBiomas, S2ID, PIB, LST, INEP)
- Toggle **dados regionais** (município vs mesorregião/RM)
- Após simulação pluvial ou ilha de calor: modo 3D automático + painel de inspeção por clique

### Catálogo de dados (componentes Fase 15/16)

| Componente | Função |
|------------|--------|
| `GeoReDusReferenceCard` | Deep link `municipioId` para o portal GeoReDUS |
| `InstitutionalGapsPanel` | Lacunas nacionais que exigem convênio MCID |
| `SingedLabPanel` | Exposição RS 2024 + importação CSV (gestor) |

### Recursos transversais (Step 9)

| Recurso | Componente | Onde aparece |
|---------|------------|--------------|
| Loading rotativo | `RotatingLoader.tsx` | PDF, simulação, IA, apresentação, recarga município |
| Tooltips técnicos | `TermTooltip.tsx` | CAPAG, IVC, IRI, Score, SRTM no Painel e Simulações |
| Banner onboarding | `OnboardingBanner.tsx` | Painel — só se `onboarding_status != concluido` |
| Progresso carga | `MunicipioLoadProgress.tsx` | Ao trocar município |
| Agente proativo | `AgenteSinidu` | Chat contextual por aba |
| Shimmer simulação | overlay em `PlatformApp` | Enquanto `simulating=true` |

### Recursos transversais (geral)

- Seletor de 61 municípios prioritários + carregados no DB
- Toast de alertas via WebSocket
- Banner offline quando API indisponível
- Cliente HTTP tipado em `frontend/src/utils/api.ts`

---

## 10. Integrações externas

### Coletores automáticos (scheduler)

| Fonte | Módulo | Frequência | Dados |
|-------|--------|------------|-------|
| IBGE | `ibge_collector.py` | Domingos 03:00 | População, PIB, série PIB (`pib_serie`), área, prefeito |
| IPEA/Atlas | `ipeadata_collector.py` | Sob demanda / sync | IDH municipal (Atlas Brasil) |
| SINGED Lab RS | `singedlab_rs_collector.py` | Sync batch (orchestrator) | Exposição CNEFE enchentes RS 2024 |
| SICONFI | `siconfi_collector.py` | Domingos 03:00 | Receitas, despesas, dívida |
| CAPAG | `capag_collector.py` | Domingos 03:00 | Nota A–D, indicadores 1–3 |
| SNIS/SINISA | `snis_sinisa_collector.py` | Domingos 03:00 (sync semanal) | Saneamento |
| Fontes externas | `external_sources_collector.py` | Sync semanal + job batch | AdaptaBrasil, GeoSGB, SIRENE, Brasil MAIS (derivados/postGIS) |
| CEMADEN | `cemaden_monitor.py` | A cada 30 min | Alertas hidrológicos |
| Open-Meteo | `weather_monitor.py` | A cada 55 min | Previsão 7 dias + probabilidade de risco |

### APIs consultadas sob demanda

| Fonte | URL / serviço | Uso |
|-------|---------------|-----|
| IBGE | servicodados.ibge.gov.br | Malhas, pesquisas 33/38 |
| Tesouro (SICONFI) | apidatalake.tesouro.gov.br | Dados fiscais |
| Tesouro (CAPAG) | CKAN tesourotransparente.gov.br | Planilha CAPAG |
| CEMADEN | cemaden.gov.br/mapainterativo/alertas.json | Alertas |
| Open-Meteo | api.open-meteo.com | Clima |
| INMET | apitempo.inmet.gov.br | Estações oficiais |
| OpenTopography | portal.opentopography.org | SRTM DEM |
| Sentinel STAC | earth-search.aws.element84.com | Imagens satélite |
| OSM Overpass | overpass-api.de | Infraestrutura urbana |
| OSRM | Container local :5000 | Rotas de evacuação (multi-região Geofabrik) |
| Gotify | Container local :8888 | Push notifications |
| Google Maps | Static Maps API (opcional) | Mapa no PDF |
| Siconfi.IA | siconfi-ia.tesourotransparente.gov.br | Perguntas fiscais |
| GeoReDUS | redus.org.br/georedus | Referência nacional, LST raster (mosaicjson) |
| IBGE SINGED Lab | ibge.gov.br/singedlab | Export CSV manual (sem API pública) |
| IPEA Atlas Econômico | ipea.gov.br/atlaseconomico | Contexto estadual (link) |

### Dados referenciados (tabelas + ETL)

- **S2ID** — histórico de desastres
- **MapBiomas** — cobertura vegetal
- **SINGED Lab RS** — exposição populacional oficial nas áreas afetadas (6 municípios RS do piloto)
- **CNES/DataSUS** — estabelecimentos de saúde
- **SINESP** — indicadores de segurança pública
- **Adapta Brasil / GeoSGB / SIRENE / Brasil MAIS** — tabela `municipio_fontes_externas` (migration 012); status dinâmico no catálogo

### Malha viária OSRM (Fase 9)

- Regiões Geofabrik: `pernambuco`, `nordeste`, `sudeste`, `sul`, `centro-oeste`, `norte`, `brazil`
- Setup: `OSRM_REGION=nordeste bash docker/osrm/setup-osrm.sh`
- Status: `GET /api/v1/routing/status` — UFs cobertas, região ativa, saúde do serviço
- Fallback geodésico: distância Haversine + duração estimada (40 km/h) quando UF fora da cobertura ou OSRM offline
- Variáveis: `OSRM_URL`, `OSRM_REGION`, `OSRM_COVERED_UFS` (opcional; padrão derivado da região)

---

## 11. Inteligência artificial e RAG

### Pipeline RAG

1. **Corpus** — textos normativos em `backend/rag/corpus/texts/` + PDFs em `documentacao/`
2. **Ingestão** — `etl_rag_ingest.py` chunking + embedding
3. **Armazenamento** — pgvector (`rag_documents`, 768d)
4. **Retrieval** — busca por similaridade no chat
5. **Geração** — LLM com prompt reforçado para citar fontes

### Corpus indexado

| Documento | Categoria |
|-----------|-----------|
| Lei 12.608/2012 (PNPDEC) | Legislação |
| Lei 14.026/2020 (Saneamento) | Legislação |
| Resolução CONAMA 369/2006 | Legislação |
| Resolução CONAMA 303/2002 (APPs) | Legislação |
| Portaria MCID 1.012/2025 | Legislação |
| AdaptaBrasil — Guia INPE | Guias |
| Manual SEDEC/MI — Gestão de Riscos | Guias |
| Documentação técnica Sinidu+Clima (PDF) | Sinidu |
| Explicação simplificada (PDF) | Sinidu |

### Provedores LLM

Configurável via `AI_CHAT_PROVIDER` e chaves de API:

- `ollama` (padrão, local, sem custo)
- `gemini` (recomendado quando `GEMINI_API_KEY` disponível)
- `openai`, `anthropic`, `groq`, `mistral`, `openrouter`

### Contexto municipal no assistente

O `MunicipalAssistantContext` injeta no prompt:

- Snapshot executivo (Score, IVC, IRI)
- Dados IBGE e CAPAG
- Alertas CEMADEN e desastres S2ID
- Maturidade e lacunas
- Diagnóstico executivo (se existir)
- Resumo do último relatório
- URL GeoReDUS do município (`georedus_url`)

### Ferramentas contextuais (agent tools)

O agente contextual (`contextual_agent_tools.py`) expõe 8 ferramentas, incluindo:

| Tool | Uso |
|------|-----|
| `get_georedus_referencia` | Quando dado local ausente, sugere indicador GeoReDUS com deep link |
| `get_catalog_coverage` | Maturidade e lacunas do catálogo |
| `get_executive_snapshot` | KPIs e Score |
| demais | Simulações, contingência, diagnóstico, etc. |

Regra no prompt: **não duplicar ingestão nacional** — citar GeoReDUS como referência externa quando a fonte Sinidu estiver em lacuna.

---

## 12. ETL e pipelines de dados

Scripts em `backend/etl/`:

| Script | Função |
|--------|--------|
| `etl_ibge.py` | Malha municipal IBGE → PostGIS |
| `etl_osm.py` | OSM Overpass → infraestrutura_urbana |
| `etl_inmet.py` | Seed S2ID, CEMADEN, MapBiomas (demo Recife) |
| `etl_saude_cnes.py` | CNES → estabelecimentos e indicadores de saúde |
| `etl_seguranca_sinesp.py` | SINESP ou CSV fallback → segurança |
| `etl_sentinel.py` | Sentinel-2 STAC (Element84) |
| `etl_dem_srtm.py` | OpenTopography SRTM → tiles Terrarium |
| `etl_flood_ml.py` | Treino modelo preditivo de alagamento |
| `etl_rag_ingest.py` | Ingestão corpus RAG |
| `etl_municipios_seed.py` | Seed 61 municípios |
| `etl_runner.py` | Orquestrador (IBGE + OSM + INMET + casos) |
| `import_singedlab_csv.py` | Import manual CSV SINGED Lab → seed + sync DB |

Scripts de importação curada (`backend/scripts/`) complementam coletores automáticos quando a fonte não expõe API pública (ex.: SINGED Lab retorna 403 em fetch automatizado).

---

## 13. Relatórios e documentos

### Relatório municipal (PDF)

- Template HTML: `backend/app/reports/templates/municipal_report.html`
- Engine: WeasyPrint
- Armazenamento: volume `reports_data`
- Histórico: tabela `relatorios_municipais`

### Plano de contingência (PDF)

- Template: `backend/app/reports/templates/contingency_plan.html`
- Engine: `contingency_report.py`

### Documentação do projeto

| Arquivo | Descrição |
|---------|-----------|
| `documentacao/Sinidu_Clima_Documentacao_Tecnica.pdf` | Documentação técnica (gerada) |
| `documentacao/Sinidu_Clima_Explicacao_Simplificada.pdf` | Versão simplificada |
| `documentacao/DOCUMENTACAO_TECNICA_COMPLETA.md` | Este documento |
| `scripts/gerar_pdfs_documentacao.py` | Gerador dos PDFs acima |

---

## 14. Agendamento e jobs em background

| Job | Cron / intervalo | Serviço |
|-----|------------------|---------|
| Sync IBGE + SICONFI + CAPAG + SNIS + fontes externas | Domingos 03:00 | `IntegrationOrchestrator` |
| Pipeline territorial (opcional) | Domingos 04:30 | `background_jobs.run_pipeline_job` |
| Jobs admin (onboarding, MapBiomas, PDFs, diagnósticos) | Sob demanda | `POST /api/v1/system/jobs/*` |
| Sync CEMADEN | A cada 30 min | `CemadenMonitor` |
| Sync Open-Meteo | A cada 55 min | `WeatherMonitor` |
| Limpeza cache clima | Diário 04:15 | `WeatherMonitor` |
| Backup PostGIS | Diário 02:30 | `postgis_backup` |

### Exportação em lote (produto)

| Job | Endpoint | Descrição |
|-----|----------|-----------|
| Diagnósticos executivos | `POST /system/jobs/diagnostics-batch` | Até 61 municípios carregados |
| Relatórios PDF | `POST /system/jobs/reports-batch?force=true` | Gate maturidade Prata (override admin) |
| Fontes externas | `POST /system/jobs/fontes-externas-batch` | Adapta/GeoSGB/SIRENE/Brasil MAIS |

Implementação: APScheduler em `backend/app/data_connectors/scheduler.py`; jobs assíncronos em `background_jobs.py`.

---

## 15. Testes automatizados

Diretório: `backend/tests/` (pytest)

Cobertura inclui: conectores (IBGE, SICONFI, CAPAG, SNIS, fontes externas, IPEA/IDH, SINGED Lab), simulação de calor (`test_heat_simulator`), PIB série, GeoReDUS (`test_georedus_reference_service`), rasters externos, geoportal, agente contextual, RAG, ML, onboarding, maturidade, DEM, relatórios, OSRM, batch export, engine analítico, auth/OIDC, system/jobs.

Execução:

```bash
docker exec sinidu_backend pytest
```

---

## 16. Variáveis de ambiente

Principais variáveis (`docker-compose.yml`):

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DATABASE_URL` | postgresql://…@db:5432/sinidu_db | Conexão PostgreSQL |
| `REDIS_URL` | redis://redis:6379/0 | Cache |
| `OLLAMA_BASE_URL` | http://ollama:11434 | Servidor Ollama |
| `OLLAMA_CHAT_MODEL` | llama3.1:8b-instruct-q4_K_M | Modelo de chat |
| `OLLAMA_EMBED_MODEL` | nomic-embed-text | Modelo de embedding |
| `AI_CHAT_PROVIDER` | ollama | Provedor LLM ativo |
| `OSRM_URL` | http://osrm:5000 | Roteamento |
| `OSRM_REGION` | nordeste | Região Geofabrik processada |
| `OSRM_COVERED_UFS` | (derivado da região) | UFs com malha viária |
| `AUTH_ENABLED` | false (dev) | JWT + roles |
| `SCHEDULED_PIPELINE_ENABLED` | false | Pipeline domingo 04:30 |
| `GOTIFY_URL` | http://gotify:80 | Push notifications |
| `GOTIFY_TOKEN` | (vazio) | Token de app Gotify |
| `OPENTOPOGRAPHY_API_KEY` | (vazio) | DEM SRTM |
| `GOOGLE_MAPS_API_KEY` | (vazio) | Mapa estático no PDF |
| `GEMINI_API_KEY` | (comentado) | Assistente cloud |
| `REPORTS_DIR` | /data/reports | PDFs gerados |
| `DEM_DIR` | /data/dem | Tiles de terreno |
| `ML_DATA_DIR` | /data/ml | Dados ML |
| `MODELS_DIR` | /data/models | Modelos serializados |

---

## 17. Fluxo operacional do gestor

```
1. Onboarding          → Integrar município (malha + IBGE + CAPAG)
        ↓
2. Painel Executivo    → Visualizar Score, KPIs, mapa, maturidade
        ↓
3. Diagnóstico         → Narrativa automática (7 seções)
        ↓
4. Plano de Ação       → Carteira de ações + programas federais
        ↓
5. Simulações          → Testar cenários; mapa 3D com extrusão e inspeção por clique
        ↓
6. Contingência        → Plano COBRADE + rotas OSRM + PDF
        ↓
7. Monitoramento       → Alertas CEMADEN + clima + WebSocket
        ↓
8. Comparação / Oficina → Comparar municípios, apresentação guiada, auditoria
        ↓
8. Assistente          → Perguntas com citação de fontes
        ↓
9. Relatório PDF       → Entrega formal ao gestor
```

Comandos úteis para validação:

```bash
# Gerar relatório PDF
curl -X POST http://localhost:8000/api/v1/reports/municipal/codigo/2611606

# Gerar diagnóstico executivo
curl -X POST http://localhost:8000/api/v1/diagnostic/generate/2611606

# Gerar plano de ação
curl -X POST http://localhost:8000/api/v1/action-plan/generate/2611606

# Contexto do assistente
curl http://localhost:8000/api/v1/assistant/municipal/2611606/context
```

---

## 18. Limitações e considerações

### 18.1 Teto de acurácia — triagem ≠ laudo (20h.7)

O Sinidu+Clima **prioriza e ensina contingência**. Não substitui:

1. Projeto hidráulico / laudo de engenharia / perícia judicial  
2. Modelagem hidrodinâmica 2D (HEC-RAS, SWMM) nem inventário completo de galerias  
3. Alerta oficial CEMADEN ou acionamento normativo da Defesa Civil  
4. IDF oficial municipal/ANA/INMET — tabelas internas são `Estimado` até 20h.4  

**O que o produto pode afirmar com honestidade:** manchas e scores com selo
(Oficial | Observado | Estimado | Derivado); hit-rate pontual contra S2ID quando houver
geometria; comparação LST observada (GeoReDUS) × cenário Sinidu (Derivado).

**Teto sem dados de rede / radar / cota de rio:** ordem de grandeza e ranking de bairros —
não profundidade calibrada metrificada para obra. Elevação do teto = Fase 21 (lastro
observacional) + 20h.4/20h.5 (IDF e manchas oficiais).

Ver também: `ESTADO_ATUAL_SINIDU.md` e `docs/CHECKLIST_LINGUAGEM_HONESTIDADE.md`.

### Hardware de referência

Desenvolvido e testado em Mac mini 2018 (Intel i5, 32 GB RAM). Ollama limitado a 12 GB no Docker. Encoding e processamento DEM são CPU-bound.

### Dados

- Malha de bairros genérica em municípios sem dados locais detalhados
- S2ID e MapBiomas podem usar seeds demo até ETL completo
- CAPAG depende do layout da planilha Tesouro Transparente (coletor com detecção automática de header)
- OSRM: região configurável via `OSRM_REGION` (padrão Nordeste); cobertura nacional exige PBF `brazil` (~1,5 GB+) ou troca de região
- Simulação pluvial comparada (120 vs 80 mm): ~60 s no piloto Recife (dois passes hidrológicos)
- Extrusão 3D é proxy visual (DEM 30 m); não substitui modelagem hidrodinâmica 2D
- **Simulação de ilha de calor v1.1** é exploratória (proxy °C); não substitui LST observada (GeoReDUS) nem estudo microclimático de campo
- **SINGED Lab** cobre apenas enchentes RS 2024; portal IBGE sem API — importação CSV manual
- **GeoReDUS** é referência externa (5.570 municípios); Sinidu opera nos 61 prioritários com simulação, contingência e IA
- **SGB/ANADEM** (16d.2) pendente de convênio CPRM — não iniciar ingestão sem trâmite A.1

### Visualização 3D

- Google Street View **não** está no fluxo principal (`Map3DGoogleContainer` isolado)
- Precisão vertical limitada pelo SRTM/Terrarium; LiDAR local melhora simulação 2D/curvas, não fachadas de rua

### Infraestrutura

- Frontend produção: `Dockerfile.prod` + `next build`; dev usa `next dev`
- Gotify e Google Maps são opcionais
- OpenTopography requer API key para download DEM em escala

### Segurança

- Autenticação JWT + roles (`admin`, `gestor_municipal`, `leitor`); desligável em dev (`AUTH_ENABLED=false`)
- OIDC gov.br / Keycloak (Fase 4); multi-tenant por UF/IBGE
- Chaves de API via variáveis de ambiente (não commitadas)
- CORS restrito via `CORS_ORIGINS` em staging/produção

---

## 19. Fase 15 — Novos indicadores e simulação climática

Trabalho concluído em julho/2026, integrado ao orchestrator, boot (migrations 017–018), API, catálogo e painel executivo.

### 19.1 Simulação de ilha de calor v1.1

**Arquivo:** `backend/app/services/heat_simulator.py`  
**API:** `POST /api/v1/simulations/heat-island`  
**Modelo:** `HEAT_MODEL_VERSION = "1.1"`

#### Posicionamento metodológico

| Aspecto | Simulação Sinidu v1.1 | LST observada (GeoReDUS) |
|---------|----------------------|--------------------------|
| Natureza | Proxy exploratório (°C ar) | Medição satélite (°C superfície) |
| Entrada | Temperatura de pico prevista + cenário de uso do solo | Série Landsat 8/9 agregada |
| Uso | Planejamento de cenários (arborizar, impermeabilizar) | Diagnóstico observado |
| Badge | Derivado Sinidu+Clima | Observado / Oficial |

#### Fórmula da intensidade UHI (ΔT) por bairro

```
ΔT = coef_imperm × impermeabilização
   + coef_urban × fração_urbana
   - coef_veg × fração_vegetação
   + coef_density × densidade_normalizada
   + amplificação_onda_calor
```

Coeficientes calibrados para cidades tropicais/subtropicais brasileiras (ΔT típico 2–6 °C):

| Coeficiente | Valor | Fonte conceitual |
|-------------|-------|------------------|
| `UHI_COEF_IMPERM` | 3.5 °C | Oke (1982) — superfície impermeável |
| `UHI_COEF_URBAN` | 1.2 °C | Calor antropogênico estrutural |
| `UHI_COEF_VEG` | 2.5 °C | Resfriamento por dossel (evapotranspiração) |
| `UHI_COEF_DENSITY` | 1.0 °C | Densidade populacional |
| `HEATWAVE_AMP_K` | 0.35 | Li & Bou-Zeid (2013) — sinergia onda de calor |

**Temperatura local** = temperatura de pico prevista + ΔT.

Impermeabilização derivada de classes MapBiomas por interseção espacial com o polígono do bairro. Baseline de temperatura obtida de `OfficialClimateService` (INMET) com fallback 27 °C.

#### Parâmetros de entrada (`IlhaCalorSimRequest`)

| Parâmetro | Descrição |
|-----------|-----------|
| `temperatura_pico_c` | Pico previsto para a cidade (°C); padrão 34 °C |
| `perda_vegetal_pct` | Cenário de desmatamento adicional (0–100%) |
| `ganho_vegetal_pct` | Cenário de arborização (0–100%) — slider bidirecional |
| `impermeabilizacao_extra_pct` | Impermeabilização adicional |

#### Saída

GeoJSON por bairro com propriedades:

- `temp_local_c` — temperatura simulada
- `uhi_intensity_c` — intensidade da ilha (ΔT)
- `heat_band` — faixa (`leve` / `moderada` / `severa`)
- `resfriamento_max_c` / `resfriamento_medio_c` — métricas de arborização

Visualização 3D: extrusão proporcional a `temp_increase_celsius × 12` em `maplibreLayers.ts`.

#### Comparador observado × simulado

**API:** `POST /api/v1/simulations/heat-lst-compare`  
Cruza resultado da simulação com LST observada (camada `lst_observada`) e gera narrativa IA com limites explícitos.

### 19.2 Camada analytics de ilhas de calor

**API:** `GET /api/v1/analytics/heat-islands`  
Proxy por bairro baseado em capacidade de adaptação (vegetação inversa). Camada `heat_band` em `layerStyles.ts`.  
Nota: série histórica interna é demonstrativa — substituir por integração oficial antes de uso conclusivo.

### 19.3 IDH municipal (IPEA / Atlas Brasil)

**Coletor:** `ipeadata_collector.py`  
**Serviço:** `atlas_economico_service.py`  
**Migration:** `018_pib_serie.sql` (PIB série) + colunas `idh` / `idh_ano` em `municipio_ibge`  
**Painel:** card Atlas Econômico no `ExecutiveDashboard` (contexto UF + link IPEA)

### 19.4 Série histórica de PIB

**Coletor:** `ibge_collector.py` (pesquisa 38, indicadores 46996/47000)  
Campo `pib_serie` (JSON) sincronizado no `IntegrationOrchestrator`.  
Seletor de ano no mapa (Fase 16c.2) consome esta série.

### 19.5 SINGED Lab RS — enchentes 2024

**Coletor:** `singedlab_rs_collector.py`  
**Migration:** `017_singedlab_rs.sql` → tabela `municipio_singedlab_rs`  
**Catálogo:** fonte `ibge_singedlab_rs` no `catalog_source_registry`

O portal IBGE não expõe API REST pública (fetch automatizado retorna 403). Estratégia:

1. Seed CSV curado: `backend/data/singedlab_rs_enchentes_2024.csv` (61 municípios)
2. Municípios RS do piloto (6): Porto Alegre, Canoas, Santa Maria, São Luiz Gonzaga, Bento Gonçalves, Caxias do Sul
3. Demais 55 municípios: `escopo = nao_aplicavel`

#### Importação curada (15.7)

| Componente | Descrição |
|------------|-----------|
| `singedlab_import_service.py` | Normalização flexível de colunas do export IBGE |
| `POST /data-catalog/singedlab/import-csv` | Upload CSV (gestor) + merge no seed + sync DB |
| `scripts/import_singedlab_csv.py` | CLI equivalente (`--sync-db`) |
| `SingedLabPanel.tsx` | UI no catálogo com métricas e botão de importação |

**APIs adicionais:**

```
GET  /api/v1/data-catalog/singedlab/{codigo_ibge}   # exposição municipal
POST /api/v1/data-catalog/singedlab/sync-all      # recarrega seed (gestor)
POST /api/v1/data-catalog/singedlab/import-csv    # upload CSV (gestor)
```

### 19.6 Testes

| Arquivo | Cobertura |
|---------|-----------|
| `test_heat_simulator.py` | Modelo v1.1, faixas, cenários vegetação |
| `test_ibge_pib_series.py` | Série PIB no coletor IBGE |
| `test_ipeadata_atlas_p1.py` | IDH / IPEA |
| `test_singedlab_collector.py` | Seed CSV, status catálogo |
| `test_singedlab_import_service.py` | Normalização e merge de importação |

---

## 20. Fase 16 — Complemento GeoReDUS

Integração paulatina com a plataforma [GeoReDUS](https://www.redus.org.br/georedus) (ReDUS/CEM-USP, 5.570 municípios). O Sinidu **não replica** o escopo nacional; referencia o GeoReDUS quando o dado local está ausente e mantém o diferencial (simulação, contingência, IA, maturidade).

### Posicionamento Sinidu × GeoReDUS

| GeoReDUS (referência externa) | Sinidu+Clima |
|------------------------------|--------------|
| Catálogo estático nacional | Operação em 61 municípios prioritários |
| LST observada (Landsat) | Simulação exploratória v1.1 + link LST |
| Indicadores Censo/INEP no mapa | Scores derivados, contingência, monitor, PDF |
| Download/visualização | Decisão + simulação + assistente + maturidade |

**Fora de escopo:** cobertura 5.570 municípios, catálogo completo saúde+educação, basemap MapTiler, substituir simulação por LST.

### Onda 16a — Quick wins ✅

| Item | Implementação |
|------|---------------|
| 16a.1 Link GeoReDUS | `GeoReDusReferenceCard` + deep link `?v=v0&municipioId={ibge}` |
| 16a.2 Busca global | Campo no `LayerPanel` + referências externas |
| 16a.3 Badge duplo calor | `SimulationPanel` — simulação Sinidu + link LST GeoReDUS |

### Onda 16b — Dados observados e Censo ✅

| Item | Implementação |
|------|---------------|
| 16b.1 LST observada | Camada `lst_observada`; tiles via `external_raster_service` |
| 16b.2 Comparador LST × simulado | `POST /simulations/heat-lst-compare` |
| 16b.3 Censo déficits | Migration `019_censo_deficits.sql`; subcamadas em `socioeconomico` |
| 16b.4 Metadados por camada | Tooltip/painel via `catalog_source_registry` + `layer_meta_registry` |

### Onda 16c — Educação, temporalidade e contexto regional ✅

| Item | Implementação |
|------|---------------|
| 16c.1 Educação INEP | Migration `020_educacao_inep.sql`; camada `educacao` |
| 16c.2 Ano por tema | Controle temporal unificado (MapBiomas, S2ID, PIB, LST, INEP) |
| 16c.3 Dados regionais | Toggle município vs mesorregião/RM no mapa |
| 16c.4 Camadas ativas (N) | `ActiveLayersPanel` — resumo, ordem, opacidade |

### Onda 16d — Territórios, risco geológico e IA

| Item | Status | Implementação |
|------|--------|---------------|
| 16d.1 Territórios especiais | ✅ | Migration `021`; camada `territorios_especiais` (quilombos, TIs, aglomerados) |
| 16d.2 SGB/ANADEM | ⬜ | Depende convênio CPRM (backlog A.1) |
| 16d.3 Assistente + GeoReDUS | ✅ | `georedus_reference_service.py`, tool `get_georedus_referencia`, RAG |
| 16d.4 Tiles raster externos | ✅ | `external_raster_service.py`, API `/map/external-rasters` |
| 16d.5 Geoportal municipal | ✅ | Migration `022`, `geoportal_service.py`, `GeoportalMunicipalPanel` |

### 20.1 Referência GeoReDUS no assistente (16d.3)

**Arquivo:** `georedus_reference_service.py`

Quando o usuário pergunta sobre tema com lacuna local, o assistente:

1. Detecta tema por palavras-chave (`GEOREDUS_INDICATORS`)
2. Cruza com lacunas do catálogo municipal
3. Retorna deep link `georedus_municipio_url(codigo_ibge)` e indicadores sugeridos
4. **Não ingere** dados nacionais — apenas referencia

Indicadores mapeados: déficits Censo, INEP, saúde CNES, territórios especiais, LST.

### 20.2 Tiles raster externos (16d.4)

**Arquivo:** `external_raster_service.py`  
**API:**

```
GET /api/v1/map/external-rasters
GET /api/v1/map/external-rasters/{layer_id}/config
GET /api/v1/map/external-rasters/{layer_id}/health
```

Registry de fontes `mosaicjson` (padrão GeoReDUS / TiTiler):

| `layer_id` | Fonte | Rescale padrão |
|------------|-------|----------------|
| `lst_observada` | GeoReDUS raster-server (Landsat 8/9, 2021–2025) | 20–60 °C |

Novas coberturas pesadas (MapBiomas raster, DSM) entram no registry com `status: em_avaliacao` — sem pipeline PostGIS.

**Frontend:** `MapContainer` carrega rasters genéricos via `externalRasters.ts`; colormap `turbo`, zoom 8–14.

### 20.3 Geoportal municipal (16d.5)

**Migration:** `022_municipio_geoportal.sql`  
**Modelo:** `MunicipioGeoportalPublicacao`  
**API:** `/api/v1/geoportal/{codigo_ibge}/*`

Fluxos suportados:

| Tipo | Endpoint | Descrição |
|------|----------|-----------|
| Upload GeoJSON | `POST .../upload` | Arquivo até 25 MB |
| Upload Shapefile | `POST .../upload` | ZIP com .shp/.dbf/.prj |
| API ArcGIS REST | `POST .../register-api` | FeatureServer/MapServer |
| URL GeoJSON | `POST .../register-api` | Fetch remoto |
| Importar malha | `POST .../import` | Persiste bairros em PostGIS |

**Frontend:** `GeoportalMunicipalPanel` no onboarding (`OnboardingPanel`).

Cadastro CTM pré-existente em `ctm_registry.py` complementa geoportais conhecidos.

### 20.4 Lacunas institucionais

**Frontend:** `InstitutionalGapsPanel` + `institutionalGaps.ts`  
Lista fontes que exigem convênio MCID (GeoSGB, Brasil MAIS, SIRENE, AdaptaBrasil, SINTER, CTM) com impacto estimado no Score e status derivado do catálogo.

### 20.5 Arquivos-chave

| Área | Arquivos |
|------|----------|
| Catálogo / lacunas | `DataCatalogPanel.tsx`, `InstitutionalGapsPanel.tsx`, `SingedLabPanel.tsx`, `GeoReDusReferenceCard.tsx` |
| Camadas mapa | `layerStyles.ts`, `MapContainer.tsx`, `externalRasters.ts`, `ActiveLayersPanel` |
| Backend | `georedus_reference_service.py`, `external_raster_service.py`, `geoportal_service.py`, `heat_simulator.py` |
| Assistente | `contextual_agent_tools.py`, `municipal_assistant_context.py`, `rag/chat.py` |
| Testes | `test_georedus_reference_service.py`, `test_external_raster_service.py`, `test_geoportal_service.py`, `test_contextual_agent.py` |

---

## Apêndice — Serviços backend

| Serviço | Arquivo | Responsabilidade |
|---------|---------|------------------|
| AnalyticalEngine | `analytical_engine.py` | IVC, IRI, camadas derivadas |
| OfficialClimateService | `official_climate.py` | Clima INMET |
| MunicipalReportGenerator | `report_generator.py` | PDF executivo |
| ExecutiveDiagnosticEngine | `executive_diagnostic_engine.py` | Diagnóstico automático |
| ActionPlanEngine | `action_plan_engine.py` | Plano de ação |
| OnboardingEngine | `onboarding_engine.py` | Carga municipal |
| MaturityEngine | `maturity_engine.py` | Score de maturidade |
| MitigationPlanner | `mitigation_planner.py` | Planos pós-simulação |
| MunicipioLoader | `municipio_loader.py` | Malhas IBGE |
| DemProcessor | `dem_processor.py` | SRTM, LiDAR local e terreno 3D |
| HydroSimulator | `hydro_simulator.py` | Simulação pluvial, faixas de profundidade, curvas D8 |
| DiagnosticReport | `diagnostic_report.py` | PDF diagnóstico executivo enriquecido |
| SocioeconomicEngine | `socioeconomic_engine.py` | Ranking intra-municipal (camada socioeconômico) |
| OsrmRouter | `osrm_router.py` | Rotas de evacuação |
| ContingencyPlanner | `contingency_planner.py` | Planos COBRADE |
| CobradeTemplates | `cobrade_templates.py` | Ações por nível |
| ContingencyReport | `contingency_report.py` | PDF contingência |
| CemadenMonitor | `cemaden_monitor.py` | Sync CEMADEN |
| WeatherMonitor | `weather_monitor.py` | Sync Open-Meteo |
| GotifyNotifier | `gotify_notifier.py` | Push mobile |
| AlertBroadcaster | `alert_broadcaster.py` | WebSocket |
| MunicipalAssistantContext | `municipal_assistant_context.py` | Contexto IA |
| SemanticSearch | `semantic_search.py` | Casos de sucesso |
| FederalFinancingCatalog | `federal_financing_catalog.py` | Programas federais |
| IntegrationOrchestrator | `data_connectors/orchestrator.py` | Sync integrações |
| HeatSimulator | `heat_simulator.py` | Ilha de calor v1.1 (°C) |
| AtlasEconomicoService | `atlas_economico_service.py` | Contexto UF IPEA/Atlas |
| SingedlabImportService | `singedlab_import_service.py` | Import CSV SINGED Lab |
| GeoReDusReferenceService | `georedus_reference_service.py` | Referência GeoReDUS no assistente |
| ExternalRasterService | `external_raster_service.py` | Registry mosaicjson (LST) |
| GeoportalService | `geoportal_service.py` | Upload/API CTM municipal |
| SiconfiIaBridge | `assistant/siconfi_ia_bridge.py` | Ponte fiscal |

---

*Documento atualizado a partir do inventário do repositório Sinidu+Clima — julho/2026 (Fases 15 e 16).*
