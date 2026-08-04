# Relatório completo do sistema — Sinidu+Clima

**Versão do documento:** ago/2026  
**Público:** análise estratégica, técnica e de produto (MCID/CGMUR, equipe, homologação)  
**Complementa:** `DOCUMENTACAO_TECNICA_COMPLETA.md`, `ESTADO_ATUAL_SINIDU.md`, `docs/ROADMAP_GEMEO_DIGITAL_PLATEAU.md`, `docs/ROADMAP_PROXIMOS_PASSOS.md`

---

## 1. Sumário executivo

O **Sinidu+Clima** (plataforma de Inteligência de Dados — CGMUR/MCID) é um sistema nacional de **inteligência territorial climática** para municípios brasileiros. Combina:

1. **Diagnóstico** — vulnerabilidade, risco de inundação, maturidade de dados, capacidade fiscal/institucional  
2. **Simulação** — chuva extrema, calor, impermeabilização, drenagem, mitigações (com honestidade metodológica: *triagem*, não laudo hidrodinâmico)  
3. **Monitoramento e contingência** — alertas CEMADEN, planos COBRADE, disseminação  
4. **Apoio à decisão** — painel executivo, agente IA dual (operacional + normativo), relatórios PDF/SEI, casos de sucesso  
5. **Gêmeo digital incremental** — terreno 3D, edificações LOD1, exposição de ativos, camadas abertas (HAND, GloFAS, OSM)

**Posicionamento defensável:** não compete com CEMADEN em nowcast de radar; ocupa o nicho de **impacto municipal e intra-urbano** — cruzar clima com vulnerabilidade social, capacidade fiscal, infraestrutura e ação recomendada, com selos de qualidade honestos.

**Pilotos principais:** Recife (`2611606`), Camutanga (`2603603`), Ilha de Itamaracá (`2607604`), além de Aracaju, Salvador, SP, RJ, Brasília no conjunto alvo de onboarding.

---

## 2. Área de negócio e valor público

### 2.1 Problema que resolve

Gestores municipais (Defesa Civil, planejamento urbano, gabinete) precisam, sob pressão de eventos extremos:

- Saber **onde** o risco se concentra (bairro/setor/ativo)  
- **Simular** chuva/calor/impermeabilização sem contratar estudo de meses  
- Cruzar risco físico com **vulnerabilidade social** e **capacidade fiscal** (CAPAG, SICONFI)  
- Produzir **artefatos auditáveis** (PDF, SEI, KMZ, CSV) para sala de crise e prestação de contas  
- Onboardar municípios pequenos com dados abertos, sem CTM próprio

### 2.2 Personas e perfis UX

| Perfil | Foco na interface | Abas priorizadas |
|--------|-------------------|------------------|
| Defesa Civil | Alerta vivo, mancha, vias, ativos, contingência | Monitor, Simulações, Contingência |
| Planejamento | Cobertura, socioeconômico, prioridade, mitigação | Painel, Catálogo, Simulações |
| Prefeito / gabinete | Narrativa, KPIs, plano de ação, PDF | Painel, Apresentação |

Roles JWT: `admin` · `gestor_municipal` · `leitor` (Auditoria/Sistema só admin).

### 2.3 O que o produto **é** e **não é**

| É | Não é |
|---|--------|
| Plataforma de triagem e priorização territorial | Substituto de HEC-RAS / SWMM / 3Di |
| Apoio à decisão com incerteza declarada | Alerta oficial CEMADEN |
| Gêmeo digital *incremental* (LOD1 + DEM) | CityGML nacional tipo PLATEAU JP |
| ML de inundação quando `model_kind=full` | Probabilidade calibrada em todos os municípios |
| Camadas Oficiais / Referência / Derivado / Estimado | “Verdade única” sem selo |

### 2.4 Ciclo de valor (negócio)

```text
Onboarding municipal → Catálogo/maturidade de dados
        ↓
Painel (IVC, IRI, Score, semáforo, diagnóstico)
        ↓
Simulação (chuva/calor/…) → mapa 2D/3D + overlays operacionais
        ↓
Ativos/vias/HAND/GloFAS → CSV/KMZ/PDF
        ↓
Contingência COBRADE / Alertas / Plano de ação
        ↓
Auditoria + export SEI
```

