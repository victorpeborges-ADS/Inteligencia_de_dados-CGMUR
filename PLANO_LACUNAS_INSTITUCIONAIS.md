# Plano de Lacunas Institucionais — Sinidu+Clima

**Atualizado:** jul/2026 · **Escopo:** 61 municípios prioritários

Este plano cobre fontes que **não se resolvem só com ETL técnico** — exigem convênio, credencial ou API institucional. O catálogo ativo já calcula impacto e explica lacunas via IA.

---

## Ranking por impacto (nacional)

| # | Fonte | Municípios afetados | Impacto Score | Dificuldade | Responsável sugerido |
|---|-------|---------------------|---------------|-------------|----------------------|
| 1 | **GeoSGB / CPRM** | 61 | ±8 pts | Convênio | MCID ↔ CPRM |
| 2 | **Brasil MAIS** | 61 | ±5 pts | Técnica + MCID | Secretaria Nacional de Habitação |
| 3 | **SIRENE / MCTI** | 10+ | ±4 pts | Institucional | MCID ↔ MCTI |
| 4 | **AdaptaBrasil / INPE** | parcial | ±3 pts | Técnica | INPE (proxy MapBiomas ativo) |
| 5 | **SINTER / Receita** | parcial | ±2 pts | Institucional | Receita Federal |

---

## Ações por fonte

### GeoSGB / CPRM (prioridade 1)
- **O que falta:** litologia, susceptibilidade geológica, aptidão do solo.
- **Impacto:** subestima risco em solos argilosos e áreas de recalque (IVC).
- **Ação:** iniciar trâmite convênio MCID–CPRM para acesso GeoSGB ou WMS institucional.
- **Prazo estimado:** 6 meses · **Status catálogo:** Em integração / Ausente.

### Brasil MAIS (prioridade 2)
- **O que falta:** índices de monitoramento territorial MCID.
- **Ação:** integração via API interna MCID ou carga batch acordada com equipe Brasil MAIS.
- **Prazo estimado:** 2–3 meses · **ETL:** `external_sources_collector` pronto.

### SIRENE / MCTI (prioridade 3)
- **O que falta:** emissões antrópicas por município.
- **Ação:** solicitar credencial ou extract anual via convênio MCTI.
- **Prazo estimado:** 4 meses.

### AdaptaBrasil (prioridade 4 — mitigado)
- **Situação:** proxy MapBiomas + estimativa ativa; status **Estimado** na maioria.
- **Ação:** credencial API INPE quando disponível; substituir proxy.

### SINTER / Receita (prioridade 5)
- **Situação:** cadastro territorial; status **Estimado** via SICONFI/IBGE.
- **Ação:** avaliar necessidade real vs. dados IBGE já integrados.

---

## O que o Sinidu já faz sem convênio

- Explica impacto por lacuna (`GET /data-catalog/impact-analysis/{ibge}/{fonte}`)
- Ranking de lacunas no painel Catálogo
- Projeção de maturidade se top 2 fontes forem integradas
- Sync batch de fontes externas quando dados existem: `POST /system/jobs/fontes-externas-batch`
- Import batch CTM/geoportal (24 municípios BAIXA/MÉDIA): `POST /system/jobs/ctm-batch`

---

## Métricas de acompanhamento

| Métrica | Baseline jul/2026 | Meta |
|---------|-------------------|------|
| Maturidade média nacional | 77% | 84% (+ GeoSGB + Brasil MAIS) |
| Municípios confiabilidade ALTA | 61/61 | manter |
| Fontes Integrado (GeoSGB) | 0 | 61 |
| Fontes Integrado (Brasil MAIS) | 0 | 61 |

---

## Próximo passo institucional

1. Encaminhar minuta de convênio MCID–CPRM (GeoSGB) — template SEI interno.
2. Abrir chamado MCID Brasil MAIS para API ou dump mensal.
3. Após convênio: `POST /api/v1/data-catalog/refresh-source/{ibge}/geosgb` por município piloto (Recife).
