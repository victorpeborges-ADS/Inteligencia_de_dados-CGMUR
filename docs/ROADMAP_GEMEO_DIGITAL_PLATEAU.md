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

**Fases posteriores:** **18** (homologação, escala, LOD2 real) · **19** (higiene, robustez de UX, dado
real no piloto) · **20** (confiança, produto IA, honestidade metodológica, estética) ·
**21** (**motor preditivo com lastro observacional** — chuva observada, ground truth, solo, drenagem,
corpos hídricos e validação calibrada).

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
| 19c.2 | **MapBiomas oficial (6 municípios)** | P1 | M | ✅ CSV Coleção 10.1 dos 6 pilotos versionado em `scripts/mapbiomas_stats/` (DOI SJZOLT); coletor semeia `MAPBIOMAS_STATS_DIR` e grava `data_quality=oficial` |

### 19e — Entregas extras (jul/2026)

| # | Item | Prioridade | Esforço | Como |
|---|------|-----------|---------|------|
| 19e.1 | **Export KMZ das simulações** | P1 | M | ✅ `POST /simulations/export/kmz` + botão no `SimulationPanel` (mancha/curvas/escoamento → Google Earth/QGIS). |
| 19e.2 | **Launchers Windows/Mac** | P1 | M | ✅ `Abrir` / `Atualizar` / `Avaliar` (.bat CRLF + `.command`); finder `SINIDU_DIR.txt`; fix do atalho Mac (`echo"`). |

### 19d — Migrado para Fase 20

Itens que estavam em 19d foram priorizados na **Fase 20** (abaixo).

**Progresso Fase 19:** **12/12 (100%)** — 19a+19b+19c+19e ✅; 19d migrado para Fase 20.

---

## Fase 20 — Confiança, produto IA e operação multi-máquina

> Fechar o que ainda limita demo externa e escala operacional: confiança (auth/testes), produto de IA de domínio (não swarm genérico), dados oficiais no piloto e operação Mac↔Windows↔Dev Tunnel.

### 20a — Confiança e homologação (P0)

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20a.1 | **Testes HTTP** dos routers críticos (`simulations`, `monitoring`, `integrations`, export KMZ) | P0 | M | ✅ `tests/test_http_smoke_critical.py` (status, map-overview, KMZ) |
| 20a.2 | **Endurecer auth/secrets** (JWT/senhas default, CORS, superfície em Dev Tunnel) | P0 | M | ✅ Boot valida secret/senhas/CORS; compose.prod exige env; checklist Tunnel em `deploy/README` |
| 20a.3 | **Policy gate em ações sensíveis** (agente/UI não ativa plano, SMS ou alerta público sem confirmação humana) | P0 | S | ✅ `policy_gate` + `confirm=true` em activate/disseminate; UI confirma; agente só leitura |
| 20a.4 | **Documento único `ESTADO_ATUAL_SINIDU.md`** (tecnologias, features, falhas, ✅/⏳) | P1 | S | ✅ `documentacao/ESTADO_ATUAL_SINIDU.md` |

### 20b — Agentes de domínio (P0/P1)

> Evoluir o que já existe (`contextual_agent_*` + assistente RAG). **Não** substituir por swarm genérico.

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20b.1 | **Unificar `AssistantPanel` × `AgenteSinidu`** (um produto, dois modos ou um só) | P0 | M | ✅ Produto “Agente Sinidu”: FAB Operacional ↔ aba Normativo; banner cruzado; `agenteModo` no store |
| 20b.2 | **Contrato rígido de tools** (schema, testes, proibição de inventar nível de alerta / VERDE silencioso) | P0 | M | ✅ `execute_tool` → `unknown_tool`/`invalid_args`; alerta vivo com `interpretacao`/`disclaimer`; regra 12 no prompt |
| 20b.3 | **Tools de domínio em falta** (export KMZ/PDF via agente; lacunas do catálogo; “explique esta mancha”) | P1 | M | ✅ Parcial: `explain_mancha_inundacao` (limites + selo Derivado). Export KMZ/PDF continua na UI (agente só leitura) |
| 20b.4 | **Telemetria de IA** (latência, fallback determinístico, tokens, taxa de tool-error) | P1 | S | ✅ SSE `done` com `tool_calls`/`tool_errors`/`fallback_deterministic` + `ai_telemetry` no log |

### 20c — MCP (adapter, não runtime do produto) (P1)

