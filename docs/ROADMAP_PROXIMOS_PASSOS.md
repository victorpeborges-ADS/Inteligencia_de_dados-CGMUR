# Roadmap — Próximos passos Sinidu+Clima

**Data:** ago/2026  
**Escopo:** o que ainda falta implementar após a onda de maturidade com dados abertos (HAND, vias, ativos críticos, SoilGrids, hidrografia OSM, GloFAS, CSV de impactos).  
**Contexto:** laboratório interno de experimentação metodológica (não plataforma nacional crítica).  
**Complementa:** [`ROADMAP_GEMEO_DIGITAL_PLATEAU.md`](./ROADMAP_GEMEO_DIGITAL_PLATEAU.md) (Fases 17–21).  
**Fontes de evolução:** diálogo metodológico (lab) + síntese multidimensional (simulação / assistente / automação) — filtradas para o que o código e o mandato atual suportam.

---

## 0. Acervo recente (já entregue — não reabrir sem motivo)

| Capacidade | Onde |
|---|---|
| Motor hidro 2.9/2.10 — vale local + grade LiDAR fina | `hydro_simulator.py` |
| Camada HAND (suscetibilidade topográfica) | `hand_suscetibilidade` |
| Vias intransitáveis (OSM × mancha) | overlay pós-simulação |
| Ativos críticos atingidos (INEP/CNES/abrigos) | overlay + meta |
| SoilGrids → grupo hidrológico / CN | `soilgrids_service` + SCS-CN |
| Hidrografia OSM (motor + camada) | `hidrografia_osm` |
| Hazard GloFAS RP100 + overlap % | `hazard_referencia` + `glofas_compare` |
| Fallback escolas OSM | `inep_educacao_collector` |
| Export CSV impactos + GeoJSON/KMZ com vias/ativos | `export/impacts-csv` |
| Maturidade municipal Bronze/Prata/Ouro | `maturity_engine` |
| Faixas de incerteza (±precipitação) | `uncertainty_bands_service` |
| Calibração hidro (base) + hit-rate S2ID / IoU manchas | `hydro_calibration_service`, validação 21e |
| IDF / `periodo_retorno_anos` no request de chuva extrema | `idf_rainfall_service` + schemas |
| Prewarm boot (DEM + sims + agent bundles) | `dem_prewarm`, `simulation_prewarm`, boot |
| Sync alertas CEMADEN | `cemaden_monitor` + `monitoring_sync` |
| RAG eval (retrieval hit + keywords) | `backend/rag/eval/` |
| Model card ML (treino) | `ml/validation.write_model_card` |

---

## Checklist — ainda a implementar

> Itens pendentes do roadmap (nenhum marcado ✅ ainda). Ordem sugerida na §7.  
> **Fora de escopo:** D.4 (nowcasting radar). **Só com mandato:** D.1–D.3, D.5.

### Agora (P0 / esforço S–M)

- [ ] **A.1** PDF de oficina com vias, ativos críticos e overlap GloFAS
- [ ] **A.2** Atalho pós-simulação “ligar HAND + GloFAS + hidrografia”
- [ ] **E.2** Eventos golden + skill scores POD / FAR / CSI
- [ ] **E.8** Assistente: RAG híbrido + citação obrigatória + abstenção
- [ ] **E.1** Manifesto de simulação (meta + hashes de inputs)
- [ ] **E.3** Gate de maturidade → linguagem permitida
- [ ] **F.1** Gatilho CEMADEN → simulação-padrão (pilotos)
- [ ] **B.1** Microdados INEP por município
- [ ] **B.2** IDF oficial além de Recife
- [ ] **C.3** Alturas reais de edifício (nDSM) nos pilotos PE3D
- [ ] **D.6** Calibração multi-evento densa (sucede E.2/E.5)

### Em seguida (P1)