---

## 3. Capabilidades funcionais (o que faz hoje)

### 3.1 Território e onboarding

- Seleção/ativação de município por IBGE  
- `ensureMunicipality` com steps (geometria, malha, fontes)  
- Bootstrap por UF  
- Malha de bairros: IBGE Censo 2022, CTM municipal, ou Voronoi estimado  
- Geoportal municipal (publicação / CTM)  
- Comparador entre municípios e apresentação executiva (`/apresentacao/{ibge}`, 8 slides)

### 3.2 Índices e painel executivo

- **IVC** — Índice de Vulnerabilidade Climática  
- **IRI** — Índice de Risco de Inundação  
- **Score Sinidu+Clima** — consolidação IVC+IRI+adaptação (+ fatores)  
- Semáforo de risco × alerta vivo CEMADEN (`risco_consolidado`)  
- KPIs, narrativa territorial, recomendações, plano de ação  
- Relatório municipal PDF (rápido/completo) e diagnóstico executivo  
- Ranking socioeconômico e déficits Censo 2022

### 3.3 Mapa e camadas

**Modos:** 2D (Leaflet) · 3D (MapLibre + terrain Terrarium) · swipe 2D↔3D e Antes↔Depois.

**Grupos de camadas (catálogo):**

| Grupo | Exemplos |
|-------|----------|
| Base | município, bairros |
| Dados urbanos | infraestrutura, educação INEP, edificações LOD1, socioeconômico, territórios especiais |
| Clima e riscos | cobertura MapBiomas, LST observada, vulnerabilidade, inundação (IRI), manchas oficiais, risco consolidado, HAND, hidrografia OSM, hazard GloFAS RP100, alertas, desastres |
| Planejamento | saneamento/drenagem, adaptação climática, prioridade, lacunas de dados |
| Saúde e segurança | saúde×risco, segurança pública, vulnerabilidade multidimensional |

Cada camada carrega **fonte**, **qualidade** e metadados no catálogo (`layer_meta_registry`).

### 3.4 Simulações

| Cenário | Entrada típica | Saída |
|---------|----------------|-------|
| Chuva extrema | mm, duração, nível do mar, drenagem | Manchas por profundidade, contornos, D8, timeline, vias, ativos, GloFAS overlap, exposição edifícios |
| Impermeabilização | % adicional | Mancha/impacto derivado |
| Ilha de calor | pico °C, vegetação | Superfície térmica + compare LST GeoReDUS |
| Déficit de drenagem | % déficit | Amplificação de alagamento |
| Mitigações | solar, telhado verde, infraverde, sombra | Delta vs baseline + plano |

**Extras pluviais recentes (maturidade open-data):**

- Motor hidro **2.10** — piso de vale local (menos “banheira”), grade fina em LiDAR ≤5 m  
- SoilGrids → grupo hidrológico A–D e Curve Number  
- Hidrografia OSM no motor e no mapa  
- Vias intransitáveis (≥35 cm)  
- Ativos críticos (escolas/saúde/abrigos)  
- HAND como suscetibilidade topográfica  
- GloFAS RP100 como hazard de referência + % overlap  
- Export **CSV impactos**, GeoJSON/KMZ enriquecidos, PDF oficina

### 3.5 Predição ML (inundação)

- Features físicas + precipitações + HAND/CN/drenagem/TWI  
- Labels: eventos observados / S2ID oficial  
- Modelos municipal e por bairro (HistGradientBoosting)  
- Política: só `model_kind=full` como probabilidade em produção  
- Cards de modelo, explicabilidade, bootstrap

### 3.6 Monitoramento e contingência

- Alertas CEMADEN / GeoRiscos, WebSocket `/ws/alerts/{ibge}`  
- Planos de contingência COBRADE (zonas, rotas OSRM, pontos de apoio)  
- Disseminação (WhatsApp/Gotify/webhook; SMS stub)  
- Eventos de campo observados pela Defesa Civil  
- Policy gate: ações críticas exigem `confirm=true`

