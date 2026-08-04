# Pilotos PE com LiDAR (PE3D) — Camutanga e Ilha de Itamaracá

Municípios pequenos de Pernambuco adicionados ao catálogo Sinidu para DEM de alta resolução via **PE3D** (Pernambuco Tridimensional).

| Município | IBGE | Área (aprox.) | Papel |
|-----------|------|---------------|--------|
| Camutanga | `2603603` | ~39 km² | Piloto LiDAR / município pequeno (Mata) |
| Ilha de Itamaracá | `2607604` | ~67 km² | Piloto LiDAR / risco costeiro |

## 1. DEM interino (SRTM) — já automatizável

```bash
export OPENTOPOGRAPHY_API_KEY=...   # ou source .env
python3 scripts/pe3d/fetch_srtm_pe_lidar_pilots.py
```

Grava `data/dem/local/2603603.tif` e `2607604.tif`.

## 2. DEM LiDAR PE3D (recomendado)

1. Cadastro gratuito: https://www.pe3d.pe.gov.br/
2. Baixe os tiles **MDT** (ZIP com `.xyz` UTM 25S) e coloque em `mdt/`.
3. Extraia e converta:

```bash
mkdir -p data/dem/pe3d_mdt/xyz
unzip -o -j 'mdt/MDT-*.zip' -d data/dem/pe3d_mdt/xyz

docker exec -w /app -e PYTHONPATH=/app sinidu_backend \
  python scripts/xyz_mdt_to_lidar.py \
  --xyz-dir /data/dem/pe3d_mdt/xyz \
  --out-dir /data/dem/local \
  --resolution 2.0
```

Isso gera:

```text
data/dem/local/2603603_lidar.tif
data/dem/local/2607604_lidar.tif
```

O `dem_processor` prioriza `*_lidar.tif` sobre o SRTM.

## 2b. MDS PE3D → cidade 3D (edificações LOD1)

O MDT é só terreno. Para alturas de prédios estilo GeoSampa, baixe os tiles **MDS** (modelo digital de superfície) no PE3D e converta:

```bash
mkdir -p data/dem/pe3d_mds/xyz mds
# coloque ZIPs MDS-*.zip em mds/ e extraia:
unzip -o -j 'mds/MDS-*.zip' -d data/dem/pe3d_mds/xyz

docker exec -w /app -e PYTHONPATH=/app sinidu_backend \
  python scripts/xyz_mdt_to_lidar.py \
  --xyz-dir /data/dem/pe3d_mds/xyz \
  --out-dir /data/dem/local \
  --product mds \
  --resolution 2.0
```

Gera `data/dem/local/{ibge}_dsm.tif`. Depois:

```bash
# footprints OSM + alturas
curl -X POST 'http://localhost:8000/api/v1/buildings/2603603/sync?force=true' \
  -H "Authorization: Bearer $TOKEN"

# refine alturas = MDS − MDT
curl -X POST 'http://localhost:8000/api/v1/buildings/2603603/refine-ndsm?force_rebuild=true' \
  -H "Authorization: Bearer $TOKEN"
```

Na UI: **Camadas → Edificações (LOD1)** com o mapa em modo **TERRENO 3D** (pitch alto).

Sem MDS, o sync usa OSM; se houver poucos footprints (comum em municípios pequenos),
cai automaticamente para **Microsoft Global Building Footprints** (altura heurística ~6 m)
até o MDS PE3D refinar as alturas.

```bash
# forçar só Microsoft
curl -X POST 'http://localhost:8000/api/v1/buildings/2603603/sync-microsoft?force=true' \
  -H "Authorization: Bearer $TOKEN"
```

## 3. Onboarding + processar terreno

```bash
curl -X POST 'http://localhost:8000/api/v1/onboarding/run' \
  -H 'Content-Type: application/json' \
  -d '{"codigo_ibge":"2603603","force":true}'

curl -X POST 'http://localhost:8000/api/v1/onboarding/run' \
  -H 'Content-Type: application/json' \
  -d '{"codigo_ibge":"2607604","force":true}'

curl -X POST 'http://localhost:8000/api/v1/terrain/2603603/process?force=true'
curl -X POST 'http://localhost:8000/api/v1/terrain/2607604/process?force=true'
```

Ou na UI: **Municípios** → buscar código → Ativar / Onboarding completo.

## 4. Eventos de campo (opcional)

```bash
docker exec sinidu_backend python scripts/seed_pe_lidar_field_events.py
```
