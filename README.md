# Inteligência de Dados — CGMUR (Sinidu+Clima)

Plataforma nacional de inteligência territorial para diagnóstico climático, simulação de cenários, contingência e apoio à decisão municipal — desenvolvida no âmbito do MCID/CGMUR.

## Escopo

- **61 municípios prioritários** com onboarding sob demanda (malhas IBGE + integrações)
- Índices IVC, IRI e Score Sinidu+Clima
- Simulações, monitoramento, planos de contingência (COBRADE)
- Diagnósticos executivos, relatórios PDF (8+ páginas com IA) e assistente municipal (RAG)
- Simulação pluvial/calor com **visualização 3D** (MapLibre + DEM + extrusão de manchas + inspeção por clique)
- Jobs em background, catálogo nacional de dados e integrações externas
- Central da Oficina, comparação entre municípios, trilha de auditoria

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

## Documentação

- [Documentação técnica completa](documentacao/DOCUMENTACAO_TECNICA_COMPLETA.md)
- [Roadmap](ROADMAP.md)
- [Deploy](deploy/README.md)
- Checklists: `CHECKLIST_STEP8.md` (PDF enriquecido), `CHECKLIST_STEP9.md` (UX), `CHECKLIST_FASE_A_3D.md` (simulação 3D), `CHECKLIST_FASE_12.md` (cache/async)

## Simulação 3D (Fase A)

1. Abra **Simulações** → cenário **Chuva** (ex.: 120 mm) → **Rodar Simulação**
2. O mapa alterna automaticamente para **Terreno 3D**
3. Clique numa mancha para ver profundidade (cm), cota do solo e cota da água (DEM SRTM 30 m)

Piloto com LiDAR local: Recife (`2611606`). Tempo típico da simulação comparada (120 vs 80 mm): ~60 s.

## Repositório

Código-fonte do MVP Sinidu+Clima — Fases 1–10 + Steps 8–9 + Fase A 3D (jul/2026).