### 3.7 Inteligência artificial

| Modo | Onde | Função |
|------|------|--------|
| Operacional (FAB) | Agente Sinidu | Contexto da página, streaming, ações no mapa |
| Normativo (aba) | Assistente | RAG (Lei 12.608, COBRADE, etc.), providers configuráveis |
| Interpretação | Pós-simulação | Resumo executivo, áreas críticas, equipamentos |

LLM: Ollama local (profile `ai`) e/ou Mistral/Gemini/etc. via env.  
**MCP** = ferramenta da equipe (Cursor), não runtime do painel web.

### 3.8 Catálogo, maturidade e operações

- Catálogo nacional de fontes com status/maturidade  
- Lacunas institucionais, impacto de fonte  
- Painel Sistema: saúde, jobs Redis, pipelines batch  
- Auditoria de ações, export SEI (PDF + hash)  
- Auth JWT + OIDC Keycloak/gov.br + multi-tenant UF/IBGE

---

## 4. Arquitetura técnica

### 4.1 Visão de camadas

```text
┌─────────────────────────────────────────────────────────────┐
│  Frontend Next.js 13 (PlatformApp) — Leaflet / MapLibre     │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST + WS
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI (backend/main.py) — /api/v1/* · /ws/alerts         │
│  AuthMiddleware · Metrics · CORS · Policy gate              │
└─┬─────────┬──────────┬──────────┬──────────┬────────────────┘
  │         │          │          │          │
  ▼         ▼          ▼          ▼          ▼
PostGIS   Redis     OSRM      Gotify     Ollama
+pgvector  jobs/     rotas     push       (opcional)
           cache
  │
  ▼
Volumes: DEM · models · reports · 3dtiles · citymodels · backups
Connectors → IBGE, S2ID, CEMADEN, MapBiomas, SNIS, INEP, CNES, …
```

### 4.2 Stack

| Camada | Tecnologias |
|--------|-------------|
| Frontend | Next.js 13, React 18, Zustand, Leaflet, MapLibre GL 4.7 (CDN), Tailwind, Recharts, Lucide |
| Backend | Python 3.10, FastAPI, SQLAlchemy, GeoAlchemy2, NumPy, SciPy, rasterio/GDAL, Shapely, scikit-learn, Jinja2/WeasyPrint |
| Dados | PostgreSQL/PostGIS, pgvector (RAG), Redis |
| Infra | Docker Compose (db, backend, frontend, redis, osrm, gotify; profiles ai/oidc/tls) |
| Auth | JWT HS256; OIDC Keycloak/gov.br (compose overlay) |

### 4.3 Backend — superfície API

Entrypoint: `backend/main.py`. Prefixo: `/api/v1`.

| Router | Domínio |
|--------|---------|
| `auth` | login, me, OIDC |
| `indicators` | camadas GeoJSON, meta, IVC/IRI |
| `analytics` | rankings, comparações |
| `simulations` | todos os cenários, jobs, exports |
| `predictions` | ML flood-risk |
| `terrain` | DEM, slope, config 3D |
| `buildings` | sync/export LOD1/2, tiles |
| `map` | rasters LST, screenshot |
| `monitoring` | alertas, sensores 3D, POIs, urban context |
| `contingency` | planos COBRADE |
| `assistant` | chat RAG / contextual |
| `data-catalog` / `maturity` / `onboarding` | dados e ativação |
| `diagnostic` / `action-plan` / `reports` | produtos executivos |
| `cases` | casos de sucesso |
| `audit` / `system` / `municipios` / `routing` / `geoportal` / `integrations` | ops e integração |

Estáticos: `/static/dem`, `/static/3dtiles`, `/static/citymodels`.

### 4.4 Domínios de serviço (backend)

~128 serviços em `backend/app/services/`. Núcleos:

