# S2ID nacional (Fase 21c.1)

Fonte: [dados abertos MIDR/SEDEC — s2id_sedec](https://dadosabertos.mdr.gov.br/dataset/s2id_sedec)

## Problema conhecido

O download direto dos CSVs costuma ser bloqueado por WAF (`Request Rejected`), mesmo com User-Agent de browser.

## Como ingerir

1. Abra o dataset no navegador e baixe os anos desejados (ex.: 2018–2022).
2. Copie os arquivos para esta pasta (montada no container em `/data/s2id_nacional/downloads`):

```text
scripts/s2id_nacional/downloads/s2id_2020.csv
scripts/s2id_nacional/downloads/s2id_2021.csv
scripts/s2id_nacional/downloads/s2id_2022.csv
```

Se o volume ainda não estiver montado:

```bash
docker cp scripts/s2id_nacional/downloads/. sinidu_backend:/data/s2id_nacional/downloads/
```

3. Rode a ingestão:

```bash
# API
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/s2id-nacional?years=2020,2021,2022'

# ou no container
docker exec sinidu_backend python -c "
from app.db import SessionLocal
from app.data_connectors.s2id_nacional_collector import ingest_national_s2id_for_pilotos
db = SessionLocal()
print(ingest_national_s2id_for_pilotos(db, years=[2020,2021,2022]))
db.close()
"
```

Eventos hidrológicos (COBRADE 121/122/123 e chuvas intensas) dos 6 municípios-piloto entram em `historico_desastres_s2id` com `data_quality=oficial` e `fonte=s2id_nacional_mdr`.