> MCP como ponte para a **equipe** (Cursor/Claude Desktop), espelhando a API. Não é o runtime do painel web.

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20c.1 | **Servidor MCP fino** (5–10 tools read-only: overview, layers/meta, diagnostic, monitoring, simulation status, catalog gaps) | P1 | M | ✅ `app/mcp` — 7 tools + resource `sinidu://limits` |
| 20c.2 | **Auth no MCP** (token/JWT tenant-aware; rate-limit; sem write por padrão) | P0 | M | ✅ `SINIDU_MCP_TOKEN`/`JWT` + rate-limit + blocklist writes |
| 20c.3 | **Documentar uso MCP** para equipe (Cursor config + limites) | P2 | S | ✅ `docs/MCP_EQUIPE.md` |

### 20d — Ruflo / multiagente de coding (P3 — experimento opcional)

> **Fora do produto Sinidu entregue ao MCID.** Só tooling da equipe, com prazo e métrica.

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20d.1 | **Spike Ruflo 2 semanas** (fora do `docker-compose` do produto; métrica: tempo de PR / cobertura de testes gerada) | P3 | M | ❌ **No-go** — spike não executado; tooling externo fora do produto MCID |
| 20d.2 | **Go/No-go**: manter só se houver ganho medido; senão descartar (não embutir no compose) | P3 | S | ✅ **No-go confirmado** — Ruflo não entra no compose nem no pipeline do produto |

### 20e — Dados e simulação (P1)

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20e.1 | **MapBiomas Coleção 10.1** nos 6 municípios (CSV oficial em `MAPBIOMAS_STATS_DIR`) | P1 | M | ✅ Fechado com 19c.2 (`scripts/mapbiomas_stats` + seed automático) |
| 20e.2 | **KMZ pacote completo** (mancha + bairros afetados + pontos de contingência, se houver) | P2 | M | ✅ Pastas KML `mancha`/`bairros_afetados`/`pontos_contingencia`; `collect_kmz_package_features` |
| 20e.3 | **Unificar narrativa de previsão** (OpenMeteo + CEMADEN + fallback — um selo só na UI) | P1 | M | ✅ `forecast_source_seal` + `selo_previsao` no Monitor/semáforo; copy “prevista” só quando OpenMeteo |

### 20h — Honestidade e acurácia metodológica das simulações (P0)

> As simulações usam **dados oficiais de entrada** e pedaços de GIS/literatura clássicos, mas **não** são metodologias oficiais ANA/CEMADEN/CPRM/INMET-IDF nem hidrodinâmica 2D. O produto deve deixar isso inequívoco na UI e elevar o que for viável (IDF oficial, validação espacial).

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20h.1 | **Copy e UI alinhados ao `method_note`** — nunca apresentar simulação como “metodologia oficial”; selo Derivado/Estimado visível no painel e no mapa | P0 | S | ✅ Badges nas abas; `qualidade_dado` na mancha; nota MD por `simulationTipo()`; RiskPanel mostra `qualidade` |
| 20h.2 | **Painel de limites metodológicos** na aba Simulações (o que é / o que não é: não-laudo, não-HEC-RAS, não-alerta CEMADEN) | P0 | S | ✅ Bloco colapsável no `SimulationPanel` + `LIMITES_METODOLOGICOS_PAINEL` |
| 20h.3 | **Separar na UI** “cenário Sinidu (Derivado)” vs “LST/observado GeoReDUS (Oficial)” no comparador de calor | P0 | S | ✅ Headers/tabela Observado × Derivado; limites completos; Badge Observado |
| 20h.4 | **IDF oficial onde existir** (ANA/INMET/PDF municipal) substituindo tabelas internas `Estimado` | P1 | M | ✅ Override em `backend/data/idf/<codigo_ibge>.json` tem precedência sobre `_IDF_MUNICIPAL`; piloto Recife (`2611606.json`, `qualidade=Oficial`); `scripts/idf/README.md` |
| 20h.5 | **Camada de validação** com manchas/estudos oficiais (Defesa Civil/CPRM) quando houver — além do hit-rate pontual S2ID | P1 | M | ✅ `official_flood_map_service.py` (IoU/coberturas via shapely) + camada `manchas_oficiais` no mapa + `validacao_mancha_oficial` no `simulation_meta`; fixture piloto Recife; `scripts/manchas_oficiais/README.md` |
| 20h.6 | **Checklist de linguagem** (demo MCID / apresentação / agente): proibir “oficial”, “homologado”, “preciso como engenharia” sem qualificador | P0 | S | ✅ `docs/CHECKLIST_LINGUAGEM_HONESTIDADE.md` + regras no `SYSTEM_TEMPLATE` do agente |
| 20h.7 | Documentar teto de acurácia em `DOCUMENTACAO_TECNICA` + `ESTADO_ATUAL` (triagem ≠ laudo) | P1 | S | ✅ §18.1 + `ESTADO_ATUAL_SINIDU.md` |

