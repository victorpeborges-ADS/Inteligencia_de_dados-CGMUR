# CHECKLIST FASE A — Simulação 3D open source (MapLibre)

**Objetivo:** visualizar volume de água e ilhas de calor em 3D sem Google Street View (custo de API).

**Atualizado:** jul/2026 · Piloto: Recife (`2611606`)

---

## Escopo implementado

- [x] Extrusão `fill-extrusion` das manchas de alagamento (altura = média da faixa de profundidade)
- [x] Extrusão de ilha de calor (`temp_increase_celsius × 12`)
- [x] Terreno MapLibre 4.7 + DEM Terrarium (CDN)
- [x] Voo oblíquo automático (`fitBounds` + pitch ~68°) após simulação
- [x] Troca automática para **Terreno 3D** em simulação pluvial ou perda de vegetação
- [x] Inspeção por clique: solo (m), +cm água, cota da água, faixa (superficial/moderada/crítica)
- [x] Marcador amarelo no ponto inspecionado
- [x] Painel inferior esquerdo com instruções e resultado da inspeção
- [x] Controles: basemap satélite/escuro, exagero relevo, inclinação

## Fora de escopo (Fase A)

- [ ] Google Street View (`Map3DGoogleContainer.tsx` — código existe, não integrado)
- [ ] Modelagem hidrodinâmica 2D / HEC-RAS
- [ ] Precisão de fachada (requer LiDAR + mesh 3D dedicado)

---

## Arquivos

| Área | Path |
|------|------|
| Container 3D | `frontend/src/components/Map/Map3DMapLibreContainer.tsx` |
| Camadas MapLibre | `frontend/src/components/Map/maplibreLayers.ts` |
| Estilos / extrusão | `frontend/src/components/Map/layerStyles.ts` |
| Inspeção | `frontend/src/utils/floodInspect.ts` |
| Auto 3D | `frontend/src/components/Platform/PlatformApp.tsx` (`handleSimulate`) |
| Motor hidro | `backend/app/services/hydro_simulator.py` |

---

## Faixas de profundidade (backend)

| Faixa | Profundidade |
|-------|----------------|
| `superficial` | 0,05 – 0,35 m |
| `moderada` | 0,35 – 0,80 m |
| `critica` | > 0,80 m |

Propriedades GeoJSON: `depth_band`, `depth_min_m`, `depth_max_m`, `precipitation_mm`, `layer_type: flood_band`.

---

## Smoke test

### Backend (~60 s)

```bash
curl -X POST "http://localhost:8000/api/v1/simulations/extreme-rainfall/compare" \
  -H "Content-Type: application/json" \
  -d '{"codigo_ibge":"2611606","scenario_mm":120,"baseline_mm":80}'
```

Esperado: `scenario.geometry.features` com dezenas de polígonos (ex.: 84 manchas).

### Frontend

1. `http://localhost:3000/simulacoes` · Recife · **Chuva** 120 mm · **Rodar Simulação**
2. Mapa alterna para **Terreno 3D** (MapLibre, não Leaflet)
3. Painel *Simulação 3D — volume de água* visível
4. Clicar numa mancha → profundidade em cm + cotas
5. Aba **Vegetação** → simular perda → painel *ilha de calor* + colunas vermelhas

---

## Limitações documentadas

- DEM SRTM 30 m: incerteza vertical ±16 m
- Recife piloto: LiDAR local melhora isolinhas/simulação, mas extrusão 3D segue resolução do raster
- Simulação comparada executa **dois** cenários hidrológicos (~1 min)

---

## Critério de done

Demonstração em 3D com manchas extrudadas e leitura de profundidade/cota por clique, sem dependência de APIs pagas de Street View.
