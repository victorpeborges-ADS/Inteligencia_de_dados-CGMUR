# CHECKLIST STEP 9 — Polimento UX e apresentabilidade

## Tarefa 1 — Loading states

- [x] `RotatingLoader.tsx` — mensagens rotativas (3s)
- [x] PDF diagnóstico / relatório — mensagens CEMADEN, Score, narrativa
- [x] Simulação pluvial — slider solta → simula + shimmer mapa + mensagens `{mm}mm`
- [x] Interpretação IA — "🤖 Analisando resultado da simulação…"
- [x] Apresentação — "Preparando apresentação…"
- [x] Recarga município — `MunicipioLoadProgress` com steps visíveis

## Tarefa 2 — Banner onboarding

- [x] `OnboardingBanner.tsx` — exibido no Painel quando `onboarding_status != concluido`
- [x] Steps: Malha IBGE · MapBiomas · Score inicial
- [x] Polling a cada 15s até concluir

## Tarefa 3 — Tooltips técnicos

- [x] `TermTooltip.tsx` + glossário IVC, IRI, Score, CAPAG, COBRADE, DEM, SRTM, S2ID
- [x] Integrado no Painel (CAPAG, IVC/IRI) e Simulação (SRTM)

## Tarefa 4 — Central da Oficina

- [x] `WorkshopCenter.tsx` — componente dedicado
- [x] DIAGNÓSTICO → "Rediagnosticar" se gerado hoje + tooltip hora
- [x] APRESENTAR → `/apresentacao/{ibge}` + loading
- [x] RELATÓRIO → dropdown rápido / completo (8 págs)
- [x] COMPARAR → abre modal

## Tarefa 5 — Comparação de municípios

- [x] `CompareModal.tsx` — selector 2º município
- [x] Tabela Score, IVC, IRI, CAPAG, alertas, maturidade
- [x] Radar sobreposto (Recharts)
- [x] Narrativa IA (`compareMonitoringMunicipalities`)
- [x] Export comparação PDF (print HTML)

## Tarefa 6 — Trilha de auditoria

- [x] `diagnostic.generate` / `download_pdf` / `presentation.view`
- [x] `action_plan.generate`
- [x] `onboarding.ensure` / `onboarding.run`
- [x] `compare.analytics` / `compare.monitoring`
- [x] `AuditPanel` — labels expandidos + filtro IBGE

## Arquivos principais

| Área | Path |
|------|------|
| Loading | `frontend/src/components/UI/RotatingLoader.tsx` |
| Tooltips | `frontend/src/components/UI/TermTooltip.tsx` |
| Onboarding UX | `frontend/src/components/Onboarding/OnboardingBanner.tsx` |
| Oficina | `frontend/src/components/Workshop/WorkshopCenter.tsx` |
| Comparação | `frontend/src/components/Compare/CompareModal.tsx` |
| Auditoria UI | `frontend/src/components/Audit/AuditPanel.tsx` |
| Audit API | `backend/app/api/diagnostic.py`, `onboarding.py`, `monitoring.py` |

## Smoke test

1. Selecionar município não concluído → banner onboarding no Painel
2. Central da Oficina → Comparar → modal com IA e radar
3. Simulação chuva → soltar slider → loading + shimmer no mapa
4. Gerar diagnóstico → mensagens rotativas
5. Aba Auditoria (admin) → registros após PDF/diagnóstico/comparação

## Critério de done

Demonstração fluida com feedback visual em todas operações pesadas, tooltips nos termos técnicos, Central da Oficina polida e trilha de auditoria populada automaticamente.

Ver também: **Fase A 3D** em `CHECKLIST_FASE_A_3D.md` e **Fase 11** em `ROADMAP.md`.
