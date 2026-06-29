'use client';

import { useEffect, useRef, useState } from 'react';
import { api } from '@/utils/api';
import { syncThematicLayers } from './maplibreLayers';

type BasemapId = 'satellite' | 'dark';
type MapLibreMap = any;

const MAPLIBRE_VERSION = '4.7.1';
const MAPLIBRE_CSS = `https://cdn.jsdelivr.net/npm/maplibre-gl@${MAPLIBRE_VERSION}/dist/maplibre-gl.css`;
const MAPLIBRE_JS = `https://cdn.jsdelivr.net/npm/maplibre-gl@${MAPLIBRE_VERSION}/dist/maplibre-gl.js`;

const TERRAIN_TILES =
  'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';

interface Props {
  activeLayers: string[];
  simGeoJSON: any;
  simContours?: any;
  simFlowPaths?: any;
  selectedMunicipio: string;
  mapFocus: [number, number];
}

declare global {
  interface Window {
    maplibregl?: any;
    __maplibreLoading?: Promise<any>;
  }
}

const BASEMAPS: Record<BasemapId, { tiles: string[]; attribution: string }> = {
  satellite: {
    tiles: [
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    ],
    attribution: 'Esri, Maxar, Earthstar Geographics',
  },
  dark: {
    tiles: ['https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'],
    attribution: '© OpenStreetMap © CARTO',
  },
};

function loadMapLibre(): Promise<any> {
  if (typeof window === 'undefined') return Promise.reject(new Error('SSR'));
  if (window.maplibregl) return Promise.resolve(window.maplibregl);
  if (window.__maplibreLoading) return window.__maplibreLoading;

  window.__maplibreLoading = new Promise((resolve, reject) => {
    if (!document.querySelector('link[data-maplibre-css]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = MAPLIBRE_CSS;
      link.setAttribute('data-maplibre-css', '1');
      document.head.appendChild(link);
    }

    const script = document.createElement('script');
    script.src = MAPLIBRE_JS;
    script.async = true;
    script.onload = () => {
      if (window.maplibregl) resolve(window.maplibregl);
      else reject(new Error('maplibre-gl'));
    };
    script.onerror = () => reject(new Error('CDN maplibre-gl'));
    document.head.appendChild(script);
  });

  return window.__maplibreLoading;
}

function waitForElementSize(el: HTMLElement): Promise<void> {
  return new Promise((resolve) => {
    const tick = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 32 && height > 32) {
        resolve();
        return;
      }
      requestAnimationFrame(tick);
    };
    tick();
  });
}

function buildStyle(basemap: BasemapId, exaggeration: number) {
  const bm = BASEMAPS[basemap];
  return {
    version: 8,
    sources: {
      basemap: {
        type: 'raster',
        tiles: bm.tiles,
        tileSize: 256,
        attribution: bm.attribution,
        maxzoom: 19,
      },
      terrain: {
        type: 'raster-dem',
        tiles: [TERRAIN_TILES],
        tileSize: 256,
        encoding: 'terrarium',
        maxzoom: 15,
      },
    },
    layers: [
      { id: 'basemap', type: 'raster', source: 'basemap' },
      {
        id: 'hillshade',
        type: 'hillshade',
        source: 'terrain',
        paint: {
          'hillshade-exaggeration': 0.25,
          'hillshade-shadow-color': '#0a0a0f',
          'hillshade-highlight-color': '#ffffff',
          'hillshade-accent-color': '#1e293b',
        },
      },
    ],
    terrain: { source: 'terrain', exaggeration },
  };
}