- [ ] **A.3** Card SoilGrids na UI
- [ ] **A.4** Lista operacional no painel (top N vias + escolas/UBS)
- [ ] **A.5** Sync escolas ao abrir município (se 0 no banco)
- [ ] **A.7** Cenários RP padronizados na UI (RP10 / RP25 / RP100)
- [ ] **E.4** Comparador metodológico A × B
- [ ] **E.5** Calibração multiobjetivo
- [ ] **E.7** Ensembles leves + mapa de robustez
- [ ] **E.9** Model card municipal (hidro + ML)
- [ ] **F.2** Pré-computação agendada de cenários RP
- [ ] **B.3** Hidrografia ANA Ottocodificada
- [ ] **B.4** Manchas oficiais depositadas (mais municípios)
- [ ] **B.5** Séries ANA HidroWeb / INMET BDMEP
- [ ] **B.7** Cartas CPRM / setores de risco
- [ ] **C.1** LOD2 telhados na UI
- [ ] **C.4** Timeline de inundação óbvia no mapa
- [ ] **C.5** Exposição por edifício na UI
- [ ] **C.6** População por setor censitário × mancha
- [ ] **D.2** Inventário de galerias / microdrenagem

### Depois / P2

- [ ] **A.6** Legenda unificada pós-simulação
- [ ] **E.6** Model selector experimental
- [ ] **E.10** Blend leve com GloFAS
- [ ] **F.3** Modo sentinela pluviométrico
- [ ] **F.4** Fila de avaliação pós-evento
- [ ] **B.6** CEMADEN histórico 10 min
- [ ] **B.8** Pedologia Embrapa
- [ ] **C.2** Viewer 3D Tiles estável
- [ ] **C.7** Cenários what-if (telhado verde × ativos)

### Só com escopo explícito (mês+)

- [ ] **D.1** Hidrodinâmica 2D / adaptador SWMM–HEC-RAS–3Di
- [ ] **D.3** Ensembles climáticos / TRs multi-década
- [ ] **D.5** CityGML nacional padronizado

---

## 1. Horizonte A — Polimento de produto (1–3 dias)

> Alto valor de uso imediato; pouco risco técnico.

| # | Item | Prioridade | Esforço | Notas |
|---|------|-----------|---------|--------|
| A.1 | **PDF de oficina** incluir vias, ativos críticos e overlap GloFAS | P0 | S | CSV já exporta; o PDF ainda não lista esses blocos |
| A.2 | **Atalho pós-simulação** “ligar HAND + GloFAS + hidrografia” | P0 | S | Um clique no painel de resultados / presets do LayerPanel |
| A.3 | **Card SoilGrids na UI** (grupo, textura, CN, escala de escoamento) | P1 | S | Dados já em `simulation_meta.soilgrids` / CN |
| A.4 | **Lista operacional no painel** (top N vias + escolas/UBS) sem abrir CSV | P1 | S | Espelhar o que o CSV já contém |
| A.5 | **Sync escolas** ao abrir município (se 0 no banco) | P1 | S | Fallback OSM já existe; falta disparo no onboarding/ensure |
| A.6 | **Legenda unificada** pós-simulação (mancha + vias + ativos + GloFAS) | P2 | S | Reduz confusão no 3D |
| A.7 | **Cenários RP padronizados na UI** (RP10 / RP25 / RP100) | P1 | S | Backend já aceita `periodo_retorno_anos` + IDF; atalhos no painel na mesma língua de GloFAS/seguradoras |

**Entregável A:** gestor vê, exporta e explica o cenário sem sair do painel.

---

## 2. Horizonte E — Laboratório metodológico (1–4 semanas)

> Transformar amplitude já existente em **reprodutibilidade, skill conhecido e aprendizado**, sem pivotar para plataforma nacional crítica.  
> Premissa: assertividade sobe quando o sistema distingue exploratório / provável / calibrado — e sabe abster-se.  
> Skill do motor: publicar POD / FAR / CSI (threat score) nos pilotos — não só “é triagem”.

