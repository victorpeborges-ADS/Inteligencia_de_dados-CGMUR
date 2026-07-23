'use client';

import { useEffect, useRef, useState } from 'react';
import { Droplets, Thermometer, MapPin, Radio, Play, Sun, Landmark, Camera, Video, Ruler } from 'lucide-react';
import { exportMapLibrePng, exportMapLibreWebm } from '@/utils/exportMapScene';
import { api } from '@/utils/api';
import {
  syncThematicLayers,
  syncLiveSensorsOverlay,
  syncCriticalPoisOverlay,
  syncUrbanContextOverlay,
  clearEdificacoesMvt,
  pulseLiveSensorsHalo,
  setInspectMarker,
  clearInspectMarker,
  simulationLayerIds,
} from './maplibreLayers';
import ActiveLayersPanel from './ActiveLayersPanel';
import Map3DNavAssist from './Map3DNavAssist';
import MapHudControls, { metersPerPixel, niceScaleMeters } from './MapHudControls';
import { buildInspectResult, formatElevation, type FloodInspectResult } from '@/utils/floodInspect';
import { MAPLIBRE_BASEMAPS } from '@/config/theme';
import { useAppStore } from '@/stores/useAppStore';
import { useAlertWebSocket } from '@/hooks/useAlertWebSocket';
import type { ContingencyMapOverlay } from '@/utils/contingencyGeo';
import { type CriticalPoisGeoJSON, type LiveSensorsGeoJSON, type UrbanContextGeoJSON } from '@/utils/api';
import {
  computeSceneLighting,
  presetDefaultHour,
  type WeatherPresetId,
} from '@/utils/solarPosition';