function boundsFromGeoJSON(
  geojson: { features?: Array<{ geometry?: { coordinates?: unknown } }> },
): [[number, number], [number, number]] | null {
  let minLng = Infinity;
  let minLat = Infinity;
  let maxLng = -Infinity;
  let maxLat = -Infinity;

  const visit = (coords: unknown): void => {
    if (!coords) return;
    if (typeof (coords as number[])[0] === 'number') {
      const [lng, lat] = coords as [number, number];
      minLng = Math.min(minLng, lng);
      minLat = Math.min(minLat, lat);
      maxLng = Math.max(maxLng, lng);
      maxLat = Math.max(maxLat, lat);
      return;
    }
    (coords as unknown[]).forEach(visit);
  };

  geojson.features?.forEach((f) => visit(f.geometry?.coordinates));

  if (!Number.isFinite(minLng)) return null;
  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ];
}

function addSkyLayer(map: MapLibreMap) {
  if (map.getLayer('sky')) return;
  map.addLayer({
    id: 'sky',
    type: 'sky',
    paint: {
      'sky-type': 'atmosphere',
      'sky-atmosphere-sun': [0.0, 90.0],
      'sky-atmosphere-sun-intensity': 10,
    },
  });
}

export default function Map3DMapLibreContainer({
  activeLayers,
  simGeoJSON,
  simContours,
  simFlowPaths,
  selectedMunicipio,
  mapFocus,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const mapDivRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const layerDataRef = useRef<Record<string, any>>({});
  const activeLayersRef = useRef<string[]>(activeLayers);
  const simGeoJSONRef = useRef<any>(simGeoJSON);
  const simContoursRef = useRef<any>(simContours);
  const simFlowPathsRef = useRef<any>(simFlowPaths);

  const [basemap, setBasemap] = useState<BasemapId>('satellite');
  const [exaggeration, setExaggeration] = useState(1.8);
  const [pitch, setPitch] = useState(62);
  const [libReady, setLibReady] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [layerData, setLayerData] = useState<Record<string, any>>({});
  const [layersLoading, setLayersLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  activeLayersRef.current = activeLayers;
  simGeoJSONRef.current = simGeoJSON;
  simContoursRef.current = simContours;
  simFlowPathsRef.current = simFlowPaths;
  layerDataRef.current = layerData;

  const applyThematicLayers = (map: MapLibreMap) => {
    syncThematicLayers(
      map,
      activeLayersRef.current,
      layerDataRef.current,
      simGeoJSONRef.current,
      simContoursRef.current,
      simFlowPathsRef.current,
    );
  };

  useEffect(() => {
    loadMapLibre()
      .then(() => setLibReady(true))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    setLayerData({});

    if (activeLayers.length === 0) {
      return;
    }

    let cancelled = false;
    setLayersLoading(true);

    Promise.all(
      activeLayers.map(async (layerName) => {
        const data = await api.getLayerGeoJSON(layerName, selectedMunicipio);
        return [layerName, data] as const;
      }),
    )
      .then((entries) => {
        if (!cancelled) setLayerData(Object.fromEntries(entries));
      })
      .catch((err) => console.error('Erro ao carregar camadas 3D:', err))
      .finally(() => {
        if (!cancelled) setLayersLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeLayers, selectedMunicipio]);

  useEffect(() => {
    const wrap = wrapRef.current;
    const container = mapDivRef.current;
    if (!libReady || !wrap || !container || mapRef.current || !window.maplibregl) return;

    let cancelled = false;
    let map: MapLibreMap | null = null;
    let ro: ResizeObserver | null = null;

    const init = async () => {
      await waitForElementSize(wrap);
      if (cancelled || !window.maplibregl) return;

      const ml = window.maplibregl;
      const [lat, lng] = mapFocus;

      map = new ml.Map({
        container,
        style: buildStyle('satellite', 1.8),
        center: [lng, lat],
        zoom: 13,
        pitch: 62,
        bearing: -24,
        maxPitch: 85,
        antialias: true,
        attributionControl: true,
      });

      map.addControl(new ml.NavigationControl({ visualizePitch: true }), 'top-left');

      map.on('load', () => {
        if (cancelled || !map) return;
        map.resize();
        addSkyLayer(map);
        applyThematicLayers(map);
        setMapReady(true);
      });

      mapRef.current = map;

      ro = new ResizeObserver(() => {
        map?.resize();
      });
      ro.observe(wrap);
    };

    init().catch((e) => setError(String(e)));

    return () => {
      cancelled = true;
      ro?.disconnect();
      map?.remove();
      mapRef.current = null;
      setMapReady(false);
    };
  }, [libReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    applyThematicLayers(map);
  }, [mapReady, layerData, activeLayers, simGeoJSON, simContours, simFlowPaths]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const boundsLayer = layerData.bairros || layerData.municipio;
    const bounds = boundsLayer ? boundsFromGeoJSON(boundsLayer) : null;
    if (bounds) {
      map.fitBounds(bounds, {
        padding: { top: 56, bottom: 48, left: 48, right: 300 },
        maxZoom: 14,
        pitch,
        duration: 1200,
      });
    }
  }, [selectedMunicipio, layerData.bairros, layerData.municipio, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const [lat, lng] = mapFocus;
    map.easeTo({ center: [lng, lat], duration: 800 });
  }, [mapFocus, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    map.setTerrain({ source: 'terrain', exaggeration });
  }, [exaggeration, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    map.setPitch(pitch);
  }, [pitch, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const style = buildStyle(basemap, exaggeration);
    const center = map.getCenter();
    const zoom = map.getZoom();
    const bearing = map.getBearing();
    const currentPitch = map.getPitch();

    map.setStyle(style);
    map.once('styledata', () => {
      map.setTerrain({ source: 'terrain', exaggeration });
      map.setCenter(center);
      map.setZoom(zoom);
      map.setBearing(bearing);
      map.setPitch(currentPitch);
      map.resize();
      addSkyLayer(map);
      applyThematicLayers(map);
    });
  }, [basemap]);

  if (error) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-zinc-950 p-6 text-sm text-rose-200">
        Erro ao carregar MapLibre: {error}
      </div>
    );
  }

  return (
    <div ref={wrapRef} className="absolute inset-0 z-0">
      <div ref={mapDivRef} className="h-full w-full" />

      {(!libReady || !mapReady || layersLoading) && (
        <div className="absolute inset-0 z-[1] flex items-center justify-center bg-zinc-950/80 text-sm text-zinc-400">
          {!libReady
            ? 'Carregando MapLibre…'
            : !mapReady
              ? 'Inicializando terreno 3D…'
              : 'Carregando camadas de risco…'}
        </div>
      )}

      <div className="absolute right-4 top-24 z-10 w-48 rounded-xl border border-teal-500/30 bg-zinc-950/95 p-3 shadow-2xl backdrop-blur-md">
        <p className="mb-2 text-[10px] font-extrabold uppercase text-teal-300">Basemap</p>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => setBasemap('satellite')}
            className={`flex-1 rounded-lg py-2 text-[10px] font-bold uppercase ${
              basemap === 'satellite'
                ? 'bg-teal-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Satélite
          </button>
          <button
            type="button"
            onClick={() => setBasemap('dark')}
            className={`flex-1 rounded-lg py-2 text-[10px] font-bold uppercase ${
              basemap === 'dark'
                ? 'bg-teal-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Escuro
          </button>
        </div>

        <label className="block text-[10px] font-extrabold uppercase text-zinc-500">
          Relevo: {exaggeration.toFixed(1)}×
        </label>
        <input
          type="range"
          min={1}
          max={4}
          step={0.1}
          value={exaggeration}
          onChange={(e) => setExaggeration(Number(e.target.value))}
          className="w-full accent-teal-500"
        />

        <label className="block text-[10px] font-extrabold uppercase text-zinc-500">
          Inclinação: {pitch}°
        </label>
        <input
          type="range"
          min={0}
          max={75}
          step={1}
          value={pitch}
          onChange={(e) => setPitch(Number(e.target.value))}
          className="w-full accent-teal-500"
        />

        <p className="text-[9px] leading-snug text-zinc-600">
          {activeLayers.length} camada(s) ativa(s) · mesmas manchas do mapa 2D
        </p>
      </div>
    </div>
  );
}