| # | Item | Prioridade | Esforço | Notas |
|---|------|-----------|---------|--------|
| E.1 | **Manifesto de simulação** — expandir `simulation_meta` | P0 | M | Commit/versão do motor, DEM+hash, fontes/datas, IDF, maturidade, avisos metodológicos; cache key com hashes de inputs (não só `HYDRO_MODEL_VERSION`). Sem STAC/OGC completo. |
| E.2 | **Eventos golden + skill scores POD/FAR/CSI** | P0 | M | Recife + 1 PE: S2ID / manchas / Defesa Civil. Além de IoU/hit-rate já existentes — **POD** (recall espacial), **FAR**, **CSI**. Frase-alvo: “triagem com CSI=X no piloto Recife”. |
| E.3 | **Gate de maturidade → linguagem permitida** | P0 | S | Evoluir Bronze/Prata/Ouro: Bronze = exploratório (sem probabilidade forte); Prata/Ouro = mais assertivo; UI e assistente respeitam o teto. Dimensões por camada (completude, atualidade, linhagem) no catálogo — sem substituir o score único de uma vez. |
| E.4 | **Comparador metodológico** (A × B) | P1 | M | Além de antes×depois de cenário: com/sem SoilGrids, SRTM×LiDAR, versão motor N×N+1; mapa de diferença (só A / só B / interseção). |
| E.5 | **Calibração multiobjetivo** (evoluir serviço atual) | P1 | L | Partir de `hydro_calibration_service`: CN, vale local, drenagem, limiares; fronteira CSI/IoU ↔ vias/ativos; aprovação humana antes de “publicar” params. |
| E.6 | **Model selector experimental** | P2 | M | Dado maturidade + dados disponíveis, recomendar motor/config; usuário pode ignorar e forçar comparação. |
| E.7 | **Ensembles leves + mapa de robustez** | P1 | L | Expandir `uncertainty_bands_service`: variar CN/HSG, erro vertical do DEM, distribuição temporal da chuva; faixa na mancha + robustez alta/média/baixa; decompor incerteza (dado × parâmetro × modelo). |
| E.8 | **Assistente: RAG híbrido + citação + abstenção** | P0 | M | Busca densa+esparsa, rerank (~20→5→3–5), citação obrigatória no normativo; recusa se confiança baixa. Pacote: conclusão, evidências, fontes, ausências, incerteza. Eval dourado em `rag/eval` a cada mudança de prompt/modelo. Router explícito normativo × operacional. Audit das decisões de IA (recuperado, fonte, confiança). Failover Ollama/cloud com degradação **visível**. Sem executar ações críticas. |
| E.9 | **Model card municipal** (hidro + ML) | P1 | M | Por município: DEM, nº eventos calibração, POD/FAR/CSI, limitações, validade. Reusar ideia de `write_model_card`; expor no catálogo / painel. |
| E.10 | **Blend leve com GloFAS** (além do % overlap) | P2 | M | Experimento: ponderar / mascarar mancha pluvial com hazard fluvial RP100 onde overlap for alto — marcado como Derivado/experimental. Não é assimilação bayesiana completa. |

**Entregável E:** motor com skill score publicado; assistente que cita ou se cala; simulações rastreáveis e comparáveis.

### Hipóteses prioritárias do catálogo (backlog de experimentos)

- SoilGrids reduz falsos positivos em áreas de alta infiltração?
- HAND melhora quais tipos de município (plano vs relevo)?
- GloFAS ajuda na validação de inundação *pluvial* ou só fluvial?
- Qual resolução DEM oferece melhor custo-benefício no piloto PE3D?
- Proxies SNIS de drenagem são plausíveis vs ausência de rede?

---

## 3. Horizonte F — Automação sentinela (lab, 2–6 semanas)

> Previsão baseada em impacto em escala de bairro/município — PoC interno, não operação 24/7 nacional.  
> Infra parcial já existe: `cemaden_monitor`, `monitoring_sync`, prewarm de simulações.

| # | Item | Prioridade | Esforço | Notas |
|---|------|-----------|---------|--------|
| F.1 | **Gatilho CEMADEN → simulação-padrão** (pilotos) | P0 | M | Quando alerta ativo cruza limiar do município/bacia, disparar RP/cenário padrão + empurrar resultado (painel/notificação interna). PoC EW4All municipal — não disseminação pública. |
| F.2 | **Pré-computação agendada de cenários RP** | P1 | M | Estender prewarm boot: lote noturno RP10/25/100 nos municípios onboarded prioritários; cache aquecido. |
| F.3 | **Modo sentinela pluviométrico** (refresh durante evento) | P2 | L | Depende de B.6 / série quase-contínua; refresh da simulação conforme acumulado. Só após F.1 estável. |
| F.4 | **Fila de avaliação pós-evento** (não retreino cego) | P2 | M | Evento observado → entra na fila de **avaliação** (skill scores E.2) e, com aprovação, calibração E.5. Retreino ML automático fica fora até lastro suficiente. |

**Entregável F:** alerta vivo gera impacto territorial pré-computado nos pilotos, com humano no loop.

---

