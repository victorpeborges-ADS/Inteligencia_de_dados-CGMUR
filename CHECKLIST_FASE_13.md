# CHECKLIST FASE 13 — Experiência institucional (UX/UI)

**Origem:** plano de melhoria Sinidu 06/07 (15 prompts + Fase 0)  
**Atualizado:** jul/2026  
**Escopo:** frontend-only — sem alterar contratos de API

## Fase 0 — Design System

- [x] Tokens `colors`, `spacing`, `layout`, `typography`, `elevation`, `radius`
- [x] Barrel export `frontend/src/design-system/index.ts`
- [x] `tailwind.config.js` inclui pasta `design-system`
- [x] Componentes base (`KpiCard`, `PanelSection`, `Badge`)
- [ ] Storybook ou página `/design-system` — opcional

## Prompt 04 — Modo Focus

- [x] Estado `focusMode` em `useAppStore`
- [x] Persistência `localStorage` (`sinidu-focus-mode`)
- [x] Tecla **F** alterna modo (ignora inputs)
- [x] Botão "Modo Focus" no header
- [x] Sidebar esquerda recolhida (`w-0`, overflow hidden)
- [x] Overlay de camadas oculto
- [x] Painel socioeconômico / legenda lateral ocultos
- [x] Header compacto
- [x] `WorkshopCenter` e toggle 2D/3D mantidos
- [x] Transições `duration-300`

## Prompt 02 — Hierarquia visual

- [x] Tipografia e peso consistentes nos painéis (`PanelSection`, `KpiCard`)
- [x] KPIs primários vs secundários no `ExecutiveDashboard`
- [x] Reduzir competição visual sidebar × mapa (sidebar mais suave, mapa com ring)

## Prompt 03 — Sidebar de camadas

- [x] `LayerPanel.tsx` — painel colapsável com persistência localStorage
- [x] Ícones por grupo (Base, Clima, Planejamento, Saúde…)
- [x] Preset `LAYER_PRESETS.cruzarRiscos` documentado

## Prompt 05 — Estados vazios e skeletons

- [x] `EmptyState` e `Skeleton` / `SkeletonKpiGrid` / `SkeletonChart`
- [x] `SimulationPanel` — estado vazio antes da 1ª simulação
- [x] `ExecutiveDashboard` — skeletons no carregamento
- [x] `MonitoringPanel` — timeline sem alertas

## Prompt 06 — Wizard pós-simulação

- [x] `SimulationNextSteps` — 3D, Modo Focus, Cruzar riscos, PDF
- [x] Integração em `PlatformApp` + `SimulationPanel`
- [x] Detecção automática de cenário volumétrico (água/calor)

## Prompt 07 — Narrativa executiva

- [x] `buildExecutiveNarrative()` — IA salva ou síntese automática
- [x] `ExecutiveNarrative` no painel (antes dos KPIs)
- [x] Bullets de próximas ações sugeridas

## Prompt 09 — Onboarding contextual por aba

- [x] `TAB_CONTEXT_HINTS` em `tabContextHints.ts`
- [x] `TabContextHint` dismissível (`localStorage` por aba)
- [x] CTAs entre abas (ex.: Simulações → Contingência)

## Prompt 10 — Comparador territorial

- [x] `compareMunicipalities.ts` — presets, deltas, bullets
- [x] Pares sugeridos (mesma UF, porte similar, referência regional)
- [x] Coluna Δ / melhor na tabela
- [x] Veredicto `mais_critico_ibge` + síntese em bullets
- [x] População no seletor e na tabela

## Prompt 08 — Motor de recomendações

- [x] `territorialRecommendations.ts` — regras explicáveis (IVC, IRI, CEMADEN, maturidade, CAPAG…)
- [x] `TerritorialRecommendations` no painel executivo (top 5, prioridade, evidências)
- [x] CTAs entre abas (simulações, monitor, contingência, catálogo…)
- [x] `npm run test:territorialRecommendations`

## Adiado / pendente

- [ ] *(nenhum item crítico da Fase 13)*

## Já implementado (marcar como referência)

- [x] 11 — Apresentação `/apresentacao/{ibge}`
- [x] 12 — `AuditPanel`
- [x] 13 — `AgenteSinidu` contextual
- [x] 14 — `TermTooltip`

## Adiado

- [x] 15 — Rótulos "INTERNO" — `NEXT_PUBLIC_INSTITUTIONAL_MODE=true` (homolog/prod); dev mantém badge

## Smoke test Modo Focus

1. Abrir `http://localhost:3000/painel` (Recife)
2. Pressionar **F** — sidebar some, mapa ocupa tela
3. `WorkshopCenter` permanece visível sobre o mapa
4. Clicar "Modo Focus" ou **F** novamente — layout normal
5. Recarregar página — preferência restaurada do `localStorage`

## Dependências

- Concluir **Fase 12b** (OSRM, testes frontend) antes de prompts 05–10 em produção
- Fase 13 não bloqueia deploy técnico; melhora percepção em oficina/sala de situação