**Fora do horizonte imediato (não fingir que cabe no MVP):** hidrodinâmica 2D / SWMM / inventário completo de galerias — só com projeto dedicado e dado de rede.

### 20f — UX / manutenção (P2)

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 20f.1 | Layout **mobile/responsivo** + acessibilidade (tablist/foco) | P2 | L | ✅ Shell `flex-col lg:flex-row`; painel full-width no mobile; `role=tablist` + setas ←/→ |
| 20f.2 | Quebrar `SimulationPanel` / `MapContainer` (hotspots) | P2 | L | ✅ `mapPopups.ts` extraído do MapContainer (−422 linhas); `SimulationResults.tsx` + `simulationFormat.ts` extraídos do SimulationPanel (−1432 linhas); formulários de chuva ainda no painel (próximo corte, se necessário) |
| 20f.3 | Playbook **Mac ↔ Windows ↔ Dev Tunnel** (git pull, rebuild, checagem API pública) | P1 | S | ✅ `docs/PLAYBOOK_MULTI_MAQUINA.md` |
| 20f.4 | **Estética sóbria e profissional** (tokens, tipografia, densidades, chrome do shell — sem mudar fluxos) | P1 | M | ✅ Source Sans 3; accent teal; header/tabs sem glow/pills; KPI/PanelSection densos; checkpoint `ui-checkpoint-pre-estetica-sobria` mantido |
| 20f.5 | **Mapa fixo + scroll só no painel** (Simulações e demais abas split painel\|mapa) | P0 | S | ✅ `h-dvh` + `min-h-0` + lock scroll do documento; só painel `overflow-y-auto` |
| 20f.6 | **Animação “Evolução no tempo” útil** (hoje ~inútil na demo) | P0 | M | ✅ 13 frames + narrativa; chrome no mapa; ritmo/loop/pico; aviso se sem features |

**Aceite 20f.5:** ao rolar o painel esquerdo (ex.: aba Simulações em Recife), o mapa à direita **não** sobe/desce com a página; header e abas ficam no lugar; só o conteúdo do painel (`overflow-y-auto`) rola. Desktop primeiro; mobile pode empilhar (alinhar com 20f.1).

**Nota técnica (20f.5):** `PlatformApp` já tem `overflow-y-auto` no painel e `overflow-hidden` no mapa, mas o `<main>` usa `min-h-screen` (não altura travada) — o documento inteiro cresce e o browser rola mapa+painel juntos. Corrigir cadeia de altura (`h-screen` / `min-h-0` no flex) sem mudar fluxos.

**Aceite 20f.6** (melhorar o que veio de **17g.1b**, sem fingir HEC-RAS):
1. **Ligado ao mapa de verdade** — play/slider atualiza a mancha no território de forma óbvia (opacidade/profundidade/fase); se `flood_timeline_features` faltar, avisar em vez de “Animar” morto.
2. **Controles no mapa** (ou chrome fixo) — relógio `t = X h`, fase (subida/pico/recessão), play/pause/reset; não depender de scrollar o painel para entender o frame (casa com 20f.5).
3. **Mais frames / ritmo demo** — >5 passos ou interpolação visual; velocidade configurável; loop opcional; destaque do pico.
4. **Legenda honesta** — “aproximação por escala do DEM (hidrograma triangular) ≠ modelo hidrodinâmico 2D”; selo Derivado.
5. **Narrativa mínima** — 1 frase por fase (“mancha sobe”, “pico”, “água recua”) alinhada ao frame.

Não é SWMM/unsteady 2D (fora do MVP — ver 20g).

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

**Progresso Fase 20:** **27/~28 itens ativos (~96%)** — **20a–20c ✅**; **20d No-go ✅**; **20e ✅**; **20f ✅**; **20h ✅**.