## 4. Horizonte B — Confiança e dados oficiais (1–2 semanas)

> Fecha lacunas de lastro observacional (alinha Fase 21 do roadmap PLATEAU). Alimenta E.2/E.5/F.

| # | Item | Prioridade | Esforço | Fontes |
|---|------|-----------|---------|--------|
| B.1 | **Microdados INEP** por município (substituir OSM onde possível) | P0 | M | Cache `microdados_ed_basica_*.csv` / pipeline deposit |
| B.2 | **IDF oficial** além de Recife | P0 | M | Framework `backend/data/idf/`; coletar PE piloto; desbloqueia A.7 fora de Recife |
| B.3 | **Hidrografia ANA Ottocodificada** (além do OSM) | P1 | M | Roadmap 21d.2 — canais oficiais |
| B.4 | **Manchas oficiais** depositadas (mais municípios) | P1 | M | `manchas_oficiais` + IoU já existem; base dos golden events / CSI |
| B.5 | **Séries ANA HidroWeb / INMET BDMEP** (não só stub/CSV) | P1 | L | Tokens + materialização PostGIS |
| B.6 | **CEMADEN histórico 10 min** (quando captcha/CSV permitir) | P2 | L | Playbook de dados observados; desbloqueia F.3 |
| B.7 | **Cartas CPRM / setores de risco** | P1 | L | Proxy IRI hoje; oficial pendente |
| B.8 | **Pedologia Embrapa** (validar/corrigir SoilGrids pontual) | P2 | M | Solo municipal mais fiel que 1 ponto |

**Entregável B:** menos “Estimado”, mais “Oficial/Observado” nos selos do mapa.

---

## 5. Horizonte C — Gêmeo digital e experiência (2–6 semanas)

> Continuidade PLATEAU / UI 3D.

| # | Item | Prioridade | Esforço | Notas |
|---|------|-----------|---------|--------|
| C.1 | **LOD2 telhados** (MDS − MDT / mesh) na UI | P1 | L | Backend parcial; UI pausada (18b) |
| C.2 | **Viewer 3D Tiles** estável no mapa | P2 | M | Overlay retirado; reativar com cuidado |
| C.3 | **Alturas reais de edifício** (nDSM) nos pilotos PE3D | P0 | M | Camutanga/Itamaracá: só MDT hoje → heurística |
| C.4 | **Timeline de inundação** ligada ao mapa de forma óbvia | P1 | M | `flood_timeline` existe; UX ainda frágil |
| C.5 | **Exposição por edifício na UI** (não só meta/backend) | P1 | M | `building_exposure_service` já calcula |
| C.6 | **População por setor censitário × mancha** (camada) | P1 | M | IBGE já no sistema; falta camada/KPI espacial |
| C.7 | **Cenários what-if** mais ricos (telhado verde × ativos) | P2 | M | Mitigações existem; cruzar com ativos/vias |

**Entregável C:** gémeo que responde “quais prédios/pessoas/ativos” com clareza visual.

---

## 6. Horizonte D — Motor e paridade com referências maduras (mês+)

> O que 3Di / Jupiter / PLATEAU têm e o Sinidu **ainda não** deve prometer no curto prazo.  
> No lab: comparar adaptadores externos *só* com mandato e dados de rede — não desenvolver solver próprio.

| # | Item | Prioridade | Esforço | Referência |
|---|------|-----------|---------|------------|
| D.1 | **Hidrodinâmica 2D** (ou acoplamento SWMM/HEC-RAS/3Di) | P2 | XL | Adaptador experimental, não solver próprio |
| D.2 | **Inventário de galerias / microdrenagem** | P1 | L | Hoje: proxy SNIS; rede sintética só como experimento marcado Estimado |
| D.3 | **Ensembles climáticos / TRs multi-década** | P2 | L | Jupiter-like; distinto dos ensembles leves E.7 |
| D.4 | **Nowcasting radar** | — | — | **Fora de nicho** (CEMADEN); não competir |
| D.5 | **CityGML nacional padronizado** | P2 | XL | PLATEAU — governo + anos de dados |
| D.6 | **Calibração multi-evento densa** (POD/FAR/CSI estáveis) | P0 | L | Fase 21 — sucede E.2/E.5; skill estável entre eventos |

**Entregável D:** só avançar com mandato, dados de rede e tempo de calibração explícitos.

---

