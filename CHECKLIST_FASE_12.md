# CHECKLIST FASE 12 — Performance e UX da simulação

**Atualizado:** jul/2026

## Step 1 — Cache Redis + compare paralelo

- [x] `simulation_cache.py` — chave `(ibge, mm, model_version)`
- [x] Compare executa baseline + cenário em paralelo (`ThreadPoolExecutor`)
- [x] Endpoints sync usam cache (`from_cache` na resposta)
- [x] `SIMULATION_CACHE_TTL` / `SIMULATION_CACHE_ENABLED` via env
- [x] Testes `test_simulation_cache.py`

## Step 2 — Job async + polling

- [x] `POST /simulations/extreme-rainfall/async`
- [x] `POST /simulations/extreme-rainfall/compare/async`
- [x] `GET /simulations/jobs/{job_id}` — progresso e resultado
- [x] `simulation_job_service.py`

## Step 3 — UI progresso real

- [x] `SimulationPanel` usa async por padrão na aba Chuva
- [x] Barra de progresso + `stage_label`
- [x] Badge `cache` quando `from_cache`

## Step 4 — Polimento 3D

- [x] Legenda faixas de profundidade no painel 3D

## Step 5 — Comparação municípios

- [x] `CompareModal` sugere par da mesma UF

## Step 6 — Testes

- [x] Backend: cache + delta compare
- [x] Script manual: `npx tsx frontend/scripts/test-floodInspect.ts`

## Step 7 — Documentação

- [x] `ROADMAP.md` Fase 12
- [x] Este checklist

## Smoke test

```bash
# 1ª execução (~60 s)
curl -X POST http://localhost:8000/api/v1/simulations/extreme-rainfall/compare \
  -H 'Content-Type: application/json' \
  -d '{"codigo_ibge":"2611606","scenario_mm":120,"baseline_mm":80}'

# 2ª execução (cache, <1 s)
# repetir comando — "from_cache": true

# Async
curl -X POST http://localhost:8000/api/v1/simulations/extreme-rainfall/compare/async \
  -H 'Content-Type: application/json' \
  -d '{"codigo_ibge":"2611606","scenario_mm":120,"baseline_mm":80}'
# → job_id → GET /api/v1/simulations/jobs/{job_id}
```

Frontend: Simulações → Chuva 120 mm → barra de progresso → 2ª rodada instantânea.

## Pendente (Fase 12b)

- [x] OSRM Nordeste na demo de contingência — banner status + instruções setup
- [x] Testes unitários frontend (`floodInspect.ts`) — `npm run test:floodInspect`
- [x] Cache interpretação IA pós-simulação — `simulation_interpret_cache.py`
- [x] Pré-aquecimento DEM ao abrir aba Simulações — badge "DEM aquecido"
- [x] CI: `test_simulation_interpret_cache` + `npm run test:floodInspect`
- [x] Env cache no `docker-compose.yml`
