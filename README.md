# Inteligência de Dados — CGMUR (Sinidu+Clima)

Plataforma nacional de inteligência territorial para diagnóstico climático, simulação de cenários, contingência e apoio à decisão municipal — desenvolvida no âmbito do MCID/CGMUR.

## Escopo

- **61 municípios prioritários** com onboarding sob demanda (malhas IBGE + integrações)
- Índices IVC, IRI e Score Sinidu+Clima
- Simulações, monitoramento, planos de contingência (COBRADE)
- Diagnósticos executivos, relatórios PDF e assistente municipal (RAG)
- Jobs em background, catálogo nacional de dados e integrações externas

## Stack

| Camada | Tecnologia |
|--------|------------|
| Frontend | Next.js 13, Leaflet, Tailwind |
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

## Repositório

Código-fonte do MVP Sinidu+Clima — Fases 1–9 concluídas (jun/2026).
