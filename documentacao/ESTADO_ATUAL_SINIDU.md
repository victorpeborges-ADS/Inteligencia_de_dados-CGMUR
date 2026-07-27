# Estado atual — Sinidu+Clima

Documento vivo (Fase 20a.4 / 20h.7). Resume o que o produto **é** e **não é**.

## Honestidade metodológica (teto de acurácia)

| Camada | Papel | Teto |
|--------|-------|------|
| Simulação pluvial / calor / asfalto / drenagem | Triagem territorial | **Não** é HEC-RAS, SWMM, laudo nem alerta CEMADEN |
| Score / semáforo | Consolidação Score×IVC×IRI×alerta×ML | Apoia priorização; não substitui Defesa Civil |
| Predição ML | Só `model_kind=full` = probabilidade; senão heurística | Exige lastro observacional (Fase 21) |
| LST GeoReDUS | Observado (satélite) | Separado do cenário Sinidu (Derivado) |
| Entradas IBGE/S2ID/CEMADEN/MapBiomas | Oficiais quando `data_quality=oficial` | Qualidade da **fonte**, não do modelo |

Detalhe técnico: `DOCUMENTACAO_TECNICA_COMPLETA.md` §18 e §18.1 (teto).  
Checklist de linguagem: `docs/CHECKLIST_LINGUAGEM_HONESTIDADE.md`.  
Nota publicável: `POST /api/v1/simulations/method-note` + painel de limites na aba Simulações.

## Stack (resumo)

- Backend FastAPI + PostGIS · Frontend Next.js · Docker Compose
- Pilotos: 6 municípios (`TARGET_MUNICIPALITIES`)
- IA: agente contextual + RAG (Mistral); MCP = ferramenta de equipe, não runtime do painel

## Status das fases ativas

| Fase | Status |
|------|--------|
| 17–18 | Quase fechadas / fechadas no roadmap plateau |
| **19** | **100%** (MapBiomas oficial dos pilotos) |
| **20** | Em curso (~79%) — 20a–20c + 20e + 20f.3/5/6 + 20h (exc. dado externo); restam 20f.1/2/4 |
| **21** | ~78% — núcleo ML; faltam dados externos + modelo por bairro |

## Falhas / lacunas conhecidas

- IDF municipal oficial (20h.4) e manchas CPRM (20h.5) — dado externo
- Auth endurecida / testes HTTP (20a) — **feito** (policy gate `confirm=true`; smoke HTTP)
- Modelos ML `full` dependem de retreino + S2ID nacional CSV
- LOD1/2 edificações — pausado (qualidade insuficiente)
- MCP equipe (20c) ✅ — `docs/MCP_EQUIPE.md`
- Playbook multi-máquina (20f.3) ✅ — `docs/PLAYBOOK_MULTI_MAQUINA.md`
- Agente Sinidu unificado (20b) ✅ · Selo único de previsão + KMZ pacote (20e) ✅

Atualizar este arquivo ao fechar itens P0 da Fase 20.