---

## Fase 21 — Motor preditivo com lastro observacional

> **Objetivo:** transformar a predição de alagamento de *score heurístico* em **modelo verificável**, com chuva observada, rótulo real, variáveis físicas do território e incerteza calibrada. A ambição declarada é ser o melhor sistema municipal de simulação e análise preditiva do país — o caminho para isso é **dado e validação**, não sofisticação de algoritmo.

### 21.0 — Diagnóstico que originou a fase (auditoria jul/2026)

| Achado | Evidência | Gravidade |
|--------|-----------|-----------|
| **ML em produção é circular** — os 10 artefatos em `backend/ml/artifacts/` são `model_kind: "baseline_synthetic"`: 900 amostras geradas por fórmula logística em `ml/baseline.py`, e o Random Forest aprende essa fórmula | `auc_roc_cv` 0,98–0,99 nos metas; `note` do próprio JSON pede retreino | **Crítica** |
| **Caminho “full” nunca materializado** — `ml/train.py` + `ml/features.py` sabem cruzar S2ID × precipitação, mas nenhum artefato tem `model_kind: "full"` | ausência de artefato full | **Crítica** |
| **Sem pluviometria observada persistida** — nenhuma tabela PostGIS de chuva medida; única série densa é reanálise Open-Meteo (ERA5) diária no centróide, em Parquet fora do banco | `ml/precipitation.py` (`OPENMETEO_ARCHIVE`, 2000–2024) | **Alta** |
| **Ground truth quase inexistente** — 22 eventos curados nos 6 pilotos (2 a 9 por cidade); fora dos pilotos os eventos S2ID são sintéticos | `s2id_collector._events_for_municipality` | **Crítica** |
| **Série descartada a cada 7 dias** — `MonitoringAlert` e `WeatherForecastCache` são purgados; a base previsão × desfecho nunca acumula | `weather_monitor.cleanup_old_records(days=7)` | **Alta** |
| **Features desalinhadas treino ↔ inferência** — `precip_7d` na inferência é `precip_72h * 1.15`; no monitor `p48 = (p24 + p72)/2` | `ml/predictor.py`, `services/weather_monitor.py` | **Alta** |
| **Rótulo *same-day*** — evento no dia seguinte à chuva conta como falso negativo | `ml/features.py` (`label` por `date_only`) | Média |
| **Sem calibração probabilística** — saída é `predict_proba` bruto; sem Brier, sem curva de confiabilidade, sem hold-out (o modelo final é treinado em 100% dos dados) | `ml/train.py` | **Alta** |
| **Dois sistemas de risco paralelos e não integrados** — ML (`risk_probability`) vs semáforo (Score/IVC/IRI) | `risk_traffic_light_service.py` | Média |

### 21a — Parar o dano e começar a acumular (P0)

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 21a.1 | **Marcar `baseline_synthetic` como não-produção**: bloquear uso do artefato sintético no Monitor e exibir “score heurístico de chuva”, nunca “probabilidade” | P0 | S | ✅ Monitor só usa ML se `model_kind=full`; UI/agent rotulam heurística |
| 21a.2 | **Não expor `auc_roc_cv` de modelo sintético** em API/UI (métrica enganosa) | P0 | S | ✅ `public_auc()` / `model_policy.py`; status e predict ocultam AUC sintético |
| 21a.3 | **Remover purge de 7 dias** para previsão/alertas — passar a arquivar (tabela quente 7d + histórica indefinida) | P0 | S | ✅ `cleanup_old_records` arquiva em `*_archive` (migração 024) |
| 21a.4 | **Tabela de verificação** `previsao_verificacao`: o que foi previsto, quando, para onde, e o desfecho observado depois (base de acerto do sistema) | P0 | M | ✅ Tabela + gravação no sync; desfecho ainda NULL (preenchimento em 21g/21c) |
| 21a.5 | **Alinhar features treino ↔ inferência** (fim do `precip_72h * 1.15` e do `p48` médio) | P0 | S | ✅ OpenMeteo `past_days=7`; janelas 24/48/72h + 7d reais; `precip_7d` no predict |

### 21b — Dados observados de verdade (P0)

> O Brasil tem séries públicas profundas que o sistema **não usa**. Validar disponibilidade/formato de cada API antes de comprometer sprint.

