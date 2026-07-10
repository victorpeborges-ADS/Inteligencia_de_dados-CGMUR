# CHECKLIST FASE 14 — Lacunas institucionais e operação demo

**Atualizado:** jul/2026  
**Escopo:** UX catálogo + operação MCID pós-Fase 13

## 14.1 — Trâmite institucional no catálogo

- [x] `institutionalGaps.ts` — ranking GeoSGB → Brasil MAIS → SIRENE → AdaptaBrasil → SINTER
- [x] `InstitutionalGapsPanel` na aba **Catálogo** com status do catálogo + botão Impacto IA
- [x] Referência `PLANO_LACUNAS_INSTITUCIONAIS.md`

## 14.2 — Design System (Fase 13 opcional)

- [x] Página `/design-system` — tokens, badges, KPIs, empty/skeleton

## 14.3 — Validação operacional

- [x] `scripts/validacao_recife_ui.py` — agente, simulação, apresentação (IBGE parametrizável)
- [x] `scripts/validacao_piloto_demo.py` — Recife + Aracaju
- [x] `scripts/validacao_osrm.py` — rotas reais na contingência
- [x] `demo-smoke.sh` — `RUN_PILOTO_VALIDATION=1`, `RUN_OSRM_VALIDATION=1`

## Smoke test

```bash
# Catálogo — bloco violeta "Trâmite institucional"
open http://localhost:3000/catalogo

# Design system
open http://localhost:3000/design-system

# Demo completa (API)
./scripts/demo-smoke.sh

# Validação piloto dupla (~5 min)
RUN_PILOTO_VALIDATION=1 ./scripts/demo-smoke.sh

# Homologação OIDC/TLS
./scripts/validacao_oidc_govbr.sh https://localhost
```

## Critério de done

- Gestor vê lacunas institucionais com responsável/prazo e aciona análise IA por fonte
- Equipe MCID tem roteiro único de smoke test pré-oficina
