# CHECKLIST STEP 5 — Catálogo de Dados com IA e Ações Diretas

## Tarefa 1 — Botões de ação por fonte

- [x] **INTEGRADO:** ↻ Atualizar agora + Ver dados (modal preview)
- [x] **INTEGRADO:** texto "Última sync · N registros"
- [x] **ESTIMADO:** Como melhorar? + impacto confiabilidade
- [x] **EM INTEGRAÇÃO:** Ver progresso + texto convênio institucional
- [x] **AUSENTE:** Entender impacto + "O que falta: {requisito}"

## Tarefa 2 — Análise de impacto (Mistral)

- [x] `GET /api/v1/data-catalog/impact-analysis/{codigo}/{fonte_id}`
- [x] Campos: campos_score, impacto_score_estimado, dificuldade, explicacao_ia
- [x] Fallback determinístico sem Mistral

## Tarefa 3 — Ranking de lacunas

- [x] Tabela "Lacunas prioritárias — por impacto no Score"
- [x] Colunas: #, Fonte, Impacto est., Dificuldade
- [x] Ordenação por impacto_score_pts

## Tarefa 4 — Widget maturidade

- [x] Radar 6 eixos (IBGE, Clima, Fiscal, Geoespacial, Riscos, Institucional)
- [x] Linha temporal mês anterior → atual (+Δ%)
- [x] Projeção se integrar top 2 lacunas
- [x] Explicação IA da maturidade

## Tarefa 5 — Atualizar Tudo

- [x] `POST /api/v1/data-catalog/refresh-all/{codigo}` → job_id
- [x] `GET /api/v1/data-catalog/refresh-job/{job_id}` polling
- [x] Apenas fontes **Integrado** com ETL
- [x] Progresso: "3/8 fontes · CEMADEN: OK · …"

## Endpoints adicionais

- [x] `GET /source-preview/{codigo}/{fonte_id}` — últimos 5 registros
- [x] `POST /refresh-source/{codigo}/{fonte_id}` — ETL unitário

## Arquivos principais

| Área | Path |
|------|------|
| API | `backend/app/api/data_catalog.py` |
| Cobertura | `backend/app/services/catalog_coverage.py` |
| Impacto IA | `backend/app/services/catalog_impact_service.py` |
| Sync/ETL | `backend/app/services/catalog_sync_service.py` |
| Registry | `backend/app/services/catalog_source_registry.py` |
| Jobs | `backend/app/services/background_jobs.py` |
| UI | `frontend/src/components/DataCatalog/DataCatalogPanel.tsx` |
| Client | `frontend/src/utils/api.ts` |

## Testes

```bash
cd backend && python3 -m pytest tests/test_catalog_impact.py -q --no-cov
```

## Smoke test (Recife 2611606)

1. Aba **Catálogo** → badge Alta · ~77%
2. Card MapBiomas → **Ver dados** abre modal
3. Card GeoSGB → **Entender impacto** explica lacuna
4. Tabela lacunas com GeoSGB/SIRENE no topo
5. **Atualizar Tudo** mostra progresso por fonte

## Critério de done

Catálogo passivo transformado em painel ativo com ações, IA explicativa e job de recarga visível.