| # | Fonte | O que entrega | Prioridade | Esforço | Status |
|---|-------|---------------|-----------|---------|--------|
| 21b.1 | **CEMADEN pluviômetros** | chuva a cada 10 min, ~4.700 estações, desde ~2014 — medição real com densidade intra-urbana | P0 | L | 🔶 Snapshot vivo via `getJson2.php` + **série diária materializada** (`materialize_cemaden_daily_from_snapshots`: último `acc24hr` do dia civil → `granularidade=diaria`); sync no monitor/scheduler; série histórica 10/10 min ainda exige captcha/CSV depositado |
| 21b.2 | **ANA / HidroWeb (SNIRH)** | séries pluvio **e fluviométricas** de décadas; cota de rio = rótulo contínuo | P0 | L | 🔶 Stub + probe (`ana_hidroweb_collector`); exige `ANA_HIDROWEB_TOKEN` (hidro@ana.gov.br); ingestão completa pendente |
| 21b.3 | **INMET / BDMEP** | estações horárias, séries longas; base para IDF real (casa com 20h.4) | P1 | M | 🔶 Coletor CSV + `POST /monitoring/sync/inmet-bdmep` + pasta `scripts/inmet_bdmep/`; API BDMEP autenticada ainda pendente |
| 21b.4 | **MERGE / CPTEC-INPE** | precipitação por satélite calibrada por pluviômetro, grade ~10 km — cobre onde não há estação | P1 | M | ✅ Coletor GRIB2 (`merge_cptec_collector`) + `POST /monitoring/sync/merge-cptec` + cache `scripts/merge_cptec/`; amostra PREC no centróide → `fonte=merge` / `reanalise` |
| 21b.5 | **ANADEM / MERIT-Hydro** | DEM hidrologicamente condicionado — substitui SRTM cru no D8 (hoje só há *fill* interno) | P0 | M | ✅ Paths `*_merit`/`*_anadem`; `hydro_dem` no meta; skip Priority-Flood; README `scripts/dem_hidro/` (clip GeoTIFF ainda manual) |
| 21b.6 | **Tabela `serie_pluviometrica_observada`** (`estacao_id`, `timestamp`, `precip_mm`, `fonte`) no PostGIS — fim do Parquet solto | P0 | M | ✅ Migração 025 + upsert; Open-Meteo ERA5 persiste como `reanalise`; CEMADEN CSV como `oficial` |

### 21c — Ground truth denso (P0, contínuo)

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 21c.1 | **Ingerir S2ID nacional completo** (FIDE / reconhecimentos) — centenas a milhares de eventos reais, em vez dos 22 curados | P0 | L | 🔶 CSVs 2013–2022 baixados + sync (`+41` oficiais nos pilotos); Recife ainda ~12 oficiais — densificar com campo/BDMEP |
| 21c.2 | **Parar de usar evento S2ID sintético como rótulo** — separar `data_quality` `oficial` de `estimado` e nunca treinar no segundo | P0 | S | ✅ Coluna `data_quality` + filtro em `ml/features.py`; treino `full` exige ≥1 positivo oficial |
| 21c.3 | **Rótulo contínuo por cota de rio** (ANA) onde houver estação — muito superior ao binário | P1 | M | ✅ Tabela `serie_fluviometrica_observada` + CSV ANA + `POST /sync/ana-fluvio`; features `cota_rio_*` no ML |
| 21c.4 | **Canal de registro em campo** pela Defesa Civil municipal (ponto/polígono + data/hora + severidade) — converte usuário em fonte de dado | P1 | L | ✅ `POST /monitoring/eventos-observados` + form no Monitor (`FieldFloodEventForm`); `fonte=defesa_civil` |
| 21c.5 | **Tabela `evento_alagamento_observado`** (geometria, início/fim, severidade, fonte, chuva acumulada associada) | P0 | M | ✅ Tabela + sync automático a partir de S2ID `oficial_curado` |

### 21d — Variáveis físicas do modelo (P0/P1)

> Escopo pedido explicitamente: além do **volume** de chuva, o modelo deve considerar **duração/intensidade**, **corpos hídricos**, **séries históricas**, **suscetibilidade por região da cidade**, **tipo de solo** e **capacidade de escoamento de água/esgoto**. A tabela abaixo separa o que **já existe** (e onde) do que **falta**.
>
> Ponto central: hoje o ML usa **8 features** (`precip_24h/48h/72h/7d`, `mes_do_ano`, `impermeabilizacao_pct`, `cobertura_vegetal_pct`, `declividade_media`) — **nenhuma** delas representa corpo hídrico, solo, drenagem, suscetibilidade local ou intensidade horária. Várias dessas variáveis já existem na **simulação física** e simplesmente não chegam ao modelo.

