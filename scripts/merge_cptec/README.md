# MERGE / CPTEC-INPE (Fase 21b.4)

Produto diário de precipitação por satélite calibrado por pluviômetros (grade ~0,1°).
FTP público: [ftp.cptec.inpe.br/.../MERGE/GPM/DAILY](https://ftp.cptec.inpe.br/modelos/tempo/MERGE/GPM/DAILY/).

## Sync automático (recomendado)

O backend baixa GRIB2 sob demanda e amostra a banda PREC no centróide municipal:

```bash
# Últimos 30 dias (default) — Recife
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/merge-cptec?codigo_ibge=2611606'

# Período explícito
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/merge-cptec?codigo_ibge=2611606&start=2024-05-01&end=2024-05-31'

# Só cache local (sem rede)
curl -X POST 'http://localhost:8000/api/v1/monitoring/sync/merge-cptec?codigo_ibge=2611606&download=false'
```

Registros em `serie_pluviometrica_observada` com `fonte=merge` e `data_quality=reanalise`.

## Cache local

Arquivos ficam em:

```text
scripts/merge_cptec/downloads/MERGE_CPTEC_YYYYMMDD.grib2
```

(volume Docker: `/data/merge_cptec`). Pode depositar GRIBs manualmente se o FTP estiver indisponível.

## Nota de qualidade

MERGE não substitui estação oficial (CEMADEN/INMET/ANA): cobre áreas sem pluviômetro com grade satélite+calibração. Use como série de preenchimento / reanálise, não como rótulo `oficial` no treino ML.
