# CHECKLIST STEP 7 — Casos de Sucesso com Busca Semântica IA

## Tarefa 1 — Modelo de dados

- [x] Migration `016_casos_sucesso_semantic.sql` (schema enriquecido + `embedding vector(1024)`)
- [x] Modelo `CasoSucesso` expandido em `models.py`
- [x] Seed com **17 casos** verificáveis (MDR, MCID, PAC, municipais)
- [x] Boot aplica seed automaticamente se `< 17` casos

## Tarefa 2 — Embeddings e busca semântica

- [x] Embedding Mistral ao inserir/atualizar (`titulo + problema + solução`)
- [x] `POST /api/v1/cases/search` com `query`, `municipio_codigo`, `top_k`
- [x] Busca pgvector `ORDER BY embedding <=> query_embedding`
- [x] Filtros: `regiao`, `tipo_intervencao`, `faixa_populacao`, `programa_financiador`
- [x] Fallback TF-IDF se Mistral indisponível
- [x] `GET /api/v1/assistant/cases/search` mantido (delega ao serviço novo)

## Tarefa 3 — Integração Plano de Ação

- [x] `enrich_action_with_cases()` no `ActionPlanEngine`
- [x] Campo `casos_referencia` em cada ação
- [x] UI `ActionPlanPanel` exibe referências 📌

## Tarefa 4 — Frontend aba CASOS

- [x] Search bar semântica
- [x] Filtros: Região · Tipo · População · Programa
- [x] Grid de cards com resumo, resultado, programa
- [x] Modal detalhe + link fonte
- [x] Botão **Casos similares ao {município}**

## Tarefa 5 — Agente IA nos casos

- [x] Contexto `/casos` em `useAgenteContexto`
- [x] `POST /cases/{id}/adapt?codigo_ibge=` — adaptação Mistral
- [x] Modal: adaptação IA + botão abrir agente com pergunta sugerida

## Arquivos principais

| Área | Path |
|------|------|
| Serviço | `backend/app/services/casos_sucesso_service.py` |
| API | `backend/app/api/cases.py` |
| Migration | `backend/migrations/016_casos_sucesso_semantic.sql` |
| UI | `frontend/src/components/CaseStudies/CaseStudiesPanel.tsx` |
| Plano | `backend/app/services/action_plan_engine.py` |

## Testes

```bash
cd backend && python3 -m pytest tests/test_casos_sucesso.py -q --no-cov
```

## Smoke test

1. Aba **Casos** → buscar "alagamento baixa renda"
2. Filtrar região **Nordeste** · tipo **drenagem**
3. Clicar card → modal + adaptação para município selecionado
4. Painel → gerar Plano de Ação → ver 📌 Referência nas ações

## Critério de done

Base de conhecimento funcional com busca semântica Mistral, integração ao plano de ação e adaptação IA por município.