- **Hydro:** `hydro_simulator`, calibração, HAND, SCS-CN, SoilGrids, OSM hidro, GloFAS, vias, ativos, drenagem, IDF, âncoras históricas  
- **DEM:** `dem_processor`, nDSM, perfil A→B, prewarm  
- **Risco:** `analytical_engine`, `risco_consolidado`, `risk_traffic_light`, `unified_risk_model`  
- **Buildings:** footprints, exposição, 3D Tiles, CityJSON, LOD2 mesh  
- **Clima urbano:** heat, LST compare, solar, green roof, sombra  
- **Contingência/alertas:** planner, live alert, public alert, broadcaster  
- **Produto:** diagnóstico executivo, maturidade, onboarding, planos de ação, catálogo  
- **IA:** agente contextual, semantic search, interpretador de simulação  

### 4.5 Modelo de dados (PostGIS) — principais tabelas

`municipios`, `bairros`, `setores_censitarios`, `historico_desastres_s2id`, `alertas_cemaden`, `cobertura_vegetal_mapbiomas`, `infraestrutura_urbana`, `edificacoes`, `escolas_inep`, `estabelecimentos_saude`, `territorios_especiais`, indicadores IBGE/fiscal/saneamento, séries pluvio/fluvio, `evento_alagamento_observado`, `contingency_plans`, `rag_documents`, `audit_log`, `integration_runs`, caches de previsão, etc. Geometrias em **EPSG:4326**.

### 4.6 Conectores de dados (~30)

Orquestrados por `orchestrator` / `scheduler`. Incluem: IBGE, SICONFI, CAPAG, SNIS/SINISA, MapBiomas, S2ID (municipal + nacional), CEMADEN pluvio, INMET BDMEP, MERGE CPTEC, ANA HidroWeb, malha territorial/CTM, OSM buildings + Microsoft footprints, INEP, CNES/saúde, equipamentos Recife, territórios especiais, Ipeadata, Censo déficits, SINESP, OSM landcover, AdaptaBrasil/GeoSGB/SIRENE (proxies).

### 4.7 Motor hidro (detalhe de negócio-técnico)

1. Carrega DEM (LiDAR local preferido; SRTM fallback)  
2. Downsample: LiDAR ≤5 m → até 1536; demais → 512  
3. Fill sinks (exceto DEM já hidro-condicionado)  
4. D8 accumulation + TWI + IRI raster + impermeabilidade  
5. SoilGrids ajusta `runoff_scale`  
6. Superfície por **piso de vale local** (~150 m), não banheira P10 municipal  
7. Boost por corpos d’água MapBiomas + **waterways OSM**  
8. Manchas `superficial` / `moderada` / `critica`  
9. Sidecars: contornos, flow paths, timeline, vias, ativos, meta (SoilGrids, GloFAS compare, drenagem, calibração)  
10. Versão `HYDRO_MODEL_VERSION` invalida cache Redis  

### 4.8 Frontend — estrutura

Shell único `PlatformApp` sobre App Router Next.js. Abas: Painel, Municípios, Catálogo, Simulações, Monitor, Contingência, Assistente, Casos, Auditoria, Sistema.

Estado global: Zustand (`useAppStore`). Cliente HTTP: `utils/api.ts` (~4k linhas). Design system institucional (teal, Source Sans 3, tokens em `design-system/`).

Fluxo de simulação: painel → API (sync/async + poll) → `handleSimulate` → overlays mapa + resultados + exports.

---

## 5. O que o sistema **pode** fazer (potencial imediato vs futuro)

### 5.1 Já implementado — usar agora

- Diagnosticar município onboarded com índices e narrativa  
- Simular chuva/calor/impermeabilização/drenagem e visualizar em 3D  
- Confrontar mancha com HAND, GloFAS, hidrografia OSM, manchas oficiais (se depositadas)  
- Listar vias e equipamentos atingidos; exportar CSV/KMZ/GeoJSON/PDF  
- Ativar plano de contingência e monitorar alertas  
- Consultar agente (normativo/operacional)  
- Auditar ações e gerar relatório SEI  

### 5.2 Pronto no código, dependente de dado/config

| Capacidade | Dependência |
|------------|-------------|
| ML `full` confiável | S2ID denso + séries pluvio + retreino |
| Alturas reais de prédios | MDS/nDSM (PE3D MDE ou LiDAR DSM) |
| Escolas oficiais fora do seed | Microdados INEP depositados |
| IDF oficial | JSON municipal em `backend/data/idf/` |
| ANA/INMET contínuos | Tokens + jobs de materialização |
| Auth/OIDC endurecido | Compose prod + Keycloak |
| Rotas OSRM de qualidade | Perfil regional carregado |

