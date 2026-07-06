# CHECKLIST STEP 6 — Monitor com IA e alertas proativos

## Tarefa 1 — Card Análise de Cenário

- [x] `GET /api/v1/monitoring/scenario-analysis/{codigo_ibge}`
- [x] Cache 30 min + `?force=true` para recalcular
- [x] Mistral + fallback determinístico
- [x] Card no `MonitoringPanel` após KPIs
- [x] Botão **Recalcular**
- [x] Campos: interpretação, tendência, recomendações, referência histórica

## Tarefa 2 — Alerta antecipado (WebSocket)

- [x] Evento `PROACTIVE_RISK` nos limiares 30% / 50% / 75%
- [x] >30%: mensagem proativa no agente IA
- [x] >50%: badge LARANJA pulsa + agente recomenda Contingência
- [x] >75%: popup crítico + botão Ativar Plano

## Tarefa 3 — Comparação entre municípios

- [x] Mini-card flutuante ao clicar no mapa nacional
- [x] `GET /api/v1/monitoring/compare/{codigo_a}/{codigo_b}`
- [x] Botão **Comparar com {município atual}**
- [x] Painel lateral com comparação IA

## Tarefa 4 — Timeline enriquecida

- [x] Ícones por tipo (chuva / vento / deslizamento)
- [x] Clique expande interpretação IA (`GET /alert-interpretation/{codigo}/{id}`)
- [x] Agrupamento `timeline_grouped` no dashboard

## Arquivos principais

| Área | Path |
|------|------|
| Serviço IA | `backend/app/services/scenario_analysis_service.py` |
| API | `backend/app/api/monitoring.py` |
| WS limiares | `backend/app/services/weather_monitor.py` |
| UI | `frontend/src/components/Monitoring/MonitoringPanel.tsx` |
| API client | `frontend/src/utils/api.ts` |

## Testes

```bash
cd backend && python3 -m pytest tests/test_scenario_analysis.py -q --no-cov
```

## Smoke test (Recife 2611606)

1. Aba **Monitor** → KPIs AMARELO · 15%
2. Card **Análise de cenário** com recomendações AMARELO
3. Timeline agrupada → clique expande interpretação
4. Mapa → clique em outro município → **Comparar com Recife**
5. (Simular) WS `PROACTIVE_RISK` tier ORANGE → badge pulsa

## Critério de done

Monitor interpreta cenário meteorológico com IA, alertas proativos proporcionais ao risco e comparação entre municípios.
