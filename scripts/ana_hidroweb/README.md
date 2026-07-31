# ANA HidroWeb — séries fluviométricas (21c.3 / 21d.9)

Sem token da API, deposite CSV exportado do HidroWeb:

```text
scripts/ana_hidroweb/downloads/2611606_cota.csv
```

Colunas reconhecidas: `estacao`, `data`, `cota_m` (e opcionalmente `vazao_m3s`, `latitude`, `longitude`, `nome`).

```bash
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/ana-fluvio?codigo_ibge=2611606&dry_run=false'
```

Com `ANA_HIDROWEB_TOKEN`, o mesmo endpoint faz probe autenticado quando não há CSV.