### 5.3 Roadmap explícito (ainda não feito)

Ver `docs/ROADMAP_PROXIMOS_PASSOS.md`:

- **A** — PDF com impactos, atalho de camadas, card SoilGrids na UI  
- **B** — dados oficiais densos (INEP, IDF, ANA, CPRM)  
- **C** — LOD2 UI, timeline UX, exposição por edifício/setor no mapa  
- **D** — hidrodinâmica 2D, ensembles climáticos (só com mandato)

### 5.4 Explicitamente fora do nicho

- Nowcasting radar nacional (CEMADEN)  
- Substituir laudo de engenharia hidrodinâmica  
- CityGML nacional sem programa de dados do Estado  

---

## 6. Qualidade, testes e operação

- ~**146** arquivos de teste backend (hydro golden, ML, buildings, auth, connectors, exports…)  
- Homologação e smoke scripts no repositório  
- Cache de simulação Redis + jobs assíncronos  
- Observabilidade: `/health`, `/metrics`, logs JSON  
- Backups PostGIS configuráveis  
- Compose: dev, LAN, prod, TLS, OIDC  

---

## 7. Riscos e limitações (para análise densa)

| Risco | Impacto | Mitigação atual |
|-------|---------|-----------------|
| Motor pluvial simplificado vs física 2D | Over/under-estimativa local | Selos Derivado; GloFAS/manchas oficiais; method-note |
| DEM downsample | Perda de microtopografia | Grade 1536 em LiDAR fino; HAND |
| Dados OSM incompletos em municípios pequenos | Vias/escolas faltando | Overpass on-demand; fallbacks |
| ML sem lastro | Falsa precisão | Bloqueio `full` vs heurística |
| Auth off em dev | Exposição se deploy errado | Compose prod força AUTH |
| Dependência de APIs externas (Overpass, SoilGrids, GloFAS) | Camadas vazias temporariamente | Cache em disco no DEM dir |

---

## 8. Matriz “quem usa o quê”

| Necessidade do gestor | Módulo | Artefato |
|----------------------|--------|----------|
| Onde está o risco agora? | Painel + risco consolidado + alerta vivo | Mapa semáforo |
| E se chover X mm? | Simulação chuva + 3D | Mancha + CSV impactos |
| Quais escolas/UBS? | Ativos críticos | Overlay + CSV |
| Quais ruas fecham? | Vias intransitáveis | Overlay vermelho |
| Isso bate com referência global? | GloFAS | Camada + % overlap |
| O solo ajuda/escóa? | SoilGrids/CN | Meta + (futuro card UI) |
| Plano de crise | Contingência | PDF COBRADE + rotas |
| Prestação de contas | Relatórios / SEI / Auditoria | PDF + hash |
| Base legal | Assistente normativo | RAG |

---

## 9. Indicadores de maturidade do produto (visão)

| Dimensão | Estado aproximado |
|----------|-------------------|
| Gêmeo 3D (terreno + LOD1) | Forte nos pilotos com DEM; LOD2 UI pausada |
| Simulação pluvial operacional | Forte (triagem); não hidrodinâmica |
| Open-data de confrontação | Forte após onda ago/2026 (HAND/GloFAS/OSM/SoilGrids) |
| Lastro observacional ML | Médio — depende de séries e S2ID |
| Contingência/monitor | Operacional |
| Escala nacional homogênea | Parcial — onboarding sob demanda, qualidade variável |
| Governança/auth/auditoria | Pronta para prod com overlays corretos |

---

## 10. Referências internas

