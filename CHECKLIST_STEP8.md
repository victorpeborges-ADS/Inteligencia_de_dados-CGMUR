# CHECKLIST STEP 8 — Relatório PDF enriquecido com IA e visuais

## Tarefa 1 — Gráficos Python

- [x] `backend/app/reports/chart_generator.py`
- [x] `gerar_grafico_desastres()` — barras horizontais S2ID (laranja > R$1M)
- [x] `gerar_grafico_precipitacao()` — linha + barras mensais Open-Meteo
- [x] `gerar_grafico_score_radar()` — 5 eixos vs benchmark rede (61 municípios)
- [x] `gerar_mapa_estatico()` — PNG 1200×700 dark (map_screenshot_service)

## Tarefa 2 — Template HTML enriquecido

- [x] `municipal_report_completo.html` — 8 páginas MCID
- [x] Capa: logo, título, score círculo CSS, versão diagnóstico
- [x] Pág 2: narrativa IA (3 parágrafos) + box score/severidade
- [x] Pág 3: mapa vulnerabilidade + legenda
- [x] Pág 4: top 10 bairros + radar
- [x] Pág 5: gráficos desastres + precipitação + box totais
- [x] Pág 6: infraestrutura + maturidade + lacunas
- [x] Pág 7: plano de ação CURTO/MÉDIO/LONGO + casos referência
- [x] Pág 8: fontes + metodologia + disclaimer
- [x] Rodapé: página N de Total · Uso interno

## Tarefa 3 — Endpoint async

- [x] `POST /api/v1/reports/municipal/codigo/{ibge}/completo?async=true`
- [x] Job background: gráficos → narrativa → HTML → PDF
- [x] `GET /api/v1/reports/{job_id}/progresso`
- [x] Frontend: barra de progresso no ExecutiveDashboard

## Arquivos principais

| Área | Path |
|------|------|
| Gráficos | `backend/app/reports/chart_generator.py` |
| Serviço | `backend/app/services/report_completo_service.py` |
| Template | `backend/app/reports/templates/municipal_report_completo.html` |
| API | `backend/app/api/reports.py` |
| UI | `frontend/src/components/Dashboard/ExecutiveDashboard.tsx` |

## Testes

```bash
cd backend && python3 -m pytest tests/test_chart_generator.py -q --no-cov
```

## Smoke test (Recife 2611606)

1. Painel → **PDF Completo (IA + gráficos)**
2. Barra de progresso: gráficos → narrativa → HTML → PDF
3. Download automático ao concluir
4. PDF com **8+ páginas**, gráficos coloridos, mapa e narrativa IA

**Validado em 06/07/2026:**

| Métrica | Resultado |
|---------|-----------|
| Páginas | **11** (critério: ≥8) |
| Tamanho | **232 KB** (vs ~93 KB relatório básico) |
| Tempo sync | ~145 s |
| Job async | `043cd31a1274` → `completed`, report_id **139** |
| Gráficos | desastres ~0,4 s · precip ~1,7 s · radar ~12 s · mapa ~6,5 s |

> Em dev com `--reload`, jobs async podem ficar órfãos se o uvicorn reiniciar durante a geração. Em produção (sem reload) o fluxo completa normalmente.

## Critério de done

Relatório de Recife com 8+ páginas, gráficos coloridos, narrativa IA e mapa estático visível. **Atendido.**
