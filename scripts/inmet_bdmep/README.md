# INMET / BDMEP (Fase 21b.3)

Fonte: [BDMEP / INMET](https://bdmep.inmet.gov.br/) — séries pluviométricas oficiais.

## Como ingerir (sem token de API)

1. Cadastre-se no BDMEP (gratuito) e exporte precipitação da estação do município (diária ou horária).
2. Salve o CSV em:

```text
scripts/inmet_bdmep/downloads/2611606_recife.csv
```

Colunas reconhecidas (PT/EN): `CD_ESTACAO`, `DC_NOME`, `DT_MEDICAO`/`Data`, `CHUVA`/`PRECIPITACAO`, `VL_LATITUDE`, `VL_LONGITUDE`.

3. Monte/copie para o container e rode:

```bash
docker cp scripts/inmet_bdmep/downloads/. sinidu_backend:/data/inmet_bdmep/
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/inmet-bdmep?codigo_ibge=2611606'
```

Os registros entram em `serie_pluviometrica_observada` com `fonte=inmet` e `data_quality=oficial`.