| # | Variável | Estado hoje | Alvo | Prior. | Esforço | Status |
|---|----------|-------------|------|--------|---------|--------|
| 21d.1 | **Duração e intensidade da chuva** | simulação física usa `HYDROGRAPH_DURATION_H = 6.0` **fixo** e `duracao_h` (0,25–6 h) na drenagem; o **ML só vê acumulados** | features de **intensidade máxima (mm/h e mm/10 min)**, **duração do evento**, e **razão intensidade/IDF** para o tempo de retorno — porque 60 mm em 1 h ≠ 60 mm em 24 h | **P0** | M | 🔶 `duracao_chuva_h`, `intensidade_media_mm_h`, `intensidade_pico_proxy_mm_h`, `razao_intensidade_idf_tr2` (Open-Meteo hours + IDF TR2); mm/10 min horária ainda pendente |
| 21d.2 | **Corpos hídricos** | máscara da classe MapBiomas `Corpo d'água` com buffer proporcional à chuva (`_reinforce_water_bodies`) | **hidrografia oficial** (ANA Base Ottocodificada / IBGE) + **HAND** (*Height Above Nearest Drainage*) e distância à drenagem como features — HAND é o preditor isolado mais forte de inundação na literatura | **P0** | L | 🔶 HAND via DEM/D8 (`hand_service`) → `hand_media_m` + `pct_hand_lt_5m` no vetor ML; hidrografia oficial ANA ainda pendente |
| 21d.3 | **Tipo de solo** | **ausente por completo** — zero referência a pedologia, grupo hidrológico ou *Curve Number* no código | **grupo hidrológico A/B/C/D** (Embrapa/IBGE pedologia ou SoilGrids 250 m) → cruzar com uso do solo MapBiomas para derivar **SCS-CN** e escoamento por célula | **P0** | L | 🔶 SCS-CN proxy MapBiomas × grupo C default (`scs_cn_service`) → `curve_number`; SoilGrids/Embrapa pendente |
| 21d.4 | **Capacidade de escoamento (água/esgoto/drenagem)** | proxy municipal em `drainage_capacity_service`: `indice_drenagem` SNIS ou cobertura, *clamp* 8–50 mm/h, eficiência fixa 0,85 | **espacializar por bairro**, usar módulo de drenagem do SNIS/SINISA quando existir, permitir **cadastro municipal de galerias** por upload, e expor saturação como feature | **P0** | M | 🔶 Features `capacidade_drenagem_mm_h` + `saturacao_drenagem_40mm`; espacialização por bairro (impermeab./água); inventário de galerias pendente |
| 21d.5 | **Suscetibilidade por região da cidade** | IRI heurístico por bairro; probabilidade de bairro é *blend* `municipal_prob * 0,55 + iri * 0,45` | **cartas de suscetibilidade e setores de risco CPRM** + suscetibilidade derivada de HAND/TWI; **modelo treinado por bairro**, não *blend* de número municipal | **P0** | L | 🔶 `suscetibilidade_hand` + `twi_media` no vetor; `suscetibilidade_local` por bairro; **21f.2** modelo `full_bairro` no ranking; CPRM ainda pendente |
| 21d.6 | **Séries históricas** | reanálise Open-Meteo diária (Parquet), MapBiomas em 6 anos-âncora, PIB ~22 anos; sem chuva observada | séries observadas de 21b + **estado antecedente do solo** (chuva acumulada 5/10/30 d), **sazonalidade** e **tendência de impermeabilização** entre anos-âncora | **P0** | M | 🔶 `precip_5d/10d/30d` + `sazonalidade_sin/cos` + `tendencia_impermeabilizacao_pp_a` (MapBiomas); OpenMeteo `past_days=30` na inferência |
| 21d.7 | **Janela temporal com defasagem** | rótulo *same-day*, sem *lag* | features de D-3 a D+1 e rótulo com janela de tolerância (evento no dia seguinte deixa de ser falso negativo) | **P0** | S | ✅ Rótulo positivo se evento em D−3…D+1 (`LABEL_LAG_*`) |
| 21d.8 | **Arquitetura híbrida (física → ML)** | simulação física e ML são **sistemas desconexos** | saída da simulação (lâmina, área alagada, rede saturada) entra como **feature** do ML; ML calibra parâmetros da física contra evento observado | P1 | L | ✅ Proxies O(1) SCS+rede (`ml/physics_proxy.py`): `lamina_proxy_mm`, `escoamento_excesso_mm`, `rede_saturada_flag`, `area_alagada_proxy_pct` no vetor treino/inferência; selo Derivado (≠ DEM) |
| 21d.9 | **Nível de rio / inundação fluvial** | ausente — só chuva | cota observada ANA como variável e como rótulo; separar **alagamento pluvial** de **inundação fluvial** (fenômenos distintos, hoje tratados como um) | P1 | M | ✅ `fenomeno` pluvial/fluvial/misto + features `cota_rio_disponivel`/`cota_rio_anomalia`; API fluvio CSV |