| Documento | Uso |
|-----------|-----|
| `documentacao/DOCUMENTACAO_TECNICA_COMPLETA.md` | Detalhe API/metodologia |
| `documentacao/ESTADO_ATUAL_SINIDU.md` | O que é / não é |
| `docs/ROADMAP_GEMEO_DIGITAL_PLATEAU.md` | Fases 17–21 gémeo |
| `docs/ROADMAP_PROXIMOS_PASSOS.md` | Backlog pós open-data |
| `docs/CHECKLIST_LINGUAGEM_HONESTIDADE.md` | Linguagem pública |
| `docs/PLAYBOOK_DADOS_OBSERVADOS.md` | Séries e labels |
| `README.md` | Quick start |

---

## 11. Inventário quantitativo do repositório (ago/2026)

| Métrica | Valor |
|---------|------:|
| Serviços Python (`backend/app/services/`) | ~128 |
| Conectores de dados | ~34 |
| Routers API | 25 |
| Arquivos de teste backend | ~146 |
| Componentes React (`frontend/src/components`) | ~48 |
| Modelos SQLAlchemy principais | ~40 classes |
| Versão API (`main.py`) | 1.1.0 |
| Abas da plataforma | 10 (+ apresentação) |
| Camadas de mapa catalogadas | ~25 |

---

## 12. Índices e motor analítico (detalhe de negócio)

### 12.1 IVC — Índice de Vulnerabilidade Climática

Calculado em `analytical_engine.calculate_climate_vulnerability` (bairro) e variante por setor censitário.

**Lógica conceitual:** combina exposição climática (alagamentos históricos S2ID, cobertura impermeável MapBiomas, temperatura/LST quando disponível) com sensibilidade socioeconômica (renda, densidade, déficits habitacionais Censo) e capacidade adaptativa (vegetação, saneamento SNIS, adaptação AdaptaBrasil quando há proxy).

**Uso:** camada `vulnerabilidade`, contribuição ao Score, narrativa do painel, priorização de bairros.

### 12.2 IRI — Índice de Risco de Inundação

`calculate_flood_risk` / setores. Cruza histórico S2ID, proximidade hidrografia, topografia (HAND/DEM quando disponível), impermeabilidade e proxies de drenagem (SNIS).

**Uso:** camada `inundacao`, semáforo, entrada de ML, comparação com manchas oficiais.

### 12.3 Score Sinidu+Clima e risco consolidado

Consolida IVC + IRI + adaptação (+ fatores locais). O **risco consolidado** (“agora”) cruza Score com **alerta vivo CEMADEN** via `risco_consolidado_service` / `risk_traffic_light_service` — é o produto “sala de situação”: não só vulnerabilidade estrutural, mas estado operacional do dia.

### 12.4 Vulnerabilidade multidimensional (VM)

Camada `vulnerabilidade_multidimensional` — cruzamento saúde × clima × segurança × socioeconômico para leitura além do binário “alagou / não alagou”.

### 12.5 Capacidade fiscal e institucional

Tabelas `MunicipioFiscal` (CAPAG, SICONFI), maturidade de fontes, lacunas institucionais. Importante para o MCID: **risco alto + CAPAG fraca** muda a recomendação de financiamento/ação.

---

## 13. Backend — profundidade por domínio

### 13.1 Simulações (`api/simulations.py` + serviços)

Endpoints cobrem: chuva extrema (sync/async/job), impermeabilização, vegetação, drenagem, calor, mitigações (solar, telhado verde, infraverde, sombra), compare de cenários, method-note, exports (GeoJSON, KMZ, PDF, CSV impactos), validação IoU com manchas oficiais.

**Cache:** chave inclui município, parâmetros, versão do motor hidro — invalidação automática ao mudar `HYDRO_MODEL_VERSION`.

**Jobs:** Redis + `simulation_job_service` para não bloquear HTTP em grades grandes (LiDAR 1536).

### 13.2 Predições ML (`ml/` + `api/predictions.py`)

Pipeline: ETL features → treino HistGradientBoosting → artefatos em volume → preditor com política `model_kind`.

Features incluem proxies físicos (`physics_proxy`), precipitações, HAND/CN/drenagem/TWI. Explicabilidade e cards de modelo no frontend. Bootstrap e retreino via scripts/sistema.

### 13.3 Terreno e gémeo (`terrain`, `buildings`, DEM)