## 7. Ordem sugerida de execução

```text
Agora          →  A.1–A.4 polimento · A.7 atalhos RP
Em seguida     →  E.2 POD/FAR/CSI · E.8 RAG citação/abstenção · E.1 manifesto · E.3 gate
PoC automação  →  F.1 gatilho CEMADEN (pilotos) · F.2 prewarm RP agendado
Ciclo lab      →  E.4 comparador · E.7 ensemble · E.9 model card · B.1 INEP · B.2 IDF PE · C.3 nDSM
Aprofundar     →  E.5 calibração · E.10 blend GloFAS · F.3–F.4 · C.4–C.6 · B.3–B.5
Só com escopo  →  D.1–D.3 · E.6 model selector amplo · CAP/OGC se houver interlocutor federal
```

### Três primeiros passos de maior alavancagem (síntese)

1. **E.2** — POD/FAR/CSI contra S2ID/manchas nos pilotos (análise + pouco código; muda a frase sobre o motor).  
2. **E.8** — busca híbrida + citação obrigatória + recusa sem fonte (maior risco de assertividade do assistente).  
3. **F.1** — gatilho CEMADEN → simulação-padrão nos pilotos (PoC concreta de automação / impacto antecipado).

### Critério de pronto (por item)
- Dado aberto ou oficial **documentado** no catálogo (`layer_meta_registry` / fontes)
- Camada ou KPI **visível** no mapa ou painel (não só meta JSON)
- Teste mínimo (unitário ou smoke no piloto)
- Selo de qualidade honesto (`Oficial` / `Referencia` / `Derivado` / `Estimado`)
- Horizonte E: **reproduzível** (manifesto + métricas) e linguagem alinhada à maturidade
- Horizonte F: humano no loop; sem disseminação automática externa

---

## 8. Pilotos e dados bloqueantes

| Município | Bloqueio atual | Desbloqueio |
|---|---|---|
| Camutanga | Escolas: sem microdados INEP (OSM fallback) | Depositar CSV INEP ou sync automático no ensure |
| Camutanga / Itamaracá | Só MDT PE3D (sem MDS) → altura de prédio heurística | Baixar MDE/MDS PE3D quando portal permitir |
| Recife | IDF oficial ok; ML municipal ainda frágil em pontos | Densificar S2ID + séries; candidato #1 a golden / CSI e F.1 |
| Outros PE | Malha/vias OSM pobres no DB | Overpass on-demand (já usado em vias/hidro) |

---

## 9. Fora deste roadmap

- Competir com CEMADEN em radar/nowcast
- “3D pelo 3D” sem decisão de risco
- Garantir paridade com 3Di/Jupiter sem rede pluvial e séries densas
- STAC / OGC API Features / SensorThings como stack obrigatório (enriquecer meta basta no lab)
- CAP / TV 3.0 / integração CENAD como projeto agora (só reabrir se houver interlocutor federal concreto)
- Alta disponibilidade, K8s, disaster recovery e endurecimento multi-tenant de produção
- Agente autónomo que executa alertas ou ações de contingência (A5)
- Retreino ML contínuo sem aprovação / lastro observacional
- Detecção de deriva (drift) de modelo antes de skill scores estáveis
- Assimilação bayesiana completa GloFAS (E.10 é blend leve, não isso)
- Programa de conformidade PL 2338/2023 — aplicar princípios (HITL, auditoria, abstenção) sem abrir frente jurídica
- Mapeamento ISO cidades sustentáveis como entrega própria
- Solver hidrodinâmico próprio antes de adaptar/comparar solvers consolidados

---

## 10. Ligação com o roadmap PLATEAU

| Este doc | Roadmap PLATEAU |
|---|---|
| Horizonte A | UX / honestidade Fase 20 |
| Horizonte E | Fase **20** (confiança) + **21g** (validação/calibração) — viés lab + skill scores |
| Horizonte F | Monitoramento / ação antecipatória (lab) — não substituir CEMADEN |
| Horizonte B | Fase **21** (lastro observacional) |
| Horizonte C | Fases **17e–18b** (LOD2, exposição, viewer) |
| Horizonte D | Pós-21 / parceria modelagem física |

Atualizar este ficheiro ao fechar cada linha da tabela (✅ / 🔶 / ⏸), mantendo o PLATEAU como visão de longo prazo.
