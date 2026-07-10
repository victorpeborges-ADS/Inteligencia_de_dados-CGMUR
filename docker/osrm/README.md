# OSRM — roteamento local

## Perfil recomendado para demo (Recife + Aracaju)

**`pe-se`** — merge Pernambuco + Sergipe (~80 MB). Processa em poucos minutos no Mac Mini.

```bash
OSRM_REGION=pe-se bash scripts/osrm-enable.sh
```

Cobre **PE** e **SE** com malha viária real na contingência.

## Nordeste completo

Região macro Geofabrik (~414 MB PBF; PE, AL, SE, PB, RN, CE, PI, MA).

```bash
OSRM_REGION=nordeste bash scripts/osrm-enable.sh
```

**Merge PE+SE:** requer `osmium-tool` no host (`brew install osmium-tool`) ou imagem Docker alternativa. Se o processo morrer com exit **137** (OOM), aumente RAM ou use `OSRM_DOCKER_MEMORY=10g`. O script remove artefatos parciais e retoma do PBF.

## Regiões disponíveis

| Região | Tamanho PBF (aprox.) | UFs típicas |
|--------|----------------------|-------------|
| **`pe-se`** | **~80 MB** | **PE, SE** (demo piloto) |
| `nordeste` | ~414 MB | PE, AL, SE, PB, RN, CE, PI, MA |
| `sudeste` | ~811 MB | SP, RJ, MG, ES |
| `sul` | ~399 MB | PR, RS, SC |
| `centro-oeste` | ~190 MB | GO, MT, MS, DF |
| `norte` | ~150 MB | AM, PA, RO, … |
| `brazil` | ~1,9 GB | nacional |

Configure no backend via `.env`:

```bash
OSRM_REGION=pe-se
OSRM_COVERED_UFS=PE,SE
```

Status: `GET /api/v1/routing/status` — painel **Sistema** → bloco OSRM.

## Setup manual

```bash
chmod +x docker/osrm/setup-osrm.sh scripts/osrm-enable.sh
OSRM_REGION=pe-se bash docker/osrm/setup-osrm.sh
docker compose up -d osrm
```

Sem dados processados, o container fica em espera e o backend usa **fallback geodésico**.

Checklist demo MCID: [`CHECKLIST_DEMO_MCID.md`](../CHECKLIST_DEMO_MCID.md)