- DEM: download/processamento SRTM; preferência LiDAR local (Recife, PE3D Camutanga/Itamaracá)  
- Terrarium tiles para MapLibre  
- Edificações: OSM + Microsoft footprints → LOD1 extrusão; exposição à mancha; LOD2/mesh e 3D Tiles parciais (UI LOD2 pausada)  
- nDSM: quando MDS − MDT existe, alturas reais; senão heurística

### 13.4 Contigência e monitoramento

Planos COBRADE versionados (`ContingencyPlan` + revisions), rotas OSRM, alertas CEMADEN persistidos + WebSocket, arquivos de previsão/alerta, eventos de campo observados pela Defesa Civil (lastro para calibração).

### 13.5 Assistente e RAG

`RagDocument` + pgvector; ingestão de normativos; chat streaming; agente contextual lê estado da UI (município, aba, última simulação) para respostas acionáveis.

### 13.6 Governança

JWT + roles; OIDC opcional; `AuditLog`; export SEI com hash; policy gate em ações destrutivas/críticas (`confirm=true`); painel Sistema para saúde e pipelines.

---

## 14. Frontend — profundidade por módulo

### 14.1 Shell `PlatformApp`

Orquestra abas, município ativo, mapa central, HUD de camadas, painéis laterais, FAB do agente, toasts, modo focus. Estado em Zustand (`useAppStore`): município, camadas ativas, resultado de simulação, overlays (vias, ativos, timeline), modo 2D/3D, perfil UX.

### 14.2 Mapa

| Componente | Papel |
|------------|-------|
| `MapContainer` | Leaflet 2D, GeoJSON layers, estilos |
| `Map3DMapLibreContainer` | Terrain, extrusão manchas, edificações |
| `LayerPanel` / `MapHudControls` | Catálogo, qualidade, presets |
| `layerStyles` / `maplibreLayers` | Visual consistente 2D/3D |

Pós-simulação: modo 3D automático, overlays de vias/ativos, compare Antes↔Depois, inspeção por clique (profundidade, cota solo/água).

### 14.3 Simulação UI

`SimulationPanel` + `SimulationResults` + `PredictiveAnalysis`: parâmetros, progresso de job, limites honestos, exports, cards ML, interpretação IA.

### 14.4 Design system

Tokens em `design-system/` (cores institucionais teal, tipografia Source Sans 3, elevação, spacing). Componentes: `KpiCard`, `Badge`, `PanelSection`. Evita “dashboard genérico AI” — linguagem MCID.

### 14.5 Abas (navegação)

Painel · Municípios · Catálogo · Simulações · Monitor · Contingência · Assistente · Casos · Auditoria · Sistema — mais rota `/apresentacao/{ibge}`.

---

## 15. Fontes de dados — mapa completo

| Fonte | Conector / uso | Selo típico |
|-------|----------------|-------------|
| IBGE | população, PIB, malha, setores | Oficial |
| SICONFI / CAPAG | fiscal | Oficial |
| SNIS/SINISA | saneamento/drenagem | Oficial |
| MapBiomas | cobertura/uso do solo | Oficial |
| S2ID / SEDEC | desastres | Oficial |
| CEMADEN | alertas, pluvio | Oficial |
| INMET BDMEP / MERGE CPTEC | chuva | Observado |
| ANA HidroWeb | níveis fluviais | Observado |
| INEP | escolas | Oficial (ou OSM fallback) |
| CNES/DataSUS | saúde | Oficial |
| OSM / Microsoft buildings | vias, hidro, footprints | Referência |
| SoilGrids | solo → CN | Referência |
| GloFAS JRC | hazard RP100 | Referência |
| GeoReDUS LST | temperatura superfície | Observado |
| LiDAR / PE3D / SRTM | DEM | Oficial/Referência conforme origem |
| AdaptaBrasil / GeoSGB / SIRENE | proxies / lacunas | Variável |
| Pref. Recife / CTM | malha, equipamentos, UCN | Oficial local |

---

## 16. Fluxos ponta a ponta (para análise de processo)

### 16.1 Onboarding de município novo

