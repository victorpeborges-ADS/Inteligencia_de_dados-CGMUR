# Curvas IDF oficiais — overrides municipais (20h.4)

Este diretório guarda curvas IDF (Intensidade-Duração-Frequência) **curadas a partir
de fonte oficial** (Plano Diretor de Drenagem municipal, APAC, ANA/INMET etc.),
que sobrepõem a tabela interna `_IDF_MUNICIPAL` (qualidade `Estimado`) do
`backend/app/services/idf_rainfall_service.py`.

## Como funciona

- O serviço `idf_rainfall_service.py` lê todo arquivo `<codigo_ibge>.json`
  deste diretório na primeira chamada (cache em processo) e usa em
  `resolve_idf_precipitacao` / `idf_curve_catalog` **antes** de qualquer
  tabela interna.
- O diretório pode ser sobrescrito pela variável de ambiente `IDF_DIR`
  (ex.: `/app/data/idf` dentro do container — ver `docker-compose.yml`).
- Se não houver arquivo para o `codigo_ibge`, ou se a duração/TR pedidos não
  estiverem na curva oficial, o serviço cai de volta para
  `_IDF_MUNICIPAL` → tabela por UF → tabela nacional, normalmente.

## Nome do arquivo

`<codigo_ibge_7_digitos>.json` — ex.: `2611606.json` para Recife-PE.

## Schema JSON

```json
{
  "fonte": "APAC/plano_diretor_drenagem_recife",
  "qualidade": "Oficial",
  "referencia": "Curva IDF municipal curada (piloto 20h.4)",
  "curvas": {
    "60": {"2": 50.0, "10": 80.0, "25": 110.0, "100": 150.0},
    "120": {"2": 65.0, "10": 100.0, "25": 135.0, "100": 185.0},
    "1440": {"2": 75.0, "10": 115.0, "25": 155.0, "100": 230.0}
  }
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `fonte` | string | Identificador curto da fonte oficial (aparece em `resolve_idf_precipitacao().fonte`). |
| `qualidade` | string | Normalmente `"Oficial"`. Propagado para `qualidade_dado` na UI/API. |
| `referencia` | string | Texto livre citando o documento/estudo de origem (usado na nota metodológica). |
| `curvas` | objeto | Mapa `duracao_min (string) → { periodo_retorno_anos (string) → lâmina_mm (number) }`. |

- Durações e períodos de retorno não precisam cobrir todos os valores
  suportados (`SUPPORTED_DURATIONS = 60, 120, 1440`; `SUPPORTED_TR = 2, 10, 25, 100`);
  o que faltar cai para a tabela interna do município/UF/nacional.
- Os valores devem ser lâmina acumulada em mm para a duração indicada (não
  intensidade mm/h) — o serviço converte para `intensidade_mm_h` internamente.

## Depositando uma curva nova

1. Gere/curador do PDF ou planilha oficial extrai os valores de lâmina (mm) por
   duração × TR.
2. Preencha `fonte`, `qualidade="Oficial"` e `referencia` citando o documento.
3. Salve como `backend/data/idf/<codigo_ibge>.json`.
4. Rode `pytest backend/tests/test_idf_rainfall.py` para validar o override.
5. Ver também `scripts/idf/README.md` para o fluxo de depósito manual.
