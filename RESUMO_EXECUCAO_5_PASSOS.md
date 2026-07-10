# Execução dos 5 Passos — jul/2026

## Passo 1 — Validação UI Recife ✅

| Check | Resultado |
|-------|-----------|
| Malha/badges | OK — malha disponível |
| Apresentação 8 slides | OK |
| Catálogo ~61% maturidade | OK |
| Agente contextual (pergunta simples) | OK — ~3s com cache / bundle leve |
| Contexto assistente (`GET .../context`) | OK — prewarm boot + cache Redis (~instantâneo na 2ª chamada) |
| Simulação 120mm | OK — ~4s com prewarm + cache Redis |
| OSRM contingência (pe-se) | OK — rotas reais PE/SE (`scripts/validacao_osrm.py`) |

Script: `python3 scripts/validacao_recife_ui.py`

Melhorias aplicadas: prewarm pluvial no boot/troca de município, agente sem `executive_snapshot`, malha priorizada no mapa, contexto municipal em cache (sem `executive_snapshot`).

---

## Passo 2 — Diagnostics-batch + PDFs (62) ✅

- **62/62** municípios com diagnóstico executivo
- **62/62** com pelo menos um PDF municipal
- Painel **Sistema → Homologação** exibe cobertura e botão **Gerar PDFs pendentes**
- Jobs zumbis expiram após 6h (`STALE_JOB_HOURS`)

Últimos gaps fechados: Londrina (`4113700`) diagnóstico + PDF; São Luiz Gonzaga (`4318903`) PDF.

---

## Passo 3 — Onboarding 61/61 ✅

- Banco: **61/61 concluído** (seed prioritários)
- Auditoria: confiabilidade ALTA nos prioritários de boot (Recife, Aracaju)

---

## Passo 4 — Lacunas institucionais ✅

Documento: **`PLANO_LACUNAS_INSTITUCIONAIS.md`**

Prioridades: GeoSGB/CPRM → Brasil MAIS → SIRENE → AdaptaBrasil → SINTER

---

## Passo 5 — Homologação MCID ✅

- `.env.homolog` com `AUTH_ENABLED=true`, `MULTI_TENANT_ENABLED=true`
- Stack: `./scripts/homolog-up.sh .env.homolog`
- HTTPS: `curl -sk https://localhost/health/ready` → OK

| URL | Uso |
|-----|-----|
| https://localhost | App prod + TLS |
| https://localhost/api/v1/ | API (auth obrigatória) |
| http://localhost:8080 | Keycloak (admin/admin) |

---

## Próximo no roadmap

| Prioridade | Item |
|------------|------|
| P2 | Commit/versionar trabalho Fase 15 ainda fora do git |
| P3 | gov.br OIDC produção (D.2) |
| P3 | Integrações institucionais A.1–A.6 (convênios) |
