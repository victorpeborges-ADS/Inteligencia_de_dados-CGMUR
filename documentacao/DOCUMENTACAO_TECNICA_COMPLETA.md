# Sinidu+Clima — Documentação Técnica Completa do Sistema

**Plataforma Nacional de Inteligência Territorial**  
**Versão do documento:** junho/2026  
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
│  Painel · Municípios · Simulações · Monitor · Contingência ·    │
│  Assistente · Casos · Mapa 2D (Leaflet) / 3D (MapLibre)        │
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
| `frontend/` | Aplicação Next.js (SPA em `src/app/page.tsx`) |
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

### Camadas geoespaciais (GeoJSON)

Endpoint: `GET /api/v1/indicators/layers/{layer_name}`

Camadas disponíveis: `municipio`, `bairros`, `setores`, `socioeconomico`, `vulnerabilidade`, `inundacao`, `cobertura`, `desastres`, `alertas`, `infraestrutura`, `adaptacao_climatica`, `prioridade_planejamento`, `saneamento_drenagem`, `lacunas_dados`, `saude_risco`, `seguranca_publica`, `vulnerabilidade_multidimensional`.

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

- **Ilhas de calor urbanas** — impermeabilização + densidade + vegetação
- **Vulnerabilidade multidimensional** — saúde × risco, segurança × risco, capacidade fiscal
- **Prioridade de planejamento** — combinação IVC + IRI + lacunas de dados

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
| Perda de vegetação | `POST /vegetation-loss` | Redução de cobertura verde |
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

### Terreno 3D

**Arquivo:** `dem_processor.py` · **API:** `/api/v1/terrain`

- Download SRTM via OpenTopography
- Tiles Terrarium para visualização MapLibre 3D
- Análise de declividade e caminhos de escoamento
- Arquivos estáticos: `GET /static/dem/*`

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

---

## 8. API REST e WebSocket

**Base URL:** `http://localhost:8000`  
**Prefixo:** `/api/v1`

### Resumo por router (~55 endpoints REST)

| Router | Prefixo | Principais operações |
|--------|---------|---------------------|
| `indicators` | `/indicators` | Municípios, seeds, executive, camadas GeoJSON |
| `analytics` | `/analytics` | Índices, ilhas de calor, clima, diagnóstico, comparação, Sentinel |
| `simulations` | `/simulations` | 4 simulações + mitigação |
| `assistant` | `/assistant` | Chat, provedores, contexto municipal, casos |
| `data_catalog` | `/data-catalog` | Cobertura de dados |
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
**Arquitetura:** SPA única (`frontend/src/app/page.tsx`)

### Abas principais

| Aba | Componente | Funcionalidade |
|-----|------------|----------------|
| Painel | `ExecutiveDashboard` | KPIs, maturidade, diagnóstico, plano de ação, relatórios |
| Municípios | `OnboardingPanel` | Cadastro e validação de municípios |
| Simulações | `SimulationPanel` | Cenários + mitigação + contingência |
| Monitor | `MonitoringPanel` | CEMADEN, clima, timeline, ativação |
| Contingência | `ContingencyWizard` | CRUD plano, desenho de zonas, PDF |
| Assistente | `AssistantPanel` | Chat IA com contexto municipal |
| Casos | `CaseStudiesPanel` | Busca semântica de casos de sucesso |

### Mapa

- **2D:** Leaflet com 16 camadas temáticas e seletor de município
- **3D:** MapLibre GL + DEM Terrarium (`Map3DMapLibreContainer`)
- Toggle 2D/3D na barra lateral
- Sincronização de camadas via `layerStyles.ts` e `maplibreLayers.ts`

### Recursos transversais

- Seletor de 61 municípios prioritários + carregados no DB
- Toast de alertas via WebSocket
- Banner offline quando API indisponível
- Cliente HTTP tipado em `frontend/src/utils/api.ts`

---

## 10. Integrações externas

### Coletores automáticos (scheduler)

| Fonte | Módulo | Frequência | Dados |
|-------|--------|------------|-------|
| IBGE | `ibge_collector.py` | Domingos 03:00 | População, PIB, área, prefeito |
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

### Dados referenciados (tabelas + ETL)

- **S2ID** — histórico de desastres
- **MapBiomas** — cobertura vegetal
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

Cobertura inclui: conectores (IBGE, SICONFI, CAPAG, SNIS, fontes externas), RAG, ML, onboarding, maturidade, DEM, relatórios, OSRM, batch export, engine analítico, auth/OIDC, system/jobs.

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
5. Simulações          → Testar cenários e mitigação
        ↓
6. Contingência        → Plano COBRADE + rotas OSRM + PDF
        ↓
7. Monitoramento       → Alertas CEMADEN + clima + WebSocket
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

### Hardware de referência

Desenvolvido e testado em Mac mini 2018 (Intel i5, 32 GB RAM). Ollama limitado a 12 GB no Docker. Encoding e processamento DEM são CPU-bound.

### Dados

- Malha de bairros genérica em municípios sem dados locais detalhados
- S2ID e MapBiomas podem usar seeds demo até ETL completo
- CAPAG depende do layout da planilha Tesouro Transparente (coletor com detecção automática de header)
- OSRM: região configurável via `OSRM_REGION` (padrão Nordeste); cobertura nacional exige PBF `brazil` (~1,5 GB+) ou troca de região

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
| DemProcessor | `dem_processor.py` | SRTM e terreno 3D |
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
| SiconfiIaBridge | `assistant/siconfi_ia_bridge.py` | Ponte fiscal |

---

*Documento gerado a partir do inventário do repositório Sinidu+Clima — junho/2026.*
