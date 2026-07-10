# Checklist — demo / oficina MCID (Sinidu+Clima)

Roteiro rápido antes de apresentação ao MCID ou oficina municipal. Piloto: **Recife** (`2611606`).

## 1. Subir stack (dev)

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
docker compose up -d
```

Aguarde `http://localhost:8000/health/ready` retornar 200.

## 2. Smoke test automatizado

```bash
chmod +x scripts/demo-smoke.sh
./scripts/demo-smoke.sh
```

Ou só API:

```bash
python3 scripts/homolog_smoke_test.py http://localhost:8000
```

## 3. OSRM — rotas reais na contingência

Sem dados OSRM, o backend usa **fallback geodésico** (linha reta). Para demo com rotas viárias no Nordeste (~414 MB + 10–25 min de processamento):

```bash
OSRM_REGION=pe-se bash scripts/osrm-enable.sh
docker compose up -d osrm backend
curl -s http://localhost:8000/api/v1/routing/status | python3 -m json.tool
```

Esperado: `"available": true`, `"covered_ufs"` inclui `PE` (Recife).

Para demo rápida **sem OSRM**, o fluxo de contingência funciona com fallback — valide apenas o banner na UI.

## 4. Roteiro UI (~5 min)

| # | Ação | O que validar |
|---|------|----------------|
| 1 | `http://localhost:3000/painel` | Narrativa executiva + **recomendações territoriais** + KPIs prioritários |
| 2 | **Simulações** → 120 mm pluvial | Barra de progresso; badge **cache** na 2ª execução |
| 3 | Após simulação | Terreno **3D** + card **Próximos passos** |
| 4 | Tecla **F** | Modo Focus (mapa expandido) |
| 5 | **Contingência** | Banner OSRM verde se PE + OSRM online |
| 6 | **Centro de oficina** → Comparar | Par sugerido Recife × Salvador + deltas |
| 7 | **Catálogo** | Bloco "Trâmite institucional" + Impacto IA por fonte |

## 5. Homologação institucional (opcional)

Auth + TLS + OIDC local:

```bash
./scripts/homolog-up.sh
./scripts/demo-smoke.sh https://localhost/api/v1  # via proxy — ajuste BASE no script
python3 scripts/homolog_smoke_test.py https://localhost
```

Detalhes: [`deploy/README.md`](deploy/README.md)

## 6. Critérios de go / no-go

| Item | Go | No-go |
|------|-----|-------|
| `health/ready` | 200 | Falha ou timeout |
| Diagnóstico Recife | 200 | 5xx ou vazio |
| Simulação 120 mm | Completa em &lt; 2 min (ou cache) | Erro ou &gt; 5 min |
| Mapa 3D pós-simulação | Camadas visíveis | Overlay de erro React |
| OSRM (desejável) | `available: true` para PE | OK usar fallback se tempo curto |

## Referências

- Fase 12/12b: [`CHECKLIST_FASE_12.md`](CHECKLIST_FASE_12.md)
- UX institucional: [`CHECKLIST_FASE_13.md`](CHECKLIST_FASE_13.md)
- OSRM: [`docker/osrm/README.md`](docker/osrm/README.md)
