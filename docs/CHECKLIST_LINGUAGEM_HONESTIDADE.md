# Checklist de linguagem — honestidade metodológica (20h.6)

Uso: demos MCID, apresentações, agente contextual e copy de UI.

## Proibido (sem qualificador)

- “metodologia oficial” (referindo-se à **simulação** Sinidu)
- “homologado” / “homologação de engenharia”
- “preciso como engenharia” / “equivalente a HEC-RAS”
- “alerta oficial Sinidu” / “substitui CEMADEN”
- “laudo” / “perícia” gerados pelo produto

## Preferir

| Em vez de | Usar |
|-----------|------|
| probabilidade (heurística) | score heurístico de chuva |
| alerta Sinidu | aviso / triagem municipal (não substitui CEMADEN) |
| oficial (resultado simulado) | Derivado ou Estimado + fonte de entrada |
| LST oficial Sinidu | LST observada GeoReDUS (Observado) vs cenário Sinidu (Derivado) |

## Permitido

- Fontes oficiais de **entrada**: IBGE, CEMADEN, S2ID, MapBiomas, CAPAG
- Selo **Oficial** só quando `data_quality` / camada for de fato oficial
- “triagem territorial”, “priorização”, “exercício de contingência”

## Gold standard (demo)

> O Sinidu+Clima usa dados oficiais de entrada e produz estimativas territoriais
> com selo explícito. Não é laudo de engenharia nem alerta CEMADEN.
