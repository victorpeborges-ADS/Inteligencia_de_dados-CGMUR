# Roadmap — Gêmeo Digital Climático (modelo PLATEAU)

**Objetivo:** evoluir o 3D atual do Sinidu+Clima para um **gêmeo digital urbano** no espírito do
[PLATEAU](https://www.mlit.go.jp/plateau/) (MLIT, Japão) — cidade 3D semântica, dados oficiais
padronizados e casos de uso de prevenção de desastres/ambiente — mas com o **viés climático** que
já é o núcleo do Sinidu, cruzando os dados e sistemas que já temos.

**Status base (jul/2026):** Fases 1–16 concluídas. Este documento propõe a **Fase 17**, dividida em
7 ondas incrementais (17a → 17g) para implementação gradual:

- **17a–17e** — gêmeo digital: edificações 3D, exposição climática, dados abertos, mitigação e LOD2.
- **17f** — visão da cidade: experiência visual e navegação (estilo PLATEAU VIEW).
- **17g** — motor e **qualidade** das simulações: novos cenários, validação e confiança.
- **17h** — **gestão de risco no território**: empoderar o gestor a ver, identificar e agir.

**Progresso Fase 17 (jul/2026):** **69/70 (~99%)** — MVP fechado. **17e.1 LOD2** migra para a Fase 18
(exige mesh/telhado real; MapLibre `fill-extrusion` é LOD1).

---

## Fase 18 — Homologação, escala e LOD2 real

> Fechar a Fase 17 com qualidade de engenharia; depois ampliar escala nacional e LOD2 onde houver LiDAR.

### 18a — Homologação e higiene (P0)

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 18a.1 | **CI verde (testes)** | P0 | M | ✅ Asserts/stubs alinhados à Fase 17; skip graceful IBGE/rede e rasterio; soft-fail DEM sem rasterio; golden hydro 2.7. |
| 18a.2 | **`.gitignore` assets pesados** | P0 | S | ✅ Ignorar `video sinudu/`, `mapbiomas/`, `data/dem/`, cache e CSVs de auditoria. |
| 18a.3 | **`requirements.txt` limpo** | P0 | S | ✅ Removidas duplicatas PyJWT/httpx. |
| 18a.4 | **Deprecations datetime/Pydantic** | P1 | M | ✅ `app/timeutil.utc_now()` no lugar de `utcnow()`; `ConfigDict` em schemas/API (`MunicipioOut`, `CasoSucessoOut`, audit, action plan). |
| 18a.5 | **Pin de versões** | P1 | S | ✅ `requirements.txt` com `~=` por major/minor (weasyprint/pydyf exactos). |

### 18b — LOD2 e gêmeo avançado (P2)

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 18b.1 | **LOD2 (telhados) via mesh** | P2 | L | ⏸ Backend pronto (`building_lod2_mesh_service` + API); UI retirada por enquanto (MapLibre fill-extrusion ≠ telhado real). |
| 18b.2 | **Viewer 3D Tiles no mapa** | P2 | M | ⏸ Overlay UI retirado; reativar quando houver viewer estável (sem conflito com terrain). |

### 18c — Escala nacional (P1)

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 18c.1 | **Bootstrap em lote (UF)** | P1 | M | ✅ `uf_bootstrap_service` + `POST /onboarding/bootstrap-uf` + preview; job background; UI na aba Municípios. |
| 18c.2 | **Footprints OSM sob demanda** | P1 | M | ✅ Fila Overpass (`building_osm_queue_service`) com intervalo/backoff; `POST /buildings/queue`; job `buildings_osm_queue`; UI na aba Municípios. |

**Progresso Fase 18:** **7/9 (~78%)** — 18a+18c ✅; 18b UI pausada (backend LOD2 mantido).

---

## Fase 19 — Higiene, robustez de UX e dado real no piloto

> Evoluir **dentro das limitações conhecidas** (sem GPU dedicada, piloto de 6 municípios, dados nacionais escassos): reduzir dívida técnica, endurecer a UX contra falhas e substituir proxies por dado real onde é viável.

### 19a — Higiene técnica (P0)

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 19a.1 | **Remover mapas mortos** | P0 | S | ✅ Excluídos `Map3DContainer` (deck.gl) e `Map3DGoogleContainer` (Google) — zero imports. |
| 19a.2 | **Remover clients órfãos de edificações** | P0 | S | ✅ `getBuildings`, `enqueueBuildingsOsm(Uf)`, `getBuildingsOsmQueueStatus` retirados de `api.ts`. |
| 19a.3 | **Limpar ramo `edificacoes`/LOD1** | P0 | S | ✅ Removido `edificacaoFillColor2d`/`buildingMaterials.ts` e o ramo `edificacoes` em `layerStyles.ts`. |
| 19a.4 | **Dívida de tipos `scenario_type`** | P1 | S | ✅ Union de `SimulationOutput` estendida (solar/telhado verde/infraverde/comparador/sombra) — `tsc --noEmit` limpo. |

### 19b — Robustez de UX (P0)

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 19b.1 | **ErrorBoundary global** | P0 | S | ✅ `components/UI/ErrorBoundary.tsx` envolvendo o app em `layout.tsx` (evita tela branca). |
| 19b.2 | **Erro visível no Monitor** | P0 | S | ✅ Falha de carga mostra banner + retry e **não degrada para VERDE** silenciosamente. |
| 19b.3 | **Erro visível no mapa 2D** | P0 | S | ✅ Camadas que falham geram aviso dispensável (não somem sem explicação). |
| 19b.4 | **Trocar `alert()` nativo** | P1 | S | ✅ `SimulationPanel` usa banner de UI (ok/erro) ao gerar contingência. |

### 19c — Dado real no piloto (P1)

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 19c.1 | **S2ID curado (6 municípios)** | P1 | M | ✅ Eventos ancorados em Defesa Civil/imprensa para Aracaju, Salvador, Rio, São Paulo e Brasília (antes só Recife). Aplicado via `ensure_s2id_loaded` no sync/onboarding. |
| 19c.2 | **MapBiomas oficial (6 municípios)** | P1 | M | ⏳ Pipeline já lê CSV oficial (`MAPBIOMAS_STATS_DIR`); pendente **obter e depositar** a estatística Coleção 10.1 por município (não fabricar hectares). |

### 19e — Entregas extras (jul/2026)

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 19e.1 | **Export KMZ das simulações** | P1 | M | ✅ `POST /simulations/export/kmz` + botão no `SimulationPanel` (mancha/curvas/escoamento → Google Earth/QGIS). |
| 19e.2 | **Launchers Windows/Mac** | P1 | M | ✅ `Abrir` / `Atualizar` / `Avaliar` (.bat CRLF + `.command`); finder `SINIDU_DIR.txt`; fix do atalho Mac (`echo"`). |

### 19d — Migrado para Fase 20

Itens que estavam em 19d foram priorizados na **Fase 20** (abaixo).

**Progresso Fase 19:** **11/12 (~92%)** — 19a+19b+19e ✅; 19c.1 ✅; 19c.2 aguarda CSV oficial MapBiomas.

---

## Fase 20 — Confiança, produto IA e operação multi-máquina

> Fechar o que ainda limita demo externa e escala operacional: confiança (auth/testes), produto de IA de domínio (não swarm genérico), dados oficiais no piloto e operação Mac↔Windows↔Dev Tunnel.

### 20a — Confiança e homologação (P0)

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20a.1 | **Testes HTTP** dos routers críticos (`simulations`, `monitoring`, `integrations`, export KMZ) | P0 | M | ⏳ |
| 20a.2 | **Endurecer auth/secrets** (JWT/senhas default, CORS, superfície em Dev Tunnel) | P0 | M | ⏳ |
| 20a.3 | **Policy gate em ações sensíveis** (agente/UI não ativa plano, SMS ou alerta público sem confirmação humana) | P0 | S | ⏳ |
| 20a.4 | **Documento único `ESTADO_ATUAL_SINIDU.md`** (tecnologias, features, falhas, ✅/⏳) | P1 | S | ⏳ |

### 20b — Agentes de domínio (P0/P1)

> Evoluir o que já existe (`contextual_agent_*` + assistente RAG). **Não** substituir por swarm genérico.

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20b.1 | **Unificar `AssistantPanel` × `AgenteSinidu`** (um produto, dois modos ou um só) | P0 | M | ⏳ |
| 20b.2 | **Contrato rígido de tools** (schema, testes, proibição de inventar nível de alerta / VERDE silencioso) | P0 | M | ⏳ |
| 20b.3 | **Tools de domínio em falta** (export KMZ/PDF via agente; lacunas do catálogo; “explique esta mancha”) | P1 | M | ⏳ |
| 20b.4 | **Telemetria de IA** (latência, fallback determinístico, tokens, taxa de tool-error) | P1 | S | ⏳ |

### 20c — MCP (adapter, não runtime do produto) (P1)

> MCP como ponte para a **equipe** (Cursor/Claude Desktop), espelhando a API. Não é o runtime do painel web.

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20c.1 | **Servidor MCP fino** (5–10 tools read-only: overview, layers/meta, diagnostic, monitoring, simulation status, catalog gaps) | P1 | M | ⏳ |
| 20c.2 | **Auth no MCP** (token/JWT tenant-aware; rate-limit; sem write por padrão) | P0 | M | ⏳ (junto com 20c.1) |
| 20c.3 | **Documentar uso MCP** para equipe (Cursor config + limites) | P2 | S | ⏳ |

### 20d — Ruflo / multiagente de coding (P3 — experimento opcional)

> **Fora do produto Sinidu entregue ao MCID.** Só tooling da equipe, com prazo e métrica.

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20d.1 | **Spike Ruflo 2 semanas** (fora do `docker-compose` do produto; métrica: tempo de PR / cobertura de testes gerada) | P3 | M | ⏳ opcional |
| 20d.2 | **Go/No-go**: manter só se houver ganho medido; senão descartar (não embutir no compose) | P3 | S | ⏳ |

### 20e — Dados e simulação (P1)

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20e.1 | **MapBiomas Coleção 10.1** nos 6 municípios (CSV oficial em `MAPBIOMAS_STATS_DIR`) | P1 | M | ⏳ (herdado 19c.2) |
| 20e.2 | **KMZ pacote completo** (mancha + bairros afetados + pontos de contingência, se houver) | P2 | M | ⏳ |
| 20e.3 | **Unificar narrativa de previsão** (OpenMeteo + CEMADEN + fallback — um selo só na UI) | P1 | M | ⏳ |

### 20h — Honestidade e acurácia metodológica das simulações (P0)

> As simulações usam **dados oficiais de entrada** e pedaços de GIS/literatura clássicos, mas **não** são metodologias oficiais ANA/CEMADEN/CPRM/INMET-IDF nem hidrodinâmica 2D. O produto deve deixar isso inequívoco na UI e elevar o que for viável (IDF oficial, validação espacial).

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20h.1 | **Copy e UI alinhados ao `method_note`** — nunca apresentar simulação como “metodologia oficial”; selo Derivado/Estimado visível no painel e no mapa | P0 | S | ⏳ |
| 20h.2 | **Painel de limites metodológicos** na aba Simulações (o que é / o que não é: não-laudo, não-HEC-RAS, não-alerta CEMADEN) | P0 | S | ⏳ |
| 20h.3 | **Separar na UI** “cenário Sinidu (Derivado)” vs “LST/observado GeoReDUS (Oficial)” no comparador de calor | P0 | S | ⏳ |
| 20h.4 | **IDF oficial onde existir** (ANA/INMET/PDF municipal) substituindo tabelas internas `Estimado` | P1 | M | ⏳ |
| 20h.5 | **Camada de validação** com manchas/estudos oficiais (Defesa Civil/CPRM) quando houver — além do hit-rate pontual S2ID | P1 | M | ⏳ |
| 20h.6 | **Checklist de linguagem** (demo MCID / apresentação / agente): proibir “oficial”, “homologado”, “preciso como engenharia” sem qualificador | P0 | S | ⏳ |
| 20h.7 | Documentar teto de acurácia em `DOCUMENTACAO_TECNICA` + `ESTADO_ATUAL` (triagem ≠ laudo) | P1 | S | ⏳ |

**Fora do horizonte imediato (não fingir que cabe no MVP):** hidrodinâmica 2D / SWMM / inventário completo de galerias — só com projeto dedicado e dado de rede.

### 20f — UX / manutenção (P2)

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20f.1 | Layout **mobile/responsivo** + acessibilidade (tablist/foco) | P2 | L | ⏳ |
| 20f.2 | Quebrar `SimulationPanel` / `MapContainer` (hotspots) | P2 | L | ⏳ |
| 20f.3 | Playbook **Mac ↔ Windows ↔ Dev Tunnel** (git pull, rebuild, checagem API pública) | P1 | S | ⏳ |
| 20f.4 | **Estética sóbria e profissional** (tokens, tipografia, densidades, chrome do shell — sem mudar fluxos) | P1 | M | ⏳ |

#### Checkpoint de aparência (rollback exato)

Antes de qualquer mudança visual da **20f.4**, o estado atual da UI fica congelado em:

| Artefato Git | Nome | Commit base |
|--------------|------|-------------|
| **Tag anotada** | `ui-checkpoint-pre-estetica-sobria` | `3e793f2` |
| **Branch** | `checkpoint/ui-antes-estetica-sobria` | mesmo commit |

**Restaurar a aparência anterior (exatamente igual):**

```bash
# Opção A — só frontend (recomendado se o resto do branch avançou)
git checkout ui-checkpoint-pre-estetica-sobria -- frontend/

# Opção B — voltar o working tree do frontend via branch de checkpoint
git checkout checkpoint/ui-antes-estetica-sobria -- frontend/
```

Depois: rebuild do frontend (`docker compose ... up -d --build frontend` ou equivalente).

**Não apagar** a tag/branch de checkpoint até a estética nova estar homologada.

### 20g — Pausado / fora do horizonte imediato

| Item | Motivo |
|------|--------|
| LOD1/LOD2 UI de edificações | Qualidade insuficiente; backend mantido |
| Escala nacional real (S2ID/MapBiomas API) | Dependência de dado/API oficial |
| gov.br produção (OIDC) | Fora de escopo do protótipo (decisão jul/2026) |
| Ruflo embutido no produto | Desencaixe de domínio; risco/ops altos |
| Hidrodinâmica 2D / SWMM / galerias completas | Exige dado de rede + projeto dedicado; fora do MVP de triagem |

**Progresso Fase 20:** **0/~26 itens ativos** — planejada (jul/2026). Ordem sugerida: **20h (honestidade metodológica)** + **20f.4 (com checkpoint)** em paralelo a **20a → 20b → 20e → 20c → 20f**; 20d só se houver dono e 2 semanas de experimento.

---

## 0. Visão e princípios norteadores

> **O gêmeo digital é o horizonte — não o pré-requisito.** Cada onda deve entregar valor para o
> **município médio brasileiro de hoje** (dados escassos, sem equipe de GIS, sem CTM, orçamento e
> conectividade limitados), e ao mesmo tempo preparar o terreno para o gêmeo digital completo.

**Missão:** empoderar o **gestor municipal** (Defesa Civil, Planejamento, Obras, Meio Ambiente) a
fazer **gestão de risco no território** — enxergar, identificar e agir sobre as vulnerabilidades,
cruzando **todos os dados disponíveis**, com respostas **adequadas à realidade do município**.

**Ciclo central — o produto gira em torno disto:**

```
VER  →  IDENTIFICAR  →  AGIR  →  (acompanhar e reavaliar)
```

**Princípios de projeto (valem para todas as ondas):**

1. **Valor no primeiro dia (bootstrap nacional).** Mesmo sem nenhum dado local, IBGE + S2ID +
   MapBiomas + CEMADEN + SRTM já produzem diagnóstico e simulação. O município não precisa "estar
   pronto" para começar a usar.
2. **Degradação graciosa + honestidade.** Quando falta o dado oficial, usa-se estimativa — sempre
   com o **selo de origem** (Oficial/Observado/Estimado/Derivado). A plataforma nunca trava por
   ausência de dado, e nunca esconde a incerteza.
3. **Resposta adequada à realidade.** Recomendações calibradas por **porte do município, CAPAG
   (capacidade fiscal) e capacidade institucional** — medidas de baixo custo para municípios
   pequenos; obras estruturais e financiamento (Pro-Cidades, PAC, FGTS) para os que comportam.
4. **Ciclo fechado e rastreável.** Do diagnóstico à ação, com auditoria e export SEI — o gestor
   presta contas do que viu, priorizou e executou.
5. **Gêmeo digital incremental.** Cada camada 3D/edifício só entra quando **melhora uma decisão de
   risco** — nunca "3D pelo 3D". A sofisticação segue a utilidade para o gestor.

---

## 1. O que o PLATEAU tem — e onde estamos

| Pilar PLATEAU | PLATEAU (referência) | Sinidu+Clima hoje | Lacuna |
|---|---|---|---|
| **Terreno 3D (DEM)** | DEM nacional | ✅ Terrarium tiles + hillshade + DEM SRTM/LiDAR (`dem_processor.py`) | Menor |
| **Edificações 3D semânticas** | CityGML LOD1/LOD2 com atributos (uso, pavimentos, ano) | ❌ Não existe — só extrusão de polígonos temáticos e colunas de simulação | **Maior lacuna** |
| **Visualizador web** | PLATEAU VIEW (CesiumJS/Terria) | ✅ MapLibre GL 3D (`Map3DMapLibreContainer.tsx`) com pitch, exagero, basemaps | Menor |
| **Simulação de desastre** | Inundação/tsunami/deslizamento | ✅ Chuva→inundação, calor, deslizamento por declividade (`hydro_simulator.py`) | Falta ligar ao **edifício** |
| **Ambiente** | Ilha de calor, solar, vento | 🔶 LST observada + simulação de calor | Falta cenário por edifício/telhado |
| **Dados abertos padronizados** | CityGML, 3D Tiles, GeoJSON | 🔶 GeoJSON temático, mesh.json, DEM | Falta formato 3D interoperável |
| **Atributos ricos** | Por edifício (pop., uso, estrutura) | 🔶 Por bairro/setor censitário | Falta granularidade por edifício |

**Conclusão:** a base de terreno e o visualizador já existem. O salto rumo ao PLATEAU é
**edificações 3D com atributos + exposição climática por edifício + formato interoperável**.

**Trunfos que aceleram o caminho:**
- A primitiva `fill-extrusion` já está no mapa (`maplibreLayers.ts`) → renderizar prédios é
  majoritariamente um problema de **dados**, não de motor gráfico.
- **LiDAR do Recife** (`data/dem/local/2611606_lidar.tif`) → altura real de edifícios via
  **nDSM (DSM − DTM)**, sem depender do CTM (bloqueado institucionalmente).
- `hydro_simulator.py` já gera superfície de inundação, D8, contornos e deslizamento →
  exposição por edifício é um **cruzamento**, não um motor novo.

---

## Legenda

| Prioridade | | Esforço | |
|---|---|---|---|
| P0 | Fundacional | S | ≤ 1 semana |
| P1 | Alto valor | M | 2–4 semanas |
| P2 | Incremental | L | > 1 mês |

---

## Onda 17a — Edificações 3D base (LOD1)  · fundacional

> Sem prédios não há gêmeo digital. Esta onda entrega a camada `edificacoes` extrudada.

| # | Item | Prioridade | Esforço | Como / fontes oficiais e abertas |
|---|------|-----------|---------|----------------------------------|
| 17a.1 | **Ingestão de footprints** | P0 | M | ✅ `building_footprints_collector.py` — OSM Overpass `building=*`, cache PostGIS; seed Recife se Overpass falhar. |
| 17a.2 | **Estimativa de altura (LOD1)** | P0 | M | ✅ Ordem: OSM `height` → `building:levels` → heurística por uso; `altura_m` + `fonte_altura` + selo Observado/Estimado/Derivado. |
| 17a.3 | **Modelo de dados `Edificacao`** | P0 | S | ✅ Tabela `edificacoes` (PostGIS MULTIPOLYGON, altura, uso, pavimentos, fontes, `codigo_ibge`). |
| 17a.4 | **API `/api/v1/buildings/{ibge}`** | P0 | S | ✅ GeoJSON com `_extrusionHeightM` + sync admin; também camada `edificacoes` em `/indicators/layers`. |
| 17a.5 | **Camada `edificacoes` no 3D** | P0 | S | ⏸ UI retirada — prismas OSM/fill-extrusion sem qualidade nem usabilidade; backend/API mantidos. |
| 17a.6 | **nDSM para Recife (piloto)** | P1 | M | ✅ `ndsm_service.py` — DSM LiDAR − min-filter DTM → nDSM; refine LOD1 + `POST /buildings/{ibge}/refine-ndsm`. |

**Entregável:** backend/API de footprints + altura prontos; **camada 3D na UI pausada** até haver qualidade/usabilidade aceitáveis (não publicar prismas OSM fracos).

---

## Onda 17b — Exposição climática por edifício  · o diferencial PLATEAU+Clima

> Aqui o gêmeo digital ganha o viés climático: não "a área alaga", mas **"estes prédios alagam,
> nesta profundidade, com esta população exposta"**.

| # | Item | Prioridade | Esforço | Como / cruzamento |
|---|------|-----------|---------|-------------------|
| 17b.1 | **Inundação × edifício** | P0 | M | ✅ `building_exposure_service` — cruza `flood_bands` com footprints LOD1 → faixa/profundidade por prédio + GeoJSON `buildings_exposed`. |
| 17b.2 | **População exposta por edifício** | P1 | M | ✅ Distribui pop. do setor (área×pavimentos) → `populacao_estimada` / `populacao_edificios_estimada` no painel. |
| 17b.3 | **Calor × edifício** | P1 | M | ✅ `compute_heat_building_exposure` — footprint × `heat_band` (ΔT/bairro) → ranking térmico + card no painel. |
| 17b.4 | **Deslizamento × edifício** | P1 | S | ✅ `compute_landslide_building_exposure` — footprint × zonas `dem_slope` → faixas por declividade + card na chuva extrema. |
| 17b.5 | **Painel "Exposição do cenário"** | P0 | M | ✅ `exposicao_cenario` no `simulation_meta` (edifícios, pop, escolas INEP, CNES por faixa) + card no painel de simulação. |
| 17b.6 | **Ferramenta de IA `get_exposicao_edificios`** | P2 | S | ✅ 14ª ferramenta do agente — inundação/deslizamento/calor com contagens + amostra. |

**Entregável:** para qualquer simulação, contagem de edifícios e população expostos, com camada
visual e resposta do assistente.

---

## Onda 17c — Padronização e dados abertos (interoperabilidade PLATEAU)

> PLATEAU é, acima de tudo, **dado aberto padronizado**. Esta onda torna o modelo reutilizável.

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 17c.1 | **Export 3D Tiles** | P1 | M | ✅ `building_3dtiles_service` — GLB LOD1 + `tileset.json`; `POST/GET .../3dtiles/build|status|tileset.json` + `/static/3dtiles`. |
| 17c.2 | **Export CityGML/CityJSON (LOD1)** | P2 | M | ✅ `building_cityjson_service` — CityJSON 2.0 + CityGML 2.0 Building LOD1; `POST/GET .../cityjson|citygml`. |
| 17c.3 | **Catálogo do modelo 3D** | P1 | S | ✅ `gemeo_digital_3d` no `data_catalog` — status por footprints/altura/export; metadados `modelo_3d` (fonte altura, maturidade, URLs 3D Tiles/CityJSON). |
| 17c.4 | **API de tiles do gêmeo** | P2 | M | ✅ `building_tiles_api_service` — MVT PostGIS + GeoJSON/tileset/GLB via API com cache Redis (`X-Sinidu-Cache`). |
| 17c.5 | **Governança/qualidade 3D** | P1 | S | ✅ `building_quality_service` — selos LiDAR/OSM/Estimado; `GET .../quality` + normalize; GeoJSON/CityJSON/mapa coloridos por selo. |

**Entregável:** modelo 3D exportável e catalogado, servível com performance.

---

## Onda 17d — Cenários de mitigação (dimensão ambiente)

> PLATEAU usa o modelo para simular intervenções. Com viés climático: **mitigação urbana**.

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 17d.1 | **Potencial solar em telhados** | P2 | M | ✅ `solar_rooftop_service` — área footprint × HSP → kWp/MWh; `POST /simulations/solar-rooftop` + aba Mitigar. |
| 17d.2 | **Telhado verde / permeabilidade** | P2 | M | ✅ `green_roof_mitigation_service` — X% telhados verdes → offset de impermeabilização + delta de mancha; `POST /simulations/green-roof`. |
| 17d.3 | **Sombra / insolação** | P2 | L | ✅ MVP `shadow_insolation_service` — posição solar + sombra por vizinhos; `POST /simulations/shadow-insolation` + aba Mitigar. |
| 17d.4 | **Infraestrutura verde × calor** | P2 | M | ✅ `green_infra_heat_service` — arborização vs UHI (baseline×mitigado); `POST /simulations/green-infra-heat`. |
| 17d.5 | **Comparador de intervenções** | P2 | M | ✅ `intervention_comparator_service` — antes/depois unificado (solar / telhado verde / infraverde); `POST /simulations/interventions/compare`. |

**Entregável:** simulações "what-if" de mitigação climática sobre o modelo 3D.

---

## Onda 17e — LOD2, temporal e gêmeo operacional

> Refinamento visual (aproximação estética do PLATEAU VIEW) e operação em tempo real.

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 17e.1 | **LOD2 (telhados)** | P2 | L | ⏸ Adiado — `fill-extrusion` MapLibre é LOD1 (prismas); telhado inclinado exige mesh/LOD2 real (LiDAR Recife). Fora do MVP atual. |
| 17e.2 | **Evolução urbana temporal** | P2 | M | ✅ `get_urban_series` com `% área municipal` + callout de evolução no `ExecutiveDashboard` (MapBiomas km² e p.p. no tempo). |
| 17e.3 | **Sensores em tempo real no gêmeo** | P1 | M | ✅ `live_sensors_3d_service` + `GET /monitoring/live-sensors/{ibge}` — CEMADEN/monitoramento/INMET/previsão como pontos; overlay pulsante no MapLibre 3D + refresh via WebSocket. |
| 17e.4 | **Texturas / materialização** | P2 | L | ✅ `buildingMaterials.ts` — cores por `uso_grupo`/selo; toggle Uso\|Qualidade no 3D; `fill-extrusion-vertical-gradient`; MVT com `uso_grupo`; legenda HUD + 2D Leaflet. |
| 17e.5 | **Modo apresentação / tour** | P2 | S | ✅ Botão "Tour apresentação" no 3D — sequência de câmera (visão geral → orbitação → sensor vivo) para demo MCID. |

**Entregável:** gêmeo digital com visual refinado, dimensão temporal e integração de sensores.

---

## Onda 17f — Visão da cidade (experiência visual e navegação)

> Aproximar a experiência do **PLATEAU VIEW**: uma cidade legível, imersiva e navegável.
> Base atual: `Map3DMapLibreContainer.tsx` (terreno + satélite/escuro/claro, pitch, exagero, céu,
> extrusão temática, inspeção por clique).

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 17f.1 | **Iluminação solar por hora do dia** | P1 | M | ✅ `solarPosition.ts` + slider de hora no 3D — controla `sky-atmosphere-sun`, `map.setLight` (extrusões) e hillshade/brilho do basemap. |
| 17f.2 | **Modo dia/noite e condição climática** | P2 | S | ✅ Presets Dia / Entardecer / Noite / Chuva no painel 3D (cor, intensidade e brilho). |
| 17f.3 | **POIs de equipamentos críticos em 3D** | P1 | M | ✅ `critical_pois_3d_service` + `GET /monitoring/critical-pois/{ibge}` — INEP/CNES/abrigos com rótulos no MapLibre 3D (toggle + legenda). |
| 17f.4 | **Navegação assistida** | P1 | M | ✅ `Map3DNavAssist` — voar até bairro, presets de cena, bookmarks de câmera (localStorage), minimapa com posição/bússola (HUD já tem norte). |
| 17f.5 | **Corte/seção transversal do terreno** | P2 | M | ✅ `terrain_profile_service` + `POST /terrain/{ibge}/profile` — clique A→B no 3D gera perfil DEM com gráfico cota × distância. |
| 17f.6 | **Camadas de contexto urbano** | P1 | M | ✅ `urban_context_3d_service` + `GET /monitoring/urban-context/{ibge}` — hidrografia (MapBiomas/rios), vias e curvas DEM; toggles + opacidade no 3D. |
| 17f.7 | **Comparador swipe 2D/3D e antes/depois** | P1 | M | ✅ `MapSwipeCompare` + botão Swipe no mapa — cortina 2D×3D ou Antes×Depois (simulação), com alça arrastável. |
| 17f.8 | **Legenda, escala e norte dinâmicos** | P0 | S | ✅ `MapHudControls` no 3D — bússola (bearing), escala métrica, legenda contextual das camadas ativas + `ScaleControl` MapLibre. |
| 17f.9 | **Exportar cena (imagem/vídeo)** | P1 | M | ✅ Export PNG/WebM do canvas MapLibre 3D (`exportMapScene.ts`, `preserveDrawingBuffer`) — botões no painel 3D; mapa estático backend já existia. |
| 17f.10 | **Performance em cidades grandes** | P1 | L | ✅ MVP: edificações via MVT no 3D (`syncEdificacoesMvt`, minzoom 13); cluster POIs/sensores; GeoJSON edificações com `limit=1500` no 2D. |

**Entregável:** cidade 3D mais realista, legível e navegável, com equipamentos críticos e exportação.

---

## Onda 17g — Motor e qualidade das simulações

> O simulador de inundação atual (`hydro_simulator.py`) é **paramétrico** (coeficiente de escoamento
> por impermeabilização + superfície d'água modulada por acúmulo D8, TWI, declividade, IRI e reforço
> fluvial). O de calor é um **proxy UHI por bairro**. São bons para triagem, mas há espaço claro para
> ganho de **realismo físico, dimensão temporal e validação**.

### 17g.1 — Incrementos de capacidade (novos cenários)

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 17g.1a | **Chuva por período de retorno (IDF)** | P1 | M | ✅ `idf_rainfall_service` + `GET /simulations/idf/{ibge}` + `periodo_retorno_anos` na API; chips TR2/10/25/100 no painel pluvial. |
| 17g.1b | **Inundação temporal (hidrograma)** | P1 | L | ✅ `build_flood_timeline` — hidrograma triangular (5 passos / 6 h) sobre depth de pico; slider + animar no painel pluvial. |
| 17g.1c | **Nível do mar e maré (cidades costeiras)** | P1 | M | ✅ `sea_level_service` + offset na cota base (`nivel_mar_m` / cenários IPCC); UI no painel pluvial (Recife/Aracaju). |
| 17g.1d | **Capacidade de drenagem** | P2 | L | ✅ `drainage_capacity_service` + sumidouro no `flood_bands` (mm removidos / saturação); params `aplicar_drenagem` / `drainage_capacity_mm_h`; meta `drenagem_urbana`; motor **v2.7**; UI em opções avançadas. |
| 17g.1e | **Deslizamento com gatilho de chuva** | P1 | M | ✅ `slope_rainfall_trigger` — risk score + FS proxy com chuva efetiva (evento + 50% antecedente); slider no painel. |
| 17g.1f | **Calor: sombreamento e ventilação** | P2 | L | ✅ UHI v1.2 — `shade_factor` / `ventilacao_factor` atenuam ΔT; proxy altura de edificações + espaço aberto; sliders sombreamento/corredores na aba Calor; meta `sombreamento_pct` / `corredores_vento_pct`. |
| 17g.1g | **Novos módulos climáticos** | P2 | L | ✅ `climate_modules_service` — seca (déficit precip × cobertura) e proxy arbovírus (T Aedes × água parada × habitat); `POST /simulations/climate-modules`; aba Seca/Arb; OpenMeteo com `temperature_2m`. |

### 17g.2 — Qualidade, validação e confiança

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 17g.2a | **Backtesting contra S2ID** | P0 | M | ✅ `validacao_s2id` na simulação pluvial — hit rate de pontos S2ID na mancha + Jaccard de bairros; limitação explícita (S2ID é ponto, não polígono). |
| 17g.2b | **Calibração de coeficientes** | P1 | M | ✅ `hydro_calibration_service` — escalas por IBGE (proxy UF/bioma + auto S2ID); `GET/POST /simulations/hydro-calibration/{ibge}`; badge + Recalibrar no painel. |
| 17g.2c | **Bandas de incerteza / cenários** | P1 | M | ✅ `uncertainty_bands` (±15% precip) no `simulation_meta` + card otimista/esperada/pessimista no painel pluvial. |
| 17g.2d | **DEM hidro-corrigido** | P1 | M | ✅ `_fill_sinks` (Priority-Flood) pré-D8; meta `dem_hydro_conditioned` / `dem_fill_sinks`; motor v2.6. MERIT-Hydro fica fase 2. |
| 17g.2e | **Selo de confiança por simulação** | P0 | S | ✅ `selo_confianca` no `simulation_meta` (Observado/Estimado/Derivado + nível alta/média/baixa); usa `vertical_accuracy_m` do DEM; UI no painel de simulação. |
| 17g.2f | **Testes de regressão numérica** | P1 | S | ✅ `test_hydro_regression.py` + golden DEM sintético (`fixtures/hydro_bowl_120_golden.json`); monotonia 60→180 mm; `UPDATE_GOLDEN=1`. |
| 17g.2g | **Nota metodológica publicável** | P1 | S | ✅ `method_note_service` + `POST /simulations/method-note` + botão “Baixar nota” no painel (anexa em `simulation_meta.nota_metodologica`). |
| 17g.2h | **Validação cruzada com AdaptaBrasil** | P2 | M | ✅ `adapta_brasil_validation_service` + bloco no risk-panel; proxy MapBiomas corrigido (`classe_uso`/`area_ha`); chip no `RiskTrafficLightPanel`. |

**Entregável:** simulações mais realistas (IDF, temporal, costeiro), com acurácia medida contra
dados oficiais, incerteza explícita e selo de confiança — defensável em auditoria técnica.

---

## Onda 17h — Gestão de risco no território: empoderar o gestor

> A onda que amarra tudo à **missão**: transformar dados e simulações em **decisão e ação** do gestor,
> no ritmo e na realidade do município. Reaproveita diagnóstico, simulações, contingência, plano de
> ação, agente IA e auditoria que já existem — organizando-os no ciclo **ver → identificar → agir**.

### 17h.1 — VER: enxergar o território e o risco

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 17h.1a | **Painel de risco único (semáforo)** | P0 | M | ✅ `GET /api/v1/analytics/risk-panel` + `RiskTrafficLightPanel` no painel executivo — Score/IVC/IRI/VM/alerta → VERDE–VERMELHO + top bairros. |
| 17h.1b | **Modo "baixa maturidade"** | P0 | M | ✅ Flag `modo_baixa_maturidade` no mesmo endpoint (Bronze / cobertura Baixa / onboarding aberto) + banner de bootstrap nacional no painel. |
| 17h.1c | **Mapa de risco consolidado** | P1 | S | ✅ Camada `risco_consolidado` (Score Sinidu × alerta vivo) + estilo semáforo 2D/3D; atalho "Ver no mapa" no painel de risco. |
| 17h.1d | **Visão por perfil de usuário** | P2 | M | ✅ Switcher no header (`uxProfiles.ts`) — reordena abas + densifica o painel por perfil; **não esconde** Monitor/Contingência. |

### 17h.2 — IDENTIFICAR: achar e priorizar vulnerabilidades

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 17h.2a | **Ranking de áreas críticas explicado** | P0 | M | ✅ `fatores` + `fatores_principais` no ranking/`risk-panel` (renda, densidade, S2ID, impermeabilização, hidrografia, adaptação). |
| 17h.2b | **Exposição de população e serviços** | P0 | M | ✅ `exposicao` por bairro + `exposicao_resumo` (população, escolas INEP, CNES, territórios especiais) no painel. |
| 17h.2c | **Cruzamento guiado pelo assistente** | P1 | M | ✅ `recommend_layer_crosswalk` + tool `recommend_cruzamento_camadas`; `recommended_layers` no chat e aplicação no mapa. |
| 17h.2d | **Hotspots recorrentes** | P1 | M | ✅ `recurring_hotspots_service` no `risk-panel` (`hotspots_recorrentes`) — S2ID≥2 ∩ (IRI≥0.45 ou mancha 120 mm em cache); card no painel. |
| 17h.2e | **Comparar e ranquear municípios** | P2 | S | ✅ `GET /analytics/rank` + aba Ranking no `CompareModal` (score/IVC/IRI/adaptação/CAPAG/população por UF). |

### 17h.3 — AGIR: resposta adequada à realidade do município

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 17h.3a | **Catálogo de medidas por porte e custo** | P0 | M | ✅ `measures_catalog.py` + `medidas_recomendadas` no `risk-panel` e no plano de ação — filtra por porte/CAPAG/fatores/nível de risco. |
| 17h.3b | **Medida → fonte de recurso** | P1 | M | ✅ `fontes_financiamento` por medida (Pro-Cidades/FGTS, PAC, SEDEC, emendas, LOA); CAPAG C/D bloqueia crédito União; UI no painel. |
| 17h.3c | **Contingência operacional reforçada** | P1 | M | ✅ `recursos_operacionais` + `protocolo_campo` + código COBRADE; wizard etapa 4; PDF seções 6–7; migration `023`. |
| 17h.3d | **Alerta à população / Defesa Civil** | P2 | M | ✅ `public_alert_service` + `POST/GET /monitoring/disseminate/*` — checklist DC, WhatsApp deep-link, Gotify, webhook; SMS stub; modal no Monitor; auditoria `alert.disseminate`. |
| 17h.3e | **Acompanhamento da ação** | P1 | M | ✅ `action_tracking_service` — PATCH status por ação + POST reavaliar (delta Score/semáforo); UI no `ActionPlanPanel`. |

### 17h.4 — Adequação à realidade municipal (transversal a esta onda)

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 17h.4a | **Perfil do município** | P0 | S | ✅ `municipal_profile_service.py` — porte (POP_FAIXAS), CAPAG, Plano Diretor e proxy Defesa Civil (SICONFI); exposto no painel e no plano de ação. |
| 17h.4b | **Onboarding leve (sem GIS)** | P1 | M | ✅ Busca por nome + **Ativar município** (`ensure`); GIS colapsado; CTA no banner de onboarding. |
| 17h.4c | **Relatórios de campo (offline/PDF)** | P1 | S | ✅ `GET /analytics/risk-panel/field-report.pdf` + botão “Ficha campo” no painel de risco (status, hotspots, medidas). |
| 17h.4d | **Capacitação embutida** | P2 | S | ✅ Glossário expandido (IDF/TR/UHI/selos/CEMADEN…) + dicas de aba em português de gestor; tooltips no risco/simulação/contingência. |

**Entregável:** o gestor de um município comum consegue, no mesmo dia, **ver** onde está o risco,
**identificar** quem está exposto e **agir** com uma medida realista ligada a uma fonte de recurso —
tudo rastreável e honesto quanto à origem do dado.

---

## Melhorias transversais (independentes do 3D, mas recomendadas)

Itens de higiene — agora rastreados na **Fase 18a**:

- ✅ **`.gitignore`**: `video sinudu/`, `mapbiomas/`, `data/dem/`, cache.
- ✅ **Testes**: asserts alinhados + skip graceful rede/rasterio.
- ✅ **`requirements.txt`**: duplicatas removidas.
- ✅ **Deprecations**: `datetime.utcnow()` → `app.timeutil.utc_now()`; Pydantic `Config` → `ConfigDict` (18a.4).
- ✅ **Qualidade de dado 3D**: selo de procedência por edifício (LiDAR/OSM/estimado).

---

## Ordem sugerida de implementação (mínimo caminho de valor)

Prioridade: primeiro o que **empodera o gestor em qualquer município hoje**; depois o **gêmeo digital**
para as cidades que já têm dados de base.

**Trilha A — Gestão de risco para todos os municípios (começar por aqui):**

1. **17h.1b + 17h.1a** (modo baixa maturidade + painel de risco único) — valor no primeiro dia.
2. **17h.2a + 17h.2b** (ranking de áreas críticas + exposição de população e serviços) — identificar.
3. **17h.3a + 17h.4a** (catálogo de medidas por porte/CAPAG + perfil do município) — agir com realismo.
4. **17g.2a + 17g.2e** (validação contra S2ID + selo de confiança) — credibilidade das simulações.

**Trilha B — Gêmeo digital (para cidades com dado de base, em paralelo/depois):**

5. **17a.1 → 17a.5** (footprints + altura + camada 3D) — desbloqueia o 3D semântico.
6. **17b.1 + 17b.5** (inundação × edifício + painel de exposição) — o "wow" climático por edifício.
7. **17a.6 + 17b.2** (nDSM Recife + população exposta) — ✅ precisão com dado oficial / setor.
8. **17f + 17c** (visão da cidade + dados abertos) e demais ondas conforme prioridade institucional.

> **Princípio:** cada onda entrega valor sozinha e reaproveita o que já existe (extrusão, DEM/LiDAR,
> hydro_simulator, diagnóstico, contingência, plano de ação, catálogo, agente IA, WebSocket de
> alertas, auditoria). Nada aqui exige refazer a base — só estendê-la, sempre no ciclo
> **ver → identificar → agir** e adequado à realidade do município.
