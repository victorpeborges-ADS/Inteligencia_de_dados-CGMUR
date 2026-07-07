# OSRM — roteamento local

Região padrão no `docker-compose.yml`: **Nordeste** (~414 MB PBF; PE, AL, SE, PB, RN, CE, PI, MA).

Geofabrik disponibiliza apenas **regiões macro** do Brasil (não há extract estadual de Pernambuco).

```bash
OSRM_REGION=nordeste bash docker/osrm/setup-osrm.sh
docker compose up -d osrm
```

**Memória:** configure Docker Desktop ≥ 8 GB. Se o processo morrer com exit **137** (OOM), aumente RAM ou use `OSRM_DOCKER_MEMORY=10g`. O script remove artefatos parciais e retoma do PBF.

Para outras regiões:

| Região | Tamanho PBF (aprox.) | UFs típicas |
|--------|----------------------|-------------|
| `nordeste` | ~414 MB | PE, AL, SE, PB, RN, CE, PI, MA |
| `sudeste` | ~811 MB | SP, RJ, MG, ES |
| `sul` | ~399 MB | PR, RS, SC |
| `centro-oeste` | ~190 MB | GO, MT, MS, DF |
| `norte` | ~150 MB | AM, PA, RO, … |
| `brazil` | ~1,9 GB | nacional |

Configure no backend: `OSRM_COVERED_UFS` (opcional; padrão derivado de `OSRM_REGION`).

Override via `.env`:

```bash
OSRM_REGION=nordeste
OSRM_COVERED_UFS=PE,AL,SE,PB,RN,CE,PI,MA
```

Status: `GET /api/v1/routing/status` — painel **Sistema** → bloco OSRM.

## Setup (uma vez)

```bash
chmod +x docker/osrm/setup-osrm.sh
bash docker/osrm/setup-osrm.sh
docker compose up -d osrm
```

Sem dados processados, o container fica em espera e o backend usa **fallback geodésico**.

Checklist demo MCID: [`CHECKLIST_DEMO_MCID.md`](../CHECKLIST_DEMO_MCID.md)

## Gotify — notificações push

1. Suba o Gotify: `docker compose up -d gotify`
2. Gere token:
   ```bash
   chmod +x docker/gotify/setup-token.sh
   bash docker/gotify/setup-token.sh
   ```
3. Cole `GOTIFY_TOKEN=...` no `docker-compose.yml` (serviço backend)
4. Acesse http://localhost:8888 (admin / admin) e instale o app mobile ou use a UI web

Alertas **LARANJA** e **VERMELHO** disparam push automaticamente.
