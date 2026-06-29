# OSRM — roteamento local

Região padrão no `docker-compose.yml`: **Nordeste** (PE, AL, SE, PB, RN, CE, PI, MA).

Para apenas Pernambuco (~50 MB):

```bash
OSRM_REGION=pernambuco bash docker/osrm/setup-osrm.sh
```

Para municípios em **SE, AL, PB, RN, CE, PI, MA** (ex.: São Cristóvão), use o Nordeste:

```bash
OSRM_REGION=nordeste bash docker/osrm/setup-osrm.sh
```

Configure no backend: `OSRM_COVERED_UFS=PE,AL,SE,PB,RN,CE,PI,MA` (padrão Nordeste) ou deixe derivar de `OSRM_REGION`.

### Multi-região (Fase 9)

| Região | UFs típicas |
|--------|-------------|
| `nordeste` | PE, AL, SE, PB, RN, CE, PI, MA |
| `sudeste` | SP, RJ, MG, ES |
| `sul` | PR, RS, SC |
| `centro-oeste` | GO, MT, MS, DF |
| `norte` | AM, PA, RO, … |

Status: `GET /api/v1/routing/status` — painel **Sistema** → bloco OSRM.

## Setup (uma vez)

```bash
chmod +x docker/osrm/setup-osrm.sh
bash docker/osrm/setup-osrm.sh
docker compose up -d osrm
```

Nordeste completo (maior, ~200 MB+):

```bash
OSRM_REGION=nordeste bash docker/osrm/setup-osrm.sh
```

Sem dados processados, o container fica em espera e o backend usa **fallback geodésico**.

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
