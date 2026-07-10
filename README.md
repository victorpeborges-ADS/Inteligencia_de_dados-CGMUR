# Inteligência de Dados — CGMUR (Sinidu+Clima)

Plataforma nacional de inteligência territorial para diagnóstico climático, simulação de cenários, contingência e apoio à decisão municipal — desenvolvida no âmbito do MCID/CGMUR.

## Stack

| Camada | Tecnologia |
|--------|------------|
| Frontend | Next.js 13, Leaflet (2D), MapLibre GL 4.7 (3D), Tailwind, Recharts |
| Backend | FastAPI, SQLAlchemy |
| Banco | PostGIS + pgvector |
| Infra | Docker Compose, Redis, Ollama, OSRM (opcional) |

## Início rápido

```bash
docker compose up -d db backend frontend
```

- API: http://localhost:8000/docs  
- Frontend: http://localhost:3000  

## Funcionalidades

### Território e análise

- **61 municípios prioritários** com onboarding sob demanda (malhas IBGE, setores censitários e integrações)
- Índices **IVC**, **IRI** e **Score Sinidu+Clima** por bairro e município
- Painel executivo com KPIs, badges de qualidade de dado (Oficial / Derivado / Lacuna) e narrativa territorial
- **Comparador** entre municípios (tabela, radar, IA, export PDF)
- **Apresentação executiva** em 8 slides por município (`/apresentacao/{ibge}`)
- Catálogo nacional de dados com **maturidade** por fonte e ranking dos prioritários

### Mapa e camadas

- Mapa **2D** (Leaflet) e **3D** (MapLibre + DEM + extrusão de manchas)
- Camadas: bairros, vulnerabilidade, S2ID, MapBiomas, saneamento, socioeconômico, Censo 2022, educação INEP, LST observada, territórios especiais, geoportal municipal (CTM)
- Seletor de **ano por tema**, contexto **regional** (mesorregião/RM) e painel de camadas ativas
- Referência externa **GeoReDUS** quando o dado local não está integrado

### Simulações climáticas

- **Chuva extrema** (hidrologia + DEM, cache Redis, jobs async, compare 80→120 mm)
- **Ilha de calor** v1.1 (temperatura + uso do solo; slider bidirecional de vegetação)
- **Impermeabilização**, perda/ganho de vegetação, déficit de drenagem
- Interpretação por IA, plano de mitigação e **modo 3D automático** após simulação
- Comparador **LST observada × simulada** (GeoReDUS)

### Contingência e monitoramento

- Planos de contingência alinhados ao **COBRADE** (zonas, rotas, pontos de apoio)
- Rotas de evacuação com **OSRM** (perfil `pe-se` para Recife/Aracaju) ou fallback geodésico
- Monitor de alertas CEMADEN, histórico S2ID e wizard de ativação de plano

### Inteligência artificial

- **Assistente municipal** com RAG (Ollama local + Mistral/Gemini opcionais)
- **Agente contextual** por página (painel, simulações, catálogo) com prewarm e cache
- Motor de **recomendações territoriais** e agente proativo na interface

### Relatórios e operação

- Diagnóstico executivo, relatório PDF municipal (8+ páginas com gráficos e IA)
- Export **SEI** (PDF + metadados + hash SHA-256)
- Painel **Sistema** (`/sistema`): saúde, jobs em background, pipeline MCID, homologação 62/62
- Auth JWT, multi-tenant por UF/IBGE, OIDC Keycloak/gov.br, auditoria de ações

### Piloto e validação

- Boot prioritário **Recife** (`2611606`) e **Aracaju** (`2800308`)
- Scripts: `validacao_recife_ui.py`, `validacao_piloto_demo.py`, `validacao_osrm.py`, `demo-smoke.sh`

## Documentação

### Referência principal

| Documento | Conteúdo |
|-----------|----------|
| [Documentação técnica completa](documentacao/DOCUMENTACAO_TECNICA_COMPLETA.md) | Arquitetura, API, metodologia, integrações, Fases 15–16 |
| [Roadmap](ROADMAP.md) | Fases 1–16, backlog priorizado e decisões técnicas |
| [Deploy](deploy/README.md) | Staging, homologação TLS, OIDC, proxy e certificados |

### Planejamento e homologação

| Documento | Conteúdo |
|-----------|----------|
| [Resumo execução 5 passos](RESUMO_EXECUCAO_5_PASSOS.md) | Validação Recife, batch 62/62, onboarding, homologação MCID |
| [Plano lacunas institucionais](PLANO_LACUNAS_INSTITUCIONAIS.md) | GeoSGB, Brasil MAIS, SIRENE, AdaptaBrasil, convênios |
| [Checklist demo MCID](CHECKLIST_DEMO_MCID.md) | Roteiro de demonstração institucional |
| [OSRM — roteamento local](docker/osrm/README.md) | Perfil `pe-se`, nordeste completo e `scripts/osrm-enable.sh` |
| [Checklist OIDC gov.br](CHECKLIST_OIDC_GOVBR.md) | Migração D.2 Keycloak → gov.br produção |

### Checklists por fase

| Documento | Tema |
|-----------|------|
| `CHECKLIST_FASE_12.md` | Cache Redis, simulação async, progresso UI |
| `CHECKLIST_FASE_13.md` | UX institucional, design system, modo focus |
| `CHECKLIST_FASE_14.md` | Lacunas institucionais, validação Recife |
| `CHECKLIST_FASE_A_3D.md` | Simulação 3D MapLibre, inspeção por clique |
| `CHECKLIST_STEP8.md` | PDF enriquecido (8+ páginas) |
| `CHECKLIST_STEP9.md` | Polimento UX e Central da Oficina |

### Simulação 3D (guia rápido)

1. Abra **Simulações** → cenário **Chuva** (ex.: 120 mm) → **Rodar Simulação**
2. O mapa alterna automaticamente para **Terreno 3D**
3. Clique numa mancha para ver profundidade (cm), cota do solo e cota da água (DEM SRTM 30 m)

Piloto com LiDAR local: Recife (`2611606`). Com prewarm + cache, simulação de 120 mm tipicamente em ~4 s.

## Repositório

Código-fonte do MVP Sinidu+Clima — Fases 1–16 + operação demo Recife/Aracaju (jul/2026).