type BasemapId = 'satellite' | 'dark' | 'light';
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
  simOverlays?: { showFlood: boolean; showContours: boolean; showFlow: boolean };
  contingencyOverlay?: ContingencyMapOverlay | null;
  showContingencyOnMap?: boolean;
  selectedMunicipio: string;
  mapFocus: [number, number];
  simulating?: boolean;
  focusMode?: boolean;
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
    tiles: MAPLIBRE_BASEMAPS.dark.tiles,
    attribution: MAPLIBRE_BASEMAPS.dark.attribution,
  },
  light: {
    tiles: MAPLIBRE_BASEMAPS.light.tiles,
    attribution: MAPLIBRE_BASEMAPS.light.attribution,
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
    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
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

/** Aplica iluminação solar + presets climáticos no céu, light e hillshade (17f.1 / 17f.2). */
function applySceneAtmosphere(
  map: MapLibreMap,
  lat: number,
  lon: number,
  hourOfDay: number,
  preset: WeatherPresetId,
) {
  const L = computeSceneLighting(lat, lon, hourOfDay, preset);
  addSkyLayer(map);
  try {
    map.setPaintProperty('sky', 'sky-atmosphere-sun', [L.sunAzimuth, L.sunPolar]);
    map.setPaintProperty('sky', 'sky-atmosphere-sun-intensity', L.sunIntensity);
  } catch {
    /* sky may be mid-transition */
  }
  try {
    map.setLight({
      anchor: 'map',
      color: L.lightColor,
      intensity: L.lightIntensity,
      position: L.lightPosition,
    });
  } catch {
    /* ignore */
  }
  try {
    if (map.getLayer('hillshade')) {
      map.setPaintProperty('hillshade', 'hillshade-exaggeration', L.hillshadeExaggeration);
    }
    if (map.getLayer('basemap')) {
      map.setPaintProperty('basemap', 'raster-brightness-max', L.basemapBrightness);
      map.setPaintProperty('basemap', 'raster-opacity', Math.min(1, 0.75 + L.basemapBrightness * 0.25));
    }
  } catch {
    /* ignore */
  }
  return L;
}

const WEATHER_PRESETS: { id: WeatherPresetId; label: string }[] = [
  { id: 'dia', label: 'Dia' },
  { id: 'entardecer', label: 'Entardecer' },
  { id: 'noite', label: 'Noite' },
  { id: 'chuva', label: 'Chuva' },
];

export default function Map3DMapLibreContainer({
  activeLayers,
  simGeoJSON,
  simContours,
  simFlowPaths,
  simOverlays = { showFlood: true, showContours: true, showFlow: true },
  contingencyOverlay = null,
  showContingencyOnMap = true,
  selectedMunicipio,
  mapFocus,
  simulating = false,
  focusMode = false,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const mapDivRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const layerDataRef = useRef<Record<string, any>>({});
  const activeLayersRef = useRef<string[]>(activeLayers);
  const simGeoJSONRef = useRef<any>(simGeoJSON);
  const simContoursRef = useRef<any>(simContours);
  const simFlowPathsRef = useRef<any>(simFlowPaths);
  const simOverlaysRef = useRef(simOverlays);
  const contingencyRef = useRef(
    showContingencyOnMap && contingencyOverlay
      ? {
          zonas: contingencyOverlay.zonas,
          rotas: contingencyOverlay.rotas,
          pontos: contingencyOverlay.pontos,
        }
      : null,
  );

  const layerOpacityById = useAppStore((s) => s.layerOpacityById);
  const layerOptions = useAppStore((s) => s.layerOptions);
  const setLayerOpacity = useAppStore((s) => s.setLayerOpacity);
  const moveActiveLayer = useAppStore((s) => s.moveActiveLayer);
  const toggleLayer = useAppStore((s) => s.toggleLayer);
  const layerOpacityRef = useRef(layerOpacityById);
  const [basemap, setBasemap] = useState<BasemapId>('satellite');
  const [exaggeration, setExaggeration] = useState(1.8);
  const [pitch, setPitch] = useState(62);
  const [bearing, setBearing] = useState(-24);
  const [scaleLabel, setScaleLabel] = useState('100 m');
  const [libReady, setLibReady] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [layerData, setLayerData] = useState<Record<string, any>>({});
  const [layersLoading, setLayersLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inspect, setInspect] = useState<FloodInspectResult | null>(null);
  const [showLiveSensors, setShowLiveSensors] = useState(true);
  const [liveSensors, setLiveSensors] = useState<LiveSensorsGeoJSON | null>(null);
  const [liveSensorsTick, setLiveSensorsTick] = useState(0);
  const [showCriticalPois, setShowCriticalPois] = useState(false);
  const [criticalPois, setCriticalPois] = useState<CriticalPoisGeoJSON | null>(null);
  const [ctxHidrografia, setCtxHidrografia] = useState(false);
  const [ctxVias, setCtxVias] = useState(false);
  const [ctxCurvas, setCtxCurvas] = useState(false);
  const [urbanContext, setUrbanContext] = useState<UrbanContextGeoJSON | null>(null);
  const [urbanCtxOpacity, setUrbanCtxOpacity] = useState(0.85);
  const [tourRunning, setTourRunning] = useState(false);
  const [solarHour, setSolarHour] = useState(12);
  const [weatherPreset, setWeatherPreset] = useState<WeatherPresetId>('dia');
  const [lightingLabel, setLightingLabel] = useState('Dia claro');
  const [exporting, setExporting] = useState(false);
  const [profileMode, setProfileMode] = useState(false);
  const [profilePoints, setProfilePoints] = useState<[number, number][]>([]);
  const [profileData, setProfileData] = useState<{
    length_m: number;
    elevation_min_m: number | null;
    elevation_max_m: number | null;
    water_level_m: number | null;
    points: Array<{ distance_m: number; elevation_m: number | null; below_water?: boolean }>;
  } | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const showLiveSensorsRef = useRef(true);
  const liveSensorsRef = useRef<LiveSensorsGeoJSON | null>(null);
  const showCriticalPoisRef = useRef(false);
  const criticalPoisRef = useRef<CriticalPoisGeoJSON | null>(null);
  const urbanContextRef = useRef<UrbanContextGeoJSON | null>(null);
  const urbanCtxVisibleRef = useRef(false);
  const urbanCtxOpacityRef = useRef(0.85);
  const tourCancelRef = useRef(false);
  const profileModeRef = useRef(false);
  const profilePointsRef = useRef<[number, number][]>([]);
  const showUrbanContext = ctxHidrografia || ctxVias || ctxCurvas;
  profileModeRef.current = profileMode;
  profilePointsRef.current = profilePoints;
  const hasSimulation = Boolean(simGeoJSON?.features?.length) && simOverlays.showFlood;
  const isHeatSim =
    simGeoJSON?.features?.some(
      (f: { properties?: { temp_increase_celsius?: number } }) =>
        f.properties?.temp_increase_celsius != null,
    ) ?? false;

  activeLayersRef.current = activeLayers;
  simGeoJSONRef.current = simGeoJSON;
  simContoursRef.current = simContours;
  simFlowPathsRef.current = simFlowPaths;
  simOverlaysRef.current = simOverlays;
  showLiveSensorsRef.current = showLiveSensors;
  liveSensorsRef.current = liveSensors;
  showCriticalPoisRef.current = showCriticalPois;
  criticalPoisRef.current = criticalPois;
  urbanContextRef.current = urbanContext;
  urbanCtxVisibleRef.current = showUrbanContext;
  urbanCtxOpacityRef.current = urbanCtxOpacity;
  contingencyRef.current =
    showContingencyOnMap && contingencyOverlay
      ? {
          zonas: contingencyOverlay.zonas,
          rotas: contingencyOverlay.rotas,
          pontos: contingencyOverlay.pontos,
        }
      : null;
  layerDataRef.current = layerData;
  layerOpacityRef.current = layerOpacityById;

  const applyThematicLayers = (map: MapLibreMap) => {
    syncThematicLayers(
      map,
      activeLayersRef.current.filter((id) => id !== 'edificacoes'),
      layerDataRef.current,
      simGeoJSONRef.current,
      simContoursRef.current,
      simFlowPathsRef.current,
      {
        layerOpacityById: layerOpacityRef.current,
        simOverlays: simOverlaysRef.current,
        contingency: contingencyRef.current,
      },
    );
    clearEdificacoesMvt(map);
    syncLiveSensorsOverlay(map, liveSensorsRef.current, showLiveSensorsRef.current);
    syncCriticalPoisOverlay(map, criticalPoisRef.current, showCriticalPoisRef.current);
    syncUrbanContextOverlay(
      map,
      urbanContextRef.current,
      urbanCtxVisibleRef.current,
      urbanCtxOpacityRef.current,
    );
  };

  useEffect(() => {
    if (!selectedMunicipio) {
      setLiveSensors(null);
      return;
    }
    let cancelled = false;
    api
      .getLiveSensors3D(selectedMunicipio, { includeInmet: true })
      .then((data) => {
        if (!cancelled) setLiveSensors(data);
      })
      .catch(() => {
        if (!cancelled) setLiveSensors(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedMunicipio, liveSensorsTick]);

  useEffect(() => {
    if (!selectedMunicipio || !showCriticalPois) {
      if (!showCriticalPois) setCriticalPois(null);
      return;
    }
    let cancelled = false;
    api
      .getCriticalPois3D(selectedMunicipio)
      .then((data) => {
        if (!cancelled) setCriticalPois(data);
      })
      .catch(() => {
        if (!cancelled) setCriticalPois(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedMunicipio, showCriticalPois]);

  useEffect(() => {
    if (!selectedMunicipio || !showUrbanContext) {
      if (!showUrbanContext) setUrbanContext(null);
      return;
    }
    let cancelled = false;
    api
      .getUrbanContext3D(selectedMunicipio, {
        hidrografia: ctxHidrografia,
        vias: ctxVias,
        curvas: ctxCurvas,
      })
      .then((data) => {
        if (!cancelled) setUrbanContext(data);
      })
      .catch(() => {
        if (!cancelled) setUrbanContext(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedMunicipio, showUrbanContext, ctxHidrografia, ctxVias, ctxCurvas]);

  useAlertWebSocket(selectedMunicipio, () => {
    setLiveSensorsTick((t) => t + 1);
    if (activeLayersRef.current.includes('alertas')) {
      api
        .getLayerGeoJSON('alertas', selectedMunicipio)
        .then((data) => {
          setLayerData((prev) => ({ ...prev, alertas: data }));
        })
        .catch(() => undefined);
    }
  });

  useEffect(() => {
    return () => {
      tourCancelRef.current = true;
    };
  }, []);

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
      activeLayers
        .filter((layerName) => layerName !== 'edificacoes')
        .map(async (layerName) => {
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
        preserveDrawingBuffer: true, // 17f.9 — export PNG/WebM
      });

      map.addControl(new ml.NavigationControl({ visualizePitch: true }), 'top-left');
      map.addControl(new ml.ScaleControl({ maxWidth: 100, unit: 'metric' }), 'bottom-left');

      const syncHud = () => {
        if (!map) return;
        setBearing(map.getBearing());
        setPitch(Math.round(map.getPitch()));
        const c = map.getCenter();
        const z = map.getZoom();
        const mpp = metersPerPixel(c.lat, z);
        setScaleLabel(niceScaleMeters(mpp).label);
      };
      map.on('move', syncHud);
      map.on('zoom', syncHud);
      map.on('rotate', syncHud);
      map.on('pitch', syncHud);

      map.on('load', () => {
        if (cancelled || !map) return;
        map.resize();
        addSkyLayer(map);
        const [lat0, lon0] = mapFocus;
        const lit = applySceneAtmosphere(map, lat0, lon0, solarHour, weatherPreset);
        setLightingLabel(lit.label);
        applyThematicLayers(map);
        syncHud();
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
  }, [
    mapReady,
    layerData,
    activeLayers,
    selectedMunicipio,
    simGeoJSON,
    simContours,
    simFlowPaths,
    simOverlays,
    layerOpacityById,
    contingencyOverlay,
    showContingencyOnMap,
    liveSensors,
    showLiveSensors,
    criticalPois,
    showCriticalPois,
    urbanContext,
    showUrbanContext,
    urbanCtxOpacity,
  ]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !showLiveSensors || !liveSensors?.features?.length) return;
    let raf = 0;
    const tick = (t: number) => {
      pulseLiveSensorsHalo(map, t);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [mapReady, showLiveSensors, liveSensors]);

  const runPresentationTour = () => {
    const map = mapRef.current;
    if (!map || tourRunning) return;
    tourCancelRef.current = false;
    setTourRunning(true);
    setShowLiveSensors(true);

    const center = map.getCenter();
    const steps: Array<{ center?: [number, number]; zoom: number; pitch: number; bearing: number; duration: number }> = [
      { zoom: 12.2, pitch: 45, bearing: -10, duration: 2200 },
      { zoom: 13.6, pitch: 62, bearing: -40, duration: 2800 },
      { zoom: 14.4, pitch: 70, bearing: 20, duration: 2800 },
      { zoom: 13.2, pitch: 58, bearing: -24, duration: 2200 },
    ];

    const sensor = liveSensors?.features?.[0]?.geometry?.coordinates;
    if (sensor && sensor.length >= 2) {
      steps.splice(2, 0, {
        center: [sensor[0], sensor[1]],
        zoom: 14.8,
        pitch: 68,
        bearing: -55,
        duration: 2600,
      });
    }

    let i = 0;
    const next = () => {
      if (tourCancelRef.current || !mapRef.current) {
        setTourRunning(false);
        return;
      }
      if (i >= steps.length) {
        setTourRunning(false);
        return;
      }
      const step = steps[i++];
      mapRef.current.easeTo({
        center: step.center || [center.lng, center.lat],
        zoom: step.zoom,
        pitch: step.pitch,
        bearing: step.bearing,
        duration: step.duration,
        essential: true,
      });
      window.setTimeout(next, step.duration + 200);
    };
    next();
  };

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !hasSimulation) return;

    const bounds = boundsFromGeoJSON(simGeoJSON);
    if (bounds) {
      map.fitBounds(bounds, {
        padding: { top: 80, bottom: 120, left: 64, right: 320 },
        maxZoom: 15,
        pitch: 68,
        bearing: -28,
        duration: 1600,
      });
    } else {
      map.easeTo({ pitch: 68, duration: 1200 });
    }
  }, [simGeoJSON, mapReady, hasSimulation]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    const onClick = (e: any) => {
      if (profileModeRef.current) {
        const pt: [number, number] = [e.lngLat.lng, e.lngLat.lat];
        const next = [...profilePointsRef.current, pt].slice(-2);
        setProfilePoints(next);
        setInspectMarker(map, pt[0], pt[1]);
        if (next.length === 2) {
          setProfileLoading(true);
          api
            .getTerrainProfile(selectedMunicipio, {
              coordinates: next,
              samples: 80,
            })
            .then((data) => setProfileData(data))
            .catch(() => setProfileData(null))
            .finally(() => setProfileLoading(false));
        } else {
          setProfileData(null);
        }
        return;
      }

      const layers = simulationLayerIds().filter((id) => map.getLayer(id));
      const hits = layers.length
        ? map.queryRenderedFeatures(e.point, { layers })
        : [];
      const props = hits[0]?.properties ?? null;

      let ground: number | null = null;
      try {
        if (typeof map.queryTerrainElevation === 'function') {
          ground = map.queryTerrainElevation(e.lngLat);
        }
      } catch {
        ground = null;
      }

      const result = buildInspectResult(e.lngLat.lat, e.lngLat.lng, props, ground);
      setInspect(result);
      setInspectMarker(map, e.lngLat.lng, e.lngLat.lat);
    };

    map.on('click', onClick);
    map.getCanvas().style.cursor =
      profileMode || hasSimulation ? 'crosshair' : '';

    return () => {
      map.off('click', onClick);
      map.getCanvas().style.cursor = '';
    };
  }, [mapReady, hasSimulation, profileMode, selectedMunicipio]);

  useEffect(() => {
    if (!hasSimulation) {
      setInspect(null);
      const map = mapRef.current;
      if (map && mapReady) clearInspectMarker(map);
    }
  }, [hasSimulation, mapReady]);

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
      const [lat0, lon0] = mapFocus;
      const lit = applySceneAtmosphere(map, lat0, lon0, solarHour, weatherPreset);
      setLightingLabel(lit.label);
      applyThematicLayers(map);
    });
  }, [basemap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const [lat0, lon0] = mapFocus;
    const lit = applySceneAtmosphere(map, lat0, lon0, solarHour, weatherPreset);
    setLightingLabel(lit.label);
  }, [mapReady, mapFocus, solarHour, weatherPreset]);

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

      {!focusMode && (
      <ActiveLayersPanel
        className="pointer-events-auto absolute left-4 top-24 z-10 w-64"
        activeLayers={activeLayers}
        layerOptions={layerOptions}
        layerOpacityById={layerOpacityById}
        setLayerOpacity={setLayerOpacity}
        moveActiveLayer={moveActiveLayer}
        toggleLayer={toggleLayer}
      />
      )}

      {!focusMode && mapReady && (
        <Map3DNavAssist
          className="pointer-events-auto absolute left-4 top-[22.5rem] z-10 w-64"
          map={mapRef.current}
          mapReady={mapReady}
          selectedMunicipio={selectedMunicipio}
          mapFocus={mapFocus}
          bearing={bearing}
        />
      )}

      {!focusMode && (
      <div className="map-ui-chrome absolute right-4 top-24 z-10 w-52 rounded-xl border border-teal-500/30 bg-zinc-950/95 p-3 shadow-2xl backdrop-blur-md transition-opacity duration-300">
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
          <button
            type="button"
            onClick={() => setBasemap('light')}
            className={`flex-1 rounded-lg py-2 text-[10px] font-bold uppercase ${
              basemap === 'light'
                ? 'bg-teal-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Claro
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

        <label className="mt-3 block text-[10px] font-extrabold uppercase text-zinc-500">
          <span className="inline-flex items-center gap-1">
            <Sun size={11} className="text-amber-300" />
            Hora solar: {String(Math.floor(solarHour)).padStart(2, '0')}:
            {String(Math.round((solarHour % 1) * 60)).padStart(2, '0')}
          </span>
        </label>
        <input
          type="range"
          min={0}
          max={23.5}
          step={0.5}
          value={solarHour}
          onChange={(e) => setSolarHour(Number(e.target.value))}
          className="w-full accent-amber-400"
          title="Iluminação solar por hora do dia (17f.1)"
        />
        <p className="mt-1 text-[9px] leading-snug text-zinc-500">{lightingLabel}</p>

        <p className="mb-1.5 mt-3 text-[10px] font-extrabold uppercase text-zinc-500">Clima / hora</p>
        <div className="grid grid-cols-2 gap-1">
          {WEATHER_PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => {
                setWeatherPreset(p.id);
                setSolarHour(presetDefaultHour(p.id));
              }}
              className={`rounded-lg py-1.5 text-[9px] font-bold uppercase ${
                weatherPreset === p.id
                  ? 'bg-amber-600 text-white'
                  : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
              title="Preset visual dia/noite/clima (17f.2)"
            >
              {p.label}
            </button>
          ))}
        </div>

        <p className="mt-3 text-[9px] leading-snug text-zinc-600">
          {activeLayers.length} camada(s) · clique na mancha para ver profundidade
        </p>

        <div className="mt-3 border-t border-zinc-800 pt-3">
          <button
            type="button"
            onClick={() => setShowLiveSensors((v) => !v)}
            className={`flex w-full items-center justify-between rounded-lg border px-2.5 py-2 text-left transition-colors ${
              showLiveSensors
                ? 'border-rose-500/40 bg-rose-500/15 text-rose-100'
                : 'border-zinc-700 bg-zinc-900 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Alertas CEMADEN e estações em tempo real (17e.3)"
          >
            <span className="flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wider">
              <Radio size={12} className={showLiveSensors && liveSensors?.meta?.vivo ? 'animate-pulse' : undefined} />
              Sensores vivos
            </span>
            <span className="text-[9px] font-bold tabular-nums text-zinc-400">
              {liveSensors?.meta?.count ?? 0}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setShowCriticalPois((v) => !v)}
            className={`mt-1.5 flex w-full items-center justify-between rounded-lg border px-2.5 py-2 text-left transition-colors ${
              showCriticalPois
                ? 'border-sky-500/40 bg-sky-500/15 text-sky-100'
                : 'border-zinc-700 bg-zinc-900 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Escolas INEP, saúde CNES e abrigos (17f.3)"
          >
            <span className="flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wider">
              <Landmark size={12} />
              POIs críticos
            </span>
            <span className="text-[9px] font-bold tabular-nums text-zinc-400">
              {criticalPois?.meta?.count ?? (showCriticalPois ? '…' : 'off')}
            </span>
          </button>
          {showCriticalPois && criticalPois?.meta?.por_categoria && (
            <p className="mt-1 text-[9px] leading-snug text-zinc-500">
              {criticalPois.meta.por_categoria.escola ?? 0} escolas ·{' '}
              {criticalPois.meta.por_categoria.saude ?? 0} saúde ·{' '}
              {criticalPois.meta.por_categoria.abrigo ?? 0} abrigos
            </p>
          )}

          <p className="mb-1.5 mt-3 text-[10px] font-extrabold uppercase text-zinc-500">
            Contexto urbano
          </p>
          <div className="grid grid-cols-3 gap-1">
            {(
              [
                { id: 'hidro' as const, label: 'Água', on: ctxHidrografia, set: setCtxHidrografia },
                { id: 'vias' as const, label: 'Vias', on: ctxVias, set: setCtxVias },
                { id: 'curvas' as const, label: 'Curvas', on: ctxCurvas, set: setCtxCurvas },
              ] as const
            ).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => item.set((v) => !v)}
                className={`rounded-lg py-1.5 text-[9px] font-bold uppercase ${
                  item.on
                    ? 'bg-cyan-600 text-white'
                    : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                }`}
                title="Hidrografia, vias e curvas de nível (17f.6)"
              >
                {item.label}
              </button>
            ))}
          </div>
          {showUrbanContext && (
            <>
              <label className="mt-2 block text-[9px] font-bold uppercase text-zinc-500">
                Opacidade: {Math.round(urbanCtxOpacity * 100)}%
              </label>
              <input
                type="range"
                min={0.15}
                max={1}
                step={0.05}
                value={urbanCtxOpacity}
                onChange={(e) => setUrbanCtxOpacity(Number(e.target.value))}
                className="w-full accent-cyan-500"
              />
              {urbanContext?.meta?.por_contexto && (
                <p className="mt-1 text-[9px] leading-snug text-zinc-500">
                  {urbanContext.meta.por_contexto.hidrografia ?? 0} água ·{' '}
                  {urbanContext.meta.por_contexto.via ?? 0} vias ·{' '}
                  {urbanContext.meta.por_contexto.curva ?? 0} curvas
                </p>
              )}
            </>
          )}

          {showLiveSensors && liveSensors?.meta && (
            <p className="mt-1.5 text-[9px] leading-snug text-zinc-500">
              {liveSensors.meta.vivo ? (
                <>
                  Nível {liveSensors.meta.nivel_alerta}
                  {liveSensors.meta.titulo_recente ? ` · ${liveSensors.meta.titulo_recente}` : ''}
                </>
              ) : (
                'Sem alerta ativo nas últimas 24h'
              )}
            </p>
          )}
          <button
            type="button"
            onClick={() => {
              if (tourRunning) {
                tourCancelRef.current = true;
                setTourRunning(false);
                return;
              }
              runPresentationTour();
            }}
            className={`mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border px-2.5 py-2 text-[10px] font-extrabold uppercase tracking-wider transition-colors ${
              tourRunning
                ? 'border-amber-500/40 bg-amber-500/15 text-amber-100'
                : 'border-teal-500/30 bg-teal-500/10 text-teal-200 hover:bg-teal-500/20'
            }`}
            title="Tour de câmera para demo institucional (17e.5)"
          >
            <Play size={12} />
            {tourRunning ? 'Parar tour' : 'Tour apresentação'}
          </button>

          <p className="mb-1.5 mt-3 text-[10px] font-extrabold uppercase text-zinc-500">
            Exportar / perfil
          </p>
          <div className="grid grid-cols-3 gap-1">
            <button
              type="button"
              disabled={exporting || !mapReady}
              onClick={async () => {
                const map = mapRef.current;
                if (!map) return;
                setExporting(true);
                try {
                  await exportMapLibrePng(
                    map,
                    `sinidu-${selectedMunicipio}-cena.png`,
                  );
                } catch {
                  /* ignore */
                } finally {
                  setExporting(false);
                }
              }}
              className="flex items-center justify-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 py-1.5 text-[9px] font-bold uppercase text-zinc-300 hover:text-white disabled:opacity-40"
              title="Exportar PNG da cena 3D (17f.9)"
            >
              <Camera size={11} />
              PNG
            </button>
            <button
              type="button"
              disabled={exporting || !mapReady}
              onClick={async () => {
                const map = mapRef.current;
                if (!map) return;
                setExporting(true);
                try {
                  if (!tourRunning) runPresentationTour();
                  const ok = await exportMapLibreWebm(
                    map,
                    5000,
                    `sinidu-${selectedMunicipio}-tour.webm`,
                  );
                  if (!ok) {
                    await exportMapLibrePng(
                      map,
                      `sinidu-${selectedMunicipio}-cena.png`,
                    );
                  }
                } finally {
                  setExporting(false);
                }
              }}
              className="flex items-center justify-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 py-1.5 text-[9px] font-bold uppercase text-zinc-300 hover:text-white disabled:opacity-40"
              title="Gravar tour curto em vídeo WebM (17f.9)"
            >
              <Video size={11} />
              Vídeo
            </button>
            <button
              type="button"
              onClick={() => {
                setProfileMode((v) => !v);
                setProfilePoints([]);
                setProfileData(null);
              }}
              className={`flex items-center justify-center gap-1 rounded-lg border py-1.5 text-[9px] font-bold uppercase ${
                profileMode
                  ? 'border-lime-500/40 bg-lime-500/15 text-lime-100'
                  : 'border-zinc-700 bg-zinc-900 text-zinc-300 hover:text-white'
              }`}
              title="Seção transversal — clique 2 pontos no mapa (17f.5)"
            >
              <Ruler size={11} />
              Perfil
            </button>
          </div>
          {profileMode && (
            <p className="mt-1.5 text-[9px] leading-snug text-zinc-500">
              {profilePoints.length === 0 && 'Clique o ponto A no mapa…'}
              {profilePoints.length === 1 && 'Clique o ponto B para fechar o corte…'}
              {profileLoading && ' Calculando perfil DEM…'}
            </p>
          )}
          {profileData && profileData.points.length > 0 && (
            <div className="mt-2 rounded-lg border border-lime-500/25 bg-zinc-900/80 p-2">
              <p className="text-[9px] font-bold uppercase text-lime-300">
                Corte · {profileData.length_m} m
              </p>
              <p className="mt-0.5 text-[9px] text-zinc-500">
                Cota {profileData.elevation_min_m ?? '—'}–{profileData.elevation_max_m ?? '—'} m
              </p>
              <svg viewBox="0 0 120 36" className="mt-1 h-10 w-full" preserveAspectRatio="none">
                {(() => {
                  const pts = profileData.points.filter((p) => p.elevation_m != null);
                  if (pts.length < 2) return null;
                  const zs = pts.map((p) => p.elevation_m as number);
                  const zMin = Math.min(...zs);
                  const zMax = Math.max(...zs);
                  const span = zMax - zMin || 1;
                  const d = pts
                    .map((p, i) => {
                      const x = (i / (pts.length - 1)) * 120;
                      const y = 32 - ((p.elevation_m as number) - zMin) / span * 28;
                      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
                    })
                    .join(' ');
                  return (
                    <>
                      <path d={d} fill="none" stroke="#84cc16" strokeWidth="1.5" />
                      {profileData.water_level_m != null && (
                        <line
                          x1="0"
                          x2="120"
                          y1={32 - ((profileData.water_level_m - zMin) / span) * 28}
                          y2={32 - ((profileData.water_level_m - zMin) / span) * 28}
                          stroke="#38bdf8"
                          strokeWidth="1"
                          strokeDasharray="3 2"
                        />
                      )}
                    </>
                  );
                })()}
              </svg>
            </div>
          )}
        </div>
      </div>
      )}

      {!focusMode && (
      <MapHudControls
        className="absolute bottom-6 right-4 z-20"
        bearing={bearing}
        scaleLabel={scaleLabel}
        activeLayers={activeLayers}
        layerOptions={layerOptions}
        hasSimulation={hasSimulation}
        showLiveSensors={showLiveSensors && Boolean(liveSensors?.features?.length)}
        showCriticalPois={showCriticalPois && Boolean(criticalPois?.features?.length)}
        showUrbanContext={showUrbanContext && Boolean(urbanContext?.features?.length)}
        onResetNorth={() => {
          const map = mapRef.current;
          if (!map) return;
          map.easeTo({ bearing: 0, duration: 600 });
        }}
      />
      )}

      {showContingencyOnMap && contingencyOverlay && !focusMode && (
        <div className="map-ui-chrome absolute bottom-6 left-6 z-10 rounded-xl border border-orange-500/40 bg-zinc-950/95 px-3 py-2 text-[10px] text-orange-100 shadow-lg backdrop-blur-md">
          <p className="font-extrabold uppercase tracking-wider text-orange-300">Plano ativo no mapa</p>
          <p className="mt-0.5 text-zinc-400">
            {contingencyOverlay.cenario} · {contingencyOverlay.nivel} ·{' '}
            {contingencyOverlay.zonas.features.length} zona(s)
          </p>
        </div>
      )}

      {hasSimulation && !focusMode && (
        <div className={`map-ui-chrome absolute z-10 max-w-sm rounded-xl border border-sky-500/40 bg-zinc-950/95 p-4 shadow-2xl backdrop-blur-md transition-opacity duration-300 ${
          showContingencyOnMap && contingencyOverlay ? 'bottom-24 left-6' : 'bottom-6 left-6'
        }`}>
          <p className="flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wider text-sky-300">
            {isHeatSim ? (
              <>
                <Thermometer size={12} /> Simulação 3D — ilha de calor
              </>
            ) : (
              <>
                <Droplets size={12} /> Simulação 3D — volume de água
              </>
            )}
          </p>
          <p className="mt-1 text-[10px] leading-relaxed text-zinc-400">
            {isHeatSim
              ? 'Colunas vermelhas = aumento térmico estimado. Clique na mancha para ver o delta no ponto.'
              : 'Barras azuis = profundidade estimada (DEM SRTM 30 m). Clique em uma mancha para ver cota e altura da água no ponto.'}
          </p>
          {simulating && (
            <p className="mt-2 animate-pulse text-[10px] text-sky-200">Calculando manchas…</p>
          )}
          {inspect && (
            <div className="mt-3 space-y-2 border-t border-zinc-800 pt-3 text-[11px]">
              <p className="flex items-center gap-1 text-zinc-500">
                <MapPin size={11} />
                {inspect.lat.toFixed(5)}, {inspect.lng.toFixed(5)}
              </p>
              {inspect.scenario === 'flood' && inspect.inFlood && (
                <>
                  <p className="text-lg font-black text-sky-300">
                    +{inspect.depthCm} cm <span className="text-sm font-semibold text-zinc-400">de água</span>
                  </p>
                  <p className="text-zinc-300">{inspect.bandLabel}</p>
                  <p className="text-zinc-500">
                    Solo ~{formatElevation(inspect.groundElevationM)} · Cota da água ~{formatElevation(inspect.waterSurfaceM)}
                  </p>
                  {inspect.precipitationMm != null && (
                    <p className="text-zinc-500">Cenário: {inspect.precipitationMm} mm de chuva</p>
                  )}
                </>
              )}
              {inspect.scenario === 'heat' && inspect.tempIncreaseC != null && (
                <p className="flex items-center gap-1 text-rose-300">
                  <Thermometer size={14} />
                  +{inspect.tempIncreaseC}°C estimado (ilha de calor)
                </p>
              )}
              {inspect.scenario === 'none' && (
                <p className="text-zinc-400">
                  Sem alagamento neste ponto
                  {inspect.groundElevationM != null && ` · solo ~${formatElevation(inspect.groundElevationM)}`}
                </p>
              )}
            </div>
          )}
          {!inspect && !simulating && (
            <p className="mt-2 text-[10px] italic text-zinc-500">Clique no mapa para inspecionar um ponto</p>
          )}
          {!isHeatSim && (
            <div className="mt-3 flex flex-wrap gap-2 border-t border-zinc-800 pt-3 text-[9px]">
              <span className="rounded border border-sky-700/40 bg-sky-900/40 px-2 py-0.5 text-sky-200">Superficial &lt;35 cm</span>
              <span className="rounded border border-indigo-700/40 bg-indigo-900/40 px-2 py-0.5 text-indigo-200">Moderada 35–80 cm</span>
              <span className="rounded border border-violet-700/40 bg-violet-900/40 px-2 py-0.5 text-violet-200">Crítica &gt;80 cm</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