### 21e — Protocolo de validação (P0 — não opcional)

> É o que separa “sistema sério” de “demo com AUC”. Deve rodar **em paralelo** a 21d, nunca depois.

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 21e.1 | **Hold-out temporal real** (treinar até 2021, validar 2022–2024) e **nunca refitar no conjunto de teste** | P0 | M | ✅ `ml/validation.py` + treino só no split de treino |
| 21e.2 | **Brier score + curva de confiabilidade** publicados junto de qualquer probabilidade (AUC deixa de ser métrica única) | P0 | M | ✅ Brier modelo/baselines + `reliability_curve` no meta |
| 21e.3 | **Calibração explícita** (Platt ou isotônica): “70%” tem de significar que ocorreu em ~70% dos casos | P0 | M | ✅ Isotônica (`CalibratedClassifierCV`) quando há rótulos suficientes |
| 21e.4 | **Baselines obrigatórios** — “chuva > X mm” e climatologia sazonal. **Se o modelo não bate o limiar simples, é descartado** | P0 | S | ✅ Compara Brier; `full_below_baseline` fora de produção |
| 21e.5 | **Validação espacial** — hit-rate da mancha contra evento georreferenciado (integra 20h.5) | P1 | M | ✅ `evaluate_spatial_hit_rate` (zona suscetibilidade × eventos oficiais); meta + model card + `/flood-risk/status` |
| 21e.6 | **Card de modelo** por município (dados, período, features, métricas, limitações) versionado no repo | P1 | M | ✅ `flood_model_{ibge}_card.md` gerado no treino |

### 21f — Modelo e simulação (P1 — só depois de 21b/21c/21e)

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 21f.1 | **Gradient boosting** (LightGBM/XGBoost) substituindo Random Forest — melhor em tabular desbalanceado e roda bem em CPU | P1 | M | ✅ `HistGradientBoosting` sklearn (`model_factory`, ML v1.4); fallback RF; importâncias por permutação |
| 21f.2 | **Modelo por bairro** com features locais (HAND, CN, drenagem, suscetibilidade) | P1 | L | ✅ Dataset `*_labeled_bairro.parquet`; artefato `flood_model_{ibge}_bairro_v1.pkl` (`full_bairro`); ranking via `predict_proba` local com fallback blend; UI `neighborhood_ranking_mode` |
| 21f.3 | **Horizonte explícito** (D+1, D+2, D+3) em vez de classificação pontual sem horizonte | P1 | M | ✅ `ml/horizon.py` + `horizons[]` na predicao; cards D+1/2/3 na UI |
| 21f.4 | **Intervalo de incerteza** na saída, não número único | P1 | M | ✅ Dispersão entre árvores RF → `uncertainty` (IC≈90%); fallback margem heurística |
| 21f.5 | **Integrar ML e semáforo** num único modelo de risco documentado (fim dos dois sistemas paralelos) | P1 | M | ✅ `unified_risk_model` + componente `ml_preditivo` no painel; status = max(estrutural, ML full); heurística capada em AMARELO; `modelo_risco` na API |

### 21g — Produto e confiança visível (P1)