1. Usuário seleciona IBGE → `ensureMunicipality`  
2. Geometria + seed + malha (Censo/CTM/Voronoi)  
3. Jobs de conectores (IBGE, MapBiomas, S2ID, …)  
4. Maturidade atualizada no catálogo  
5. Painel passa a mostrar IVC/IRI (mesmo que parciais)

### 16.2 Simulação de chuva → decisão

1. Parâmetros (mm, duração, nível mar, drenagem)  
2. API → hydro 2.10 (+ SoilGrids, OSM hidro)  
3. Cache hit ou job async  
4. Frontend: mancha 3D + vias + ativos + meta GloFAS  
5. Export CSV/KMZ/PDF → sala de crise  
6. Opcional: ativar contingência / registrar evento observado

### 16.3 Alerta vivo

1. Coletor/API CEMADEN → `AlertaCemaden` / `MonitoringAlert`  
2. WebSocket empurra UI Monitor  
3. Risco consolidado muda semáforo  
4. Gestor abre contingência / agente pergunta “o que fazer agora”

---

## 17. Segurança, multi-tenant e deploy

- **Dev:** auth pode estar relaxada; Compose LAN com CORS RFC1918  
- **Prod:** AUTH obrigatória, OIDC Keycloak/gov.br, TLS overlay, proxy headers  
- Escopo territorial por UF/IBGE no token  
- Volumes persistentes: DEM, models, reports, 3dtiles, backups  
- Profiles Compose: `ai` (Ollama), `oidc`, `tls`  
- Homologação: scripts smoke + checklist demo MCID

---

## 18. Comparativo com referências internacionais (leitura estratégica)

| Capacidade | Sinidu hoje | 3Di / HEC-RAS | PLATEAU JP | CEMADEN |
|------------|-------------|---------------|------------|---------|
| Rede de drenagem explícita | Proxy SNIS | Sim | N/A | N/A |
| Hidrodinâmica 2D | Não (triagem) | Sim | N/A | N/A |
| CityGML nacional | LOD1 local | N/A | Sim | N/A |
| Nowcast radar | Não | N/A | N/A | Sim |
| Vulnerabilidade social + fiscal | Sim (núcleo) | Raro | Parcial | Parcial |
| Contingência COBRADE + SEI | Sim | Não | Não | Parcial |
| Ciclo gestor único (ver→agir→auditar) | Sim | Não | Não | Não |

Conclusão: competir no **fechamento do ciclo institucional brasileiro**, não na física pura.

---

## 19. Perguntas-guia para análise densa (workshop)

1. Qual persona é P0 na próxima demo MCID — Defesa Civil, planejamento ou gabinete?  
2. Aceitamos manter teto “triagem” por 12 meses, ou há mandato para acoplar modelo 2D?  
3. Qual município escala depois de Recife/PE — capital com CTM ou interior com só dados abertos?  
4. Onde investir: lastro observacional (B) ou UX gémeo (C)?  
5. Auth/OIDC gov.br é bloqueante de produção agora?  
6. Quais camadas merecem selo “Oficial” obrigatório antes de discurso público?  
7. ML `full` deve aparecer na UI só após hit-rate mínimo publicado?

---

## 20. Conclusão para análise

O Sinidu+Clima é uma **plataforma de decisão climática municipal** com profundidade incomum num MVP governamental: do onboarding de dados abertos ao gémeo 3D, passando por motor pluvial versionado, ML condicionado, contingência e IA dual.  

A análise estratégica deve separar três planos:

1. **Produto utilizável hoje** — triagem, mapa, simulação, overlays operacionais, exports, contingência  
2. **Produto com lastro** — cresce com INEP/IDF/ANA/S2ID densos e MDS  
3. **Produto de paridade internacional** — exige hidrodinâmica/rede e programa de dados tipo PLATEAU — fora do escopo curto  

O diferencial competitivo sustentável não é “ser o melhor modelo físico do mundo”, e sim **fechar o ciclo gestor**: ver → simular → cruzar vulnerabilidade/capacidade → agir → auditar — com honestidade metodológica explícita.

---

*Documento gerado para análise completa do sistema. Atualizar ao fechar horizontes A–D do roadmap ou mudanças de versão do motor hidro / API.*
