# Depósito de curvas IDF oficiais (20h.4)

Este diretório documenta o fluxo manual para depositar curvas IDF
(Intensidade-Duração-Frequência) oficiais por município, que passam a ter
precedência sobre as tabelas internas `Estimado` do
`backend/app/services/idf_rainfall_service.py`.

## Onde salvar

Os arquivos consumidos pelo backend ficam em:

```
backend/data/idf/<codigo_ibge>.json
```

Ver o schema completo em `backend/data/idf/README.md`.

## Fontes recomendadas por prioridade

1. **Plano Diretor de Drenagem municipal** (curva IDF do próprio estudo, quando
   publicado) — maior precedência, já é a curva de projeto usada pela
   prefeitura.
2. **ANA** — equações IDF regionalizadas (quando disponíveis para o município).
3. **INMET/BDMEP** — séries horárias longas, permitem ajuste de curva IDF local
   (casa com 21b.3 — coletor `inmet_bdmep_collector.py`).
4. **APAC / órgão estadual de meteorologia** — boletins e estudos técnicos
   estaduais/municipais.

## Passo a passo

1. Obtenha o PDF/planilha/equação oficial da fonte.
2. Extraia a lâmina acumulada (mm) por duração de projeto (min) × período de
   retorno (anos) — não confundir com intensidade (mm/h).
3. Preencha o JSON conforme `backend/data/idf/README.md`, citando a fonte em
   `fonte` e o documento/estudo em `referencia`.
4. Salve em `backend/data/idf/<codigo_ibge>.json`.
5. Rode os testes: `pytest backend/tests/test_idf_rainfall.py -v`.
6. No Docker, o backend lê o diretório via `IDF_DIR=/app/data/idf`
   (bind mount `./backend:/app` já expõe `backend/data/idf`).

## Não versionar dados sensíveis

Se a curva oficial vier de um PDF restrito ou licenciado, deposite apenas os
valores numéricos extraídos (mm por duração/TR) — não é necessário versionar o
PDF original neste repositório.
