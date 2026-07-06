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

## Prompts 05–10 (pendentes)

- [ ] 05 — Estados vazios e skeletons
- [ ] 06 — Wizard pós-simulação (ir ao 3D, exportar)
- [ ] 07 — Narrativa executiva no painel
- [ ] 08 — Motor de recomendações *(adiado)*
- [ ] 09 — Onboarding contextual por aba
- [ ] 10 — Comparador territorial enriquecido

## Já implementado (marcar como referência)

- [x] 11 — Apresentação `/apresentacao/{ibge}`
- [x] 12 — `AuditPanel`
- [x] 13 — `AgenteSinidu` contextual
- [x] 14 — `TermTooltip`

## Adiado

- [ ] 15 — Remover rótulos "MVP" / "INTERNO" — pós-homologação MCID

## Smoke test Modo Focus

1. Abrir `http://localhost:3000/painel` (Recife)
2. Pressionar **F** — sidebar some, mapa ocupa tela
3. `WorkshopCenter` permanece visível sobre o mapa
4. Clicar "Modo Focus" ou **F** novamente — layout normal
5. Recarregar página — preferência restaurada do `localStorage`

## Dependências

- Concluir **Fase 12b** (OSRM, testes frontend) antes de prompts 05–10 em produção
- Fase 13 não bloqueia deploy técnico; melhora percepção em oficina/sala de situação
