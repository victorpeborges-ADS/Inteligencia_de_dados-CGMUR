'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type MunicipalityOption, type TerrainConfig, type TerrainMesh } from '@/utils/api';

declare global {
  interface Window {
    deck?: {
      Deck: new (props: Record<string, unknown>) => {
        setProps: (p: Record<string, unknown>) => void;
        finalize: () => void;
      };
      SimpleMeshLayer: new (p: Record<string, unknown>) => unknown;
      TileLayer: new (p: Record<string, unknown>) => unknown;
      BitmapLayer: new (p: Record<string, unknown>) => unknown;
      PathLayer: new (p: Record<string, unknown>) => unknown;
      ColumnLayer: new (p: Record<string, unknown>) => unknown;
      HeatmapLayer: new (p: Record<string, unknown>) => unknown;
      COORDINATE_SYSTEM: { LNGLAT: number };
      WebMercatorViewport: new (props: Record<string, unknown>) => {
        fitBounds: (b: [[number, number], [number, number]], opts?: { padding?: number; maxZoom?: number }) => {
          longitude: number;
          latitude: number;
          zoom: number;
        };
      };
    };
  }
}

interface Map3DProps {
  selectedMunicipio: string;
  municipalities: MunicipalityOption[];
  onMunicipioChange: (codigoIbge: string) => void;
  simGeoJSON: any;
  mapFocus: [number, number];
  verticalExaggeration: number;
  onVerticalExaggerationChange: (value: number) => void;
  floodLevel: number;
  onFloodLevelChange: (value: number) => void;
}

type ColumnDatum = { position: [number, number]; height: number; vm: number; nome: string };
type HeatmapDatum = { position: [number, number]; weight: number };

const DECK_CDN = 'https://cdn.jsdelivr.net/npm/deck.gl@9.0.38/dist.min.js';

function loadDeckGl() {
  if (typeof window === 'undefined') return Promise.reject(new Error('SSR'));
  if (window.deck) return Promise.resolve(window.deck!);
  return new Promise<NonNullable<Window['deck']>>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = DECK_CDN;
    script.async = true;
    script.onload = () => {
      if (window.deck) resolve(window.deck);
      else reject(new Error('deck.gl'));
    };
    script.onerror = () => reject(new Error('CDN deck.gl'));
    document.head.appendChild(script);
  });
}

function centroidOfPolygon(coords: number[][][]): [number, number] {
  const ring = coords[0] ?? coords;
  let sx = 0, sy = 0;
  for (const [lon, lat] of ring) { sx += lon; sy += lat; }
  return [sx / ring.length, sy / ring.length];
}

function vmColor(vm: number): [number, number, number, number] {
  const t = Math.min(1, Math.max(0, vm));
  return [Math.round(20 + t * 220), Math.round(180 - t * 120), Math.round(160 - t * 130), 220];
}

/** Converte grid de altitudes em malha 3D para SimpleMeshLayer (coordenadas LNGLAT + Z em metros). */
function buildMeshFromGrid(mesh: TerrainMesh, exaggeration: number) {
  const { width, height, bounds, heights, colors } = mesh;
  const [west, south, east, north] = bounds;
  const n = width * height;
  const positions = new Float32Array(n * 3);
  const meshColors = new Uint8ClampedArray(n * 4);

  for (let row = 0; row < height; row++) {
    for (let col = 0; col < width; col++) {
      const idx = row * width + col;
      positions[idx * 3] = west + (col / (width - 1)) * (east - west);
      positions[idx * 3 + 1] = south + (row / (height - 1)) * (north - south);
      positions[idx * 3 + 2] = heights[idx] * exaggeration;
      const ci = idx * 3;
      meshColors[idx * 4] = colors[ci];
      meshColors[idx * 4 + 1] = colors[ci + 1];
      meshColors[idx * 4 + 2] = colors[ci + 2];
      meshColors[idx * 4 + 3] = 255;
    }
  }

  const triCount = (width - 1) * (height - 1) * 2;
  const indices = new Uint32Array(triCount * 3);
  let t = 0;
  for (let row = 0; row < height - 1; row++) {
    for (let col = 0; col < width - 1; col++) {
      const a = row * width + col;
      const b = a + 1;
      const c = a + width;
      const d = c + 1;
      indices[t++] = a; indices[t++] = c; indices[t++] = b;
      indices[t++] = b; indices[t++] = c; indices[t++] = d;
    }
  }

  return {
    attributes: {
      positions: { size: 3, value: positions },
      colors: { size: 4, value: meshColors, normalized: true },
    },
    indices: { size: 1, value: indices },
  };
}

function fitViewToBounds(
  deckLib: NonNullable<Window['deck']>,
  bounds: [number, number, number, number],
  width: number,
  height: number,
) {
  const [west, south, east, north] = bounds;
  const vp = new deckLib.WebMercatorViewport({ width, height });
  const fitted = vp.fitBounds(
    [[west, south], [east, north]],
    { padding: 60, maxZoom: 14 },
  );
  return {
    longitude: fitted.longitude,
    latitude: fitted.latitude,
    zoom: fitted.zoom,
    pitch: 58,
    bearing: -30,
    minZoom: 8,
    maxZoom: 18,
  };
}