| # | Item | Prioridade | Esforço | Status |
|---|------|-----------|---------|--------|
| 21g.1 | **“Acertamos Y% das últimas Z previsões”** na UI, alimentado por `previsao_verificacao` — é isso que ganha confiança de gestor, não AUC | P1 | M | ✅ `previsao_verificacao_service` (backfill desfecho + acerto); card no Monitor; dashboard `acerto_previsoes` |
| 21g.2 | **Previsão de impacto, não de chuva**: bairros afetados, população exposta, medidas cabíveis na capacidade fiscal | P1 | L | ✅ `flood_impact_service` + `impact` na predicao; card na Análise Preditiva (pop. × CAPAG × medidas) |
| 21g.3 | **Explicabilidade por variável** (contribuição de chuva, solo, drenagem, HAND) na resposta | P1 | M | ✅ `ml/explainability.py` (domínios RF); `explanation` na predicao; barras na Análise Preditiva |

### Critérios de aceite da Fase 21 (travados antes de codar)

1. Existe **≥ 1 modelo com `model_kind != baseline_synthetic`**, treinado em rótulo observado.
2. **Brier score e curva de confiabilidade** publicados, com hold-out temporal.
3. O modelo **bate o baseline “chuva > X mm”** — se não bater, é descartado, não maquiado.
4. `previsao_verificacao` com **N previsões e desfechos** reais registrados.
5. Nenhuma tela apresenta saída de modelo sintético como probabilidade.
6. As variáveis de 21d.1–21d.6 estão **de fato no vetor de features**, não apenas na simulação física.

### Posicionamento estratégico

Competir com o **CEMADEN em *nowcasting*** de chuva é perder: eles têm radar, rede nacional e mandato. O nicho defensável e desocupado é **previsão de impacto em escala municipal e intra-urbana**, cruzando clima com vulnerabilidade social, capacidade fiscal e infraestrutura, com incerteza honesta e ação recomendada.

### Teto de acurácia (explícito)

Sem inventário de galerias e sem radar meteorológico, **não se chega a acurácia de projeto de engenharia**. Chega-se a **priorização confiável e verificada** — que é mais do que qualquer painel municipal brasileiro oferece hoje. Este teto deve constar da documentação técnica (casa com 20h.7).

### Fora de escopo da Fase 21

| Item | Motivo |
|------|--------|
| *Deep learning* em imagem de satélite | Sem GPU (Mac mini 2018, UHD 630); ganho marginal vs tabular |
| Hidrodinâmica 2D / SWMM nacional | Exige dado de rede + projeto dedicado (ver 20g) |
| Treinar os 5.570 municípios | Aprofundar nos 6 pilotos até ser cientificamente defensável e só então escalar |
| Novos cenários de simulação | Congelados até os existentes estarem validados |

**Progresso Fase 21:** **~38/~40 itens (~95%)** — **21a ✅**; **21d 🔶/✅** (21d.8/21d.9 ✅); **21e ✅**; **21g ✅**; **21f ✅**; **21b.4/21b.5/21b.6 ✅**; **21c.3/21c.4/21c.5 ✅**; **21b.1–3/21c.1 🔶** (dado externo/token).

**Retreino Recife (jul/2026):** `etl_flood_ml.py --municipio 2611606 --force` gerou `model_kind=full_below_baseline` (AUC hold-out 0,80; Brier 0,20 > chuva 0,08 e clima 0,07) — protocolo 21e.4 descartou corretamente. Rio (`3304557`) e São Paulo (`3550308`) já têm `model_kind=full` em produção. Cards versionados em `backend/ml/model_cards/`.

**Próximo:** depositar CSV BDMEP/ANA (cota); histórico CEMADEN com captcha; densificar rótulos Recife (campo UI) até `model_kind=full`. Ver `docs/PLAYBOOK_DADOS_OBSERVADOS.md`.

### Quanto falta (visão rápida — jul/2026)

| Fase | Progresso | O que trava o fechamento |
|------|-----------|--------------------------|
| 17 | ~99% | LOD2 UI pausada (qualidade) |
| 18 | ~78% | LOD2/3D Tiles pausados |
| 19 | **100%** | Fechada (19d migrado → 20) |
| **20** | **~96%** | Ruflo No-go; UX mobile ✅ |
| **21** | **~95%** | **🔶 dados externos** — BDMEP/ANA token + densificar rótulos Recife |

**S2ID nacional (jul/2026):** CSVs 2013–2022 em `scripts/s2id_nacional/downloads/`; sync OK (`created` 27+14). Retreino Recife → ainda `full_below_baseline` (Brier 0,20 > chuva 0,08) — protocolo 21e.4 correto.

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
