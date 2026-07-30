# DEM hidrologicamente condicionado (21b.5)

Deposite GeoTIFF MERIT-Hydro ou ANADEM recortado ao município:

```text
data/dem/local/2611606_merit.tif
data/dem/local/2611606_anadem.tif
# ou
data/dem/2611606/merit.tif
```

Ao processar, o `dem_processor` marca `hydro_dem=true` / `dem_source=MERIT-Hydro|ANADEM` e o `hydro_simulator` **pula** o Priority-Flood interno (já vem condicionado na fonte).

Reprocesse:

```bash
curl -X POST 'http://localhost:8000/api/v1/terrain/2611606/process?force=true'
```