type DeckInstance = {
  setProps: (p: Record<string, unknown>) => void;
  finalize: () => void;
};

export default function Map3DContainer({
  selectedMunicipio,
  municipalities,
  onMunicipioChange,
  simGeoJSON,
  mapFocus,
  verticalExaggeration,
  onVerticalExaggerationChange,
  floodLevel,
  onFloodLevelChange,
}: Map3DProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const deckRef = useRef<DeckInstance | null>(null);
  const sizeRef = useRef({ width: 800, height: 600 });

  const [terrain, setTerrain] = useState<TerrainConfig | null>(null);
  const [meshData, setMeshData] = useState<TerrainMesh | null>(null);
  const [flowPaths, setFlowPaths] = useState<any>(null);
  const [columns, setColumns] = useState<ColumnDatum[]>([]);
  const [heatmapPoints, setHeatmapPoints] = useState<HeatmapDatum[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [deckReady, setDeckReady] = useState(false);
  const [viewState, setViewState] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    loadDeckGl().then(() => setDeckReady(true)).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) {
        sizeRef.current = { width, height };
        deckRef.current?.setProps({ width, height });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const loadTerrain = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let config: TerrainConfig;
      try {
        config = await api.getTerrainConfig(selectedMunicipio);
      } catch {
        setProcessing(true);
        config = (await api.processTerrainDem(selectedMunicipio, true)).config;
        setProcessing(false);
      }
      setTerrain(config);

      const meshUrl = config.mesh_url || config.elevation_url.replace('elevation.png', 'mesh.json');
      const [mesh, flowRes, vmLayer] = await Promise.all([
        fetch(meshUrl).then((r) => {
          if (!r.ok) throw new Error('mesh.json ausente — reprocesse o DEM');
          return r.json() as Promise<TerrainMesh>;
        }),
        fetch(config.flow_paths_url).then((r) => r.json()).catch(() => ({ features: [] })),
        api.getLayerGeoJSON('vulnerabilidade_multidimensional', selectedMunicipio).catch(() => null),
      ]);
      setMeshData(mesh);
      setFlowPaths(flowRes);

      const { width, height } = sizeRef.current;
      if (window.deck && mesh.bounds) {
        setViewState(fitViewToBounds(window.deck, mesh.bounds, width, height));
      }

      const cols: ColumnDatum[] = [];
      vmLayer?.features?.forEach((feat: any) => {
        const vm = Number(feat.properties?.indice_vm ?? feat.properties?.indice_vulnerabilidade ?? 0.4);
        if (feat.geometry?.type === 'Polygon') {
          cols.push({
            position: centroidOfPolygon(feat.geometry.coordinates),
            height: vm * 400 * verticalExaggeration,
            vm,
            nome: String(feat.properties?.nome ?? feat.properties?.bairro ?? 'Bairro'),
          });
        }
      });
      setColumns(cols);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar 3D');
    } finally {
      setLoading(false);
      setProcessing(false);
    }
  }, [selectedMunicipio, verticalExaggeration]);

  useEffect(() => { loadTerrain(); }, [loadTerrain]);

  useEffect(() => {
    const pts: Array<{ position: [number, number]; weight: number }> = [];
    if (simGeoJSON?.features?.length) {
      simGeoJSON.features.forEach((f: any) => {
        if (f.geometry?.type === 'Polygon') {
          pts.push({
            position: centroidOfPolygon(f.geometry.coordinates),
            weight: Number(f.properties?.intensidade ?? floodLevel / 100),
          });
        }
      });
    } else {
      api.getLayerGeoJSON('inundacao', selectedMunicipio).then((layer) => {
        layer.features?.forEach((f: any) => {
          if (f.geometry?.type === 'Polygon') {
            pts.push({
              position: centroidOfPolygon(f.geometry.coordinates),
              weight: Number(f.properties?.indice_risco ?? 0.6),
            });
          }
        });
        setHeatmapPoints(pts);
      }).catch(() => setHeatmapPoints([]));
      return;
    }
    setHeatmapPoints(pts);
  }, [simGeoJSON, selectedMunicipio, floodLevel]);

  useEffect(() => {
    const deckLib = window.deck;
    const container = wrapRef.current;
    if (!deckLib || !deckReady || !container || !meshData || !viewState) return;

    const { width, height } = sizeRef.current;
    const mesh = buildMeshFromGrid(meshData, verticalExaggeration);
    const CS = deckLib.COORDINATE_SYSTEM.LNGLAT;

    const layers: unknown[] = [
      new deckLib.TileLayer({
        id: 'basemap',
        data: 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        minZoom: 0,
        maxZoom: 19,
        tileSize: 256,
        renderSubLayers: (props: any) =>
          new deckLib.BitmapLayer({
            ...props,
            data: undefined,
            image: props.data,
            bounds: [props.tile.bbox.west, props.tile.bbox.south, props.tile.bbox.east, props.tile.bbox.north],
          }),
      }),
      new deckLib.SimpleMeshLayer({
        id: 'terrain-mesh',
        data: [1],
        mesh,
        coordinateSystem: CS,
        getPosition: () => [0, 0, 0],
        material: { ambient: 0.55, diffuse: 0.85, shininess: 28, specularColor: [30, 35, 40] },
        pickable: true,
      }),
    ];

    if (flowPaths?.features?.length) {
      layers.push(
        new deckLib.PathLayer({
          id: 'flow',
          data: flowPaths.features,
          getPath: (f: any) => f.geometry.coordinates,
          getColor: [56, 189, 248, 230],
          getWidth: 5,
          widthMinPixels: 2,
          coordinateSystem: CS,
        }),
      );
    }

    if (columns.length) {
      layers.push(
        new deckLib.ColumnLayer({
          id: 'vm-bars',
          data: columns,
          diskResolution: 12,
          radius: 150,
          extruded: true,
          pickable: true,
          coordinateSystem: CS,
          getPosition: (d: ColumnDatum) => d.position,
          getElevation: (d: ColumnDatum) => d.height * (1 + floodLevel / 200),
          getFillColor: (d: ColumnDatum) => vmColor(d.vm),
        }),
      );
    }

    if (heatmapPoints.length) {
      layers.push(
        new deckLib.HeatmapLayer({
          id: 'flood',
          data: heatmapPoints,
          getPosition: (d: HeatmapDatum) => d.position,
          getWeight: (d: HeatmapDatum) => d.weight * (0.5 + floodLevel / 100),
          radiusPixels: 55,
          intensity: 1.8,
          threshold: 0.04,
          coordinateSystem: CS,
        }),
      );
    }

    if (!deckRef.current) {
      deckRef.current = new deckLib.Deck({
        parent: container,
        width,
        height,
        initialViewState: viewState,
        controller: true,
        layers,
        onViewStateChange: ({ viewState: vs }: { viewState: Record<string, number> }) => setViewState(vs),
        getTooltip: ({ object }: { object?: ColumnDatum }) =>
          object?.nome ? { text: `${object.nome}\nVM ${(object.vm * 100).toFixed(0)}%` } : null,
      });
    } else {
      deckRef.current.setProps({ layers, width, height });
    }
  }, [deckReady, meshData, viewState, flowPaths, columns, heatmapPoints, verticalExaggeration, floodLevel]);

  useEffect(() => () => { deckRef.current?.finalize(); deckRef.current = null; }, []);

  return (
    <div ref={wrapRef} className="relative h-full w-full min-h-[400px] bg-[#0d1117]">
      <div className="absolute right-4 top-24 z-[1200] w-72 space-y-2 rounded-xl border border-teal-500/30 bg-zinc-950/95 p-3 text-zinc-200 shadow-2xl backdrop-blur-md pointer-events-auto">
        <label className="block text-[10px] font-extrabold uppercase tracking-wider text-teal-300">Município</label>
        <select
          value={selectedMunicipio}
          onChange={(e) => onMunicipioChange(e.target.value)}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-bold"
        >
          {municipalities.map((m) => (
            <option key={m.codigo_ibge} value={m.codigo_ibge}>{m.nome} - {m.uf}</option>
          ))}
        </select>
        <label className="block text-[10px] font-extrabold uppercase text-zinc-400">
          Exagero vertical: {verticalExaggeration.toFixed(1)}×
        </label>
        <input type="range" min={1} max={8} step={0.5} value={verticalExaggeration}
          onChange={(e) => onVerticalExaggerationChange(Number(e.target.value))} className="w-full accent-teal-500" />
        <label className="block text-[10px] font-extrabold uppercase text-zinc-400">Chuva simulada: {floodLevel} mm</label>
        <input type="range" min={0} max={200} step={10} value={floodLevel}
          onChange={(e) => onFloodLevelChange(Number(e.target.value))} className="w-full accent-sky-500" />
        {terrain?.stats && (
          <p className="text-[10px] text-zinc-500">
            {terrain.dem_source}<br />
            Alt. {terrain.stats.altitude_min_m}–{terrain.stats.altitude_max_m} m · encosta {terrain.stats.suscetibilidade_alta_pct}%
          </p>
        )}
      </div>

      {(loading || processing || !deckReady) && (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-zinc-950/85 text-sm text-zinc-300">
          {processing ? 'Gerando malha 3D...' : !deckReady ? 'Carregando deck.gl...' : 'Carregando terreno...'}
        </div>
      )}
      {error && !loading && (
        <div className="absolute inset-0 z-[1000] flex flex-col items-center justify-center gap-3 bg-zinc-950/90 pointer-events-auto">
          <p className="text-sm text-rose-200 px-6 text-center">{error}</p>
          <button type="button" onClick={loadTerrain} className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-bold text-white">
            Reprocessar DEM
          </button>
        </div>
      )}
    </div>
  );
}
