# Playbook — densificar dados observados (🔶 → ✅)

Roteiro operacional para fechar os itens que **dependem de download/token humano**.
Depois de depositar, rode sync + retreino Recife.

## Ordem recomendada (impacto no ML)

| # | Fonte | Por quê | Esforço |
|---|-------|---------|---------|
| 1 | **S2ID nacional** | densifica rótulos oficiais (mais positivos reais) | 10–15 min no browser |
| 2 | **CEMADEN snapshot** | já automático; histórico opcional | 0 / captcha |
| 3 | **MERGE/CPTEC** | já automático | 0 |
| 4 | **INMET/BDMEP** | séries oficiais longas (IDF real) | cadastro + export |
| 5 | **ANA HidroWeb** | cota de rio (fluvial) | token ou CSV |

---

## 1. S2ID nacional (21c.1) — **faça primeiro**

1. Abra: https://dadosabertos.mdr.gov.br/dataset/s2id_sedec  
2. Baixe **Relatório Gerencial — Danos Informados** dos anos **2018–2022** (CSV).  
3. Renomeie/salve em:

```text
scripts/s2id_nacional/downloads/s2id_2018.csv
scripts/s2id_nacional/downloads/s2id_2019.csv
scripts/s2id_nacional/downloads/s2id_2020.csv
scripts/s2id_nacional/downloads/s2id_2021.csv
scripts/s2id_nacional/downloads/s2id_2022.csv
```

> Download por `curl`/script costuma receber `Request Rejected` (WAF). Browser real costuma funcionar.

4. Sync:

```bash
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/s2id-nacional?years=2018,2019,2020,2021,2022'
```

5. Retreino Recife:

```bash
docker exec sinidu_backend python etl/etl_flood_ml.py --municipio 2611606 --force
```

Aceite: `model_kind=full` (ou pelo menos mais positivos oficiais no card).

**Resultado jul/2026 (já executado):** CSVs 2013–2022 baixados e sync OK (`+41` eventos oficiais nos 6 pilotos). Seed de campo Recife (+34 eventos a partir das âncoras) → **modelo bairro `full_bairro` em produção** (bate baselines). Modelo municipal ainda `full_below_baseline` (Brier 0,19 > chuva 0,10). BDMEP continua manual (e-mail + confirmação no portal).

---

## 2. CEMADEN pluviômetros (21b.1)

### Automático (já no produto)
```bash
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/cemaden-pluvio?codigo_ibge=2611606'
# ou todos os pilotos:
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/cemaden-pluvio'
```

### Histórico 10/10 min (manual + captcha)
1. https://mapainterativo.cemaden.gov.br/download/downpluv.php  
2. Resolva captcha, peça o e-mail, baixe o CSV.  
3. Deposite em `scripts/cemaden_pluvio/downloads/` (montado em `/data/cemaden_pluvio`).  
4. Rode o sync de novo.

---

## 3. MERGE / CPTEC (21b.4) — automático

```bash
# Últimos 30 dias no centróide
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/merge-cptec?codigo_ibge=2611606'

# Período histórico (ex. maio/2022 Recife)
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/merge-cptec?codigo_ibge=2611606&start=2022-05-01&end=2022-05-31'
```

---

## 4. INMET / BDMEP (21b.3)

1. Cadastro gratuito: https://bdmep.inmet.gov.br/  
2. Exporte precipitação da estação do município (diária ou horária).  
3. Salve:

```text
scripts/inmet_bdmep/downloads/2611606_recife.csv
```

Colunas típicas: `CD_ESTACAO`, `DC_NOME`, `DT_MEDICAO`, `CHUVA`, `VL_LATITUDE`, `VL_LONGITUDE`.

```bash
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/inmet-bdmep?codigo_ibge=2611606'
```

---

## 5. ANA HidroWeb — cota (21b.2 / 21c.3)

### Sem token (CSV)
1. Portal HidroWeb → série de cota da estação do município.  
2. Salve:

```text
scripts/ana_hidroweb/downloads/2611606_cota.csv
```

Colunas: `estacao`, `data`, `cota_m` (opcional `vazao_m3s`).

```bash
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/ana-fluvio?codigo_ibge=2611606&dry_run=false'
```

### Com token
1. Solicite em **hidro@ana.gov.br**.  
2. Defina `ANA_HIDROWEB_TOKEN` no `.env` / compose.  
3. `curl -X POST '.../sync/ana-probe'` e depois `.../sync/ana-fluvio`.

---

## 6. Checklist pós-depósito

```bash
# 1) Syncs
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/s2id-nacional?years=2018,2019,2020,2021,2022'
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/cemaden-pluvio?codigo_ibge=2611606'
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/merge-cptec?codigo_ibge=2611606&start=2022-05-01&end=2022-05-31'
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/inmet-bdmep?codigo_ibge=2611606'
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/ana-fluvio?codigo_ibge=2611606&dry_run=false'

# 2) Retreino
docker exec sinidu_backend python etl/etl_flood_ml.py --municipio 2611606 --force

# 3) Conferir artefato
docker exec sinidu_backend python -c "
from ml.paths import model_path
import pickle
p=model_path('2611606')
print('path', p)
"
# ou card:
ls backend/ml/model_cards/ | grep 2611606
```

### Sinais de sucesso
- Sync S2ID: `ingested > 0` nos pilotos  
- Card Recife: `model_kind=full` (não `full_below_baseline` / `baseline_synthetic`)  
- Monitor usa probabilidade ML (não só heurística)

---

## Atalhos UI

| Dado | Onde no Sinidu |
|------|----------------|
| Registro pontual Defesa Civil | Monitor → **Registro em campo** |
| IDF oficial | depositar `backend/data/idf/<ibge>.json` |
| Mancha oficial | `backend/data/manchas_oficiais/<ibge>.geojson` + camada no mapa |
| DEM MERIT/ANADEM | `data/dem/local/<ibge>_merit.tif` |

---

*Atualizado jul/2026 — Fase 21 🔶.*
