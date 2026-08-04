'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { MapContainer as LeafletMap, TileLayer, GeoJSON, useMap, useMapEvents } from 'react-leaflet';
import { ChevronDown, ChevronRight, ChevronUp, AlertTriangle, X } from 'lucide-react';
import L from 'leaflet';
import { api } from '@/utils/api';
import { getLayerStyle, getSimulationFeatureStyle } from './layerStyles';
import { getSocioSubcamada, type SocioSubcamadaId } from '@/config/socioeconomicoSubcamadas';
import {
  DEPENDENCIA_COLORS,
  DEPENDENCIA_LABELS,
  EQUIPAMENTO_DEPS_DEFAULT,
  EQUIPAMENTO_TIPOS,
  EQUIPAMENTO_TIPOS_DEFAULT,
  getEducacaoEtapa,
  matchEquipamentoFiltro,
  type DependenciaId,
  type EducacaoEtapaId,
  type EquipamentoTipoId,
} from '@/config/educacaoInep';
import {
  layerTitles,
  createFeaturePopupHandler,
  createPointToLayer,
  buildSimulationFeaturePopup,
  buildRegionalFeaturePopup,
  buildContourTooltip,
} from './mapPopups';
import {
  TERRITORIO_LEGEND,
  getTerritorioTipo,
  type TerritorioTipoId,
} from '@/config/territoriosEspeciais';
import type { LayerOption } from '@/config/platformTabs';
import type { TemporalTemaId } from '@/config/layerTemporal';
import type { RegionalOverlayResponse } from '@/config/regionalContext';
import { useAppStore } from '@/stores/useAppStore';
import { MAP_TILE_URLS, type MapBasemapId } from '@/config/theme';
import type { ContingencyMapOverlay } from '@/utils/contingencyGeo';
import LayerMetaBlock from './LayerMetaBlock';
import RegionalOverlayPanel from './RegionalOverlayPanel';
import ActiveLayersPanel from './ActiveLayersPanel';
import { buildVectorRenderOrder } from '@/utils/activeLayerOrder';
import { MAP_CENTER_LEFT } from '@/config/mapOverlayLayout';
import {
  EXTERNAL_RASTER_LAYER_IDS,
  isExternalRasterLayer,
  RASTER_RESCALE_UI,
  type ExternalRasterId,
} from '@/config/externalRasters';
import { buildLayerFetchParams } from '@/config/layerTemporal';

const LEGEND_PANEL_COLLAPSED_KEY = 'sinidu-legend-panel-collapsed';
const LEGEND_SECTIONS_COLLAPSED_KEY = 'sinidu-legend-sections-collapsed';

type RasterRuntimeConfig = {
  tileUrl: string;
  minZoom: number;
  maxZoom: number;
  attribution: string;
};

// Fix Leaflet marker asset paths
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface MapProps {
  activeLayers: string[];
  mapFocus: [number, number];
  zoom: number;
  simGeoJSON: any;
  simContours?: any;
  simFlowPaths?: any;
  simImpassableRoads?: any;
  simCriticalAssets?: any;
  simOverlays?: {
    showFlood: boolean;
    showContours: boolean;
    showFlow: boolean;
    showImpassableRoads?: boolean;
    showCriticalAssets?: boolean;
  };
  contingencyOverlay?: ContingencyMapOverlay | null;
  showContingencyOnMap?: boolean;
  selectedMunicipio: string;
  simulating?: boolean;
  socioSubcamada?: SocioSubcamadaId;
  layerOptions?: LayerOption[];
  educacaoEtapa?: EducacaoEtapaId;
  educacaoRaioM?: number;
  showEducacaoBuffer?: boolean;
  territorioTipo?: TerritorioTipoId;
  layerAnoByTema?: Partial<Record<TemporalTemaId, number>>;
}

type LegendItem = {
  color: string;
  label: string;
};

const legendByLayer: Record<string, LegendItem[]> = {
  municipio: [{ color: '#38bdf8', label: 'Limite municipal' }],
  bairros: [{ color: '#6366f1', label: 'Malha de bairros' }],
  territorios_especiais: TERRITORIO_LEGEND,
  infraestrutura: [
    ...EQUIPAMENTO_TIPOS.filter((t) => t.id !== 'via').map((t) => ({
      color: t.color,
      label: `${t.short} · ${t.label}`,
    })),
    { color: '#94a3b8', label: 'V · Vias' },
  ],
  educacao: [
    { color: DEPENDENCIA_COLORS.federal, label: 'Federal' },
    { color: DEPENDENCIA_COLORS.estadual, label: 'Estadual' },
    { color: DEPENDENCIA_COLORS.municipal, label: 'Municipal' },
    { color: DEPENDENCIA_COLORS.privada, label: 'Privada' },
  ],
  socioeconomico: [
    { color: '#22c55e', label: 'Renda alta (terço superior)' },
    { color: '#eab308', label: 'Renda média (terço médio)' },
    { color: '#f97316', label: 'Renda baixa (terço inferior)' }
  ],
  cobertura: [
    { color: '#15803d', label: 'Vegetação / parque' },
    { color: '#1e3a8a', label: "Corpo d'água / rios" },
    { color: '#a1a1aa', label: 'Área construída' },
  ],
  vulnerabilidade: [
    { color: '#7f1d1d', label: 'IVC alto' },
    { color: '#f97316', label: 'IVC médio' },
    { color: '#fde047', label: 'IVC baixo' }
  ],
  inundacao: [
    { color: '#075985', label: 'Risco alto' },
    { color: '#0284c7', label: 'Risco médio' },
    { color: '#7dd3fc', label: 'Risco baixo' }
  ],
  hand_suscetibilidade: [
    { color: '#7f1d1d', label: 'HAND < 2 m' },
    { color: '#ea580c', label: 'HAND 2–5 m' },
    { color: '#ca8a04', label: 'HAND 5–10 m' },
    { color: '#a3a3a3', label: 'HAND 10–25 m' },
  ],
  hidrografia_osm: [{ color: '#1d4ed8', label: 'Hidrografia OSM' }],
  hazard_referencia: [
    { color: '#93c5fd', label: 'GloFAS 5–50 cm' },
    { color: '#2563eb', label: 'GloFAS 50–150 cm' },
    { color: '#1e3a8a', label: 'GloFAS > 150 cm' },
  ],
  alertas: [
    { color: '#f43f5e', label: 'Muito alto' },
    { color: '#f97316', label: 'Alto' },
    { color: '#eab308', label: 'Moderado/baixo' }
  ],
  desastres: [{ color: '#ef4444', label: 'Evento S2ID' }],
  saneamento_drenagem: [
    { color: '#0e7490', label: 'Drenagem crítica' },
    { color: '#06b6d4', label: 'Atenção' },
    { color: '#e0f2fe', label: 'Monitoramento' }
  ],
  adaptacao_climatica: [
    { color: '#16a34a', label: 'Capacidade alta' },
    { color: '#facc15', label: 'Capacidade média' },
    { color: '#f97316', label: 'Capacidade baixa' }
  ],
  prioridade_planejamento: [
    { color: '#be123c', label: 'Prioridade alta' },
    { color: '#9333ea', label: 'Prioridade média' },
    { color: '#c4b5fd', label: 'Prioridade baixa' }
  ],
  risco_consolidado: [
    { color: '#dc2626', label: 'Vermelho — crítico' },
    { color: '#ea580c', label: 'Laranja — elevado' },
    { color: '#eab308', label: 'Amarelo — atenção' },
    { color: '#22c55e', label: 'Verde — baixo' },
  ],
  lacunas_dados: [
    { color: '#16a34a', label: 'Maturidade alta' },
    { color: '#f59e0b', label: 'Maturidade média' },
    { color: '#e11d48', label: 'Maturidade baixa' }
  ],
  saude_risco: [
    { color: '#16a34a', label: 'Cobertura adequada' },
    { color: '#eab308', label: 'Atenção' },
    { color: '#ef4444', label: 'Crítica em área de risco' }
  ],
  seguranca_publica: [
    { color: '#7f1d1d', label: 'Alta incidência / 100k hab' },
    { color: '#f97316', label: 'Média' },
    { color: '#fde68a', label: 'Baixa' }
  ],
  vulnerabilidade_multidimensional: [
    { color: '#581c87', label: 'VM crítica + flag multidimensional' },
    { color: '#a855f7', label: 'VM alta' },
    { color: '#e9d5ff', label: 'VM moderada/baixa' }
  ]
};

// Controller to dynamically update map view coordinates and zoom
function MapController({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom, { animate: true, duration: 1.0 });
  }, [center, zoom, map]);
  return null;
}

/** Clique no mapa com LST ativa → amostra temperatura GeoReDUS no ponto. */
function LstPointIdentify({
  enabled,
  codigoIbge,
}: {
  enabled: boolean;
  codigoIbge?: string;
}) {
  const map = useMap();
  const reqId = useRef(0);

  useMapEvents({
    click: (e) => {
      if (!enabled) return;
      const { lat, lng } = e.latlng;
      const id = ++reqId.current;
      map.closePopup();
      const popup = L.popup({
        maxWidth: 300,
        className: 'sinidu-lst-identify-popup',
        autoPan: true,
      })
        .setLatLng(e.latlng)
        .setContent(
          `<div class="p-1 font-sans text-xs min-w-[200px]">
            <p class="mb-1 text-[10px] font-bold uppercase tracking-wide text-orange-300">Temperatura de superfície (LST)</p>
            <p class="text-[11px] text-zinc-300">Consultando mosaico GeoReDUS…</p>
            <p class="mt-1 text-[9px] font-mono text-zinc-500">${lat.toFixed(5)}, ${lng.toFixed(5)}</p>
          </div>`,
        )
        .openOn(map);

      void api
        .sampleLstPoint(lng, lat, codigoIbge)
        .then((data) => {
          if (id !== reqId.current) return;
          if (data.temperatura_c == null || !data.disponivel) {
            popup.setContent(
              `<div class="p-1 font-sans text-xs min-w-[200px]">
                <p class="mb-1 text-[10px] font-bold uppercase tracking-wide text-orange-300">Temperatura de superfície (LST)</p>
                <p class="text-[11px] text-amber-200">Sem valor LST neste ponto</p>
                <p class="mt-1 text-[9px] leading-snug text-zinc-500">${data.nota || ''}</p>
                <p class="mt-1 text-[9px] font-mono text-zinc-500">${lat.toFixed(5)}, ${lng.toFixed(5)}</p>
              </div>`,
            );
            return;
          }
          const temp = data.temperatura_c;
          const tone =
            temp >= 45 ? 'text-rose-300' : temp >= 38 ? 'text-orange-300' : temp >= 32 ? 'text-amber-200' : 'text-sky-200';
          popup.setContent(
            `<div class="p-1 font-sans text-xs min-w-[220px] max-w-[300px]">
              <p class="mb-1 text-[10px] font-bold uppercase tracking-wide text-orange-300">Temperatura de superfície (LST)</p>
              <p class="mb-1 flex items-baseline gap-1.5">
                <span class="text-2xl font-black ${tone}">${temp.toFixed(1)}</span>
                <span class="text-sm font-bold text-zinc-300">${data.unit || '°C'}</span>
              </p>
              <p class="mb-1 text-[11px] text-zinc-300">Temperatura estimada no ponto (pixel do mosaico)</p>
              <p class="mt-2 flex flex-wrap gap-1">
                <span class="rounded border border-sky-500/40 bg-sky-500/10 px-1.5 py-0.5 text-[9px] font-bold uppercase text-sky-200">${data.qualidade || 'Observado'}</span>
                <span class="rounded border border-zinc-700 px-1.5 py-0.5 text-[9px] text-zinc-400">${data.periodo || '2021–2025'}</span>
              </p>
              <p class="mt-2 border-t border-zinc-800 pt-1 text-[10px] text-zinc-500">${data.fonte}${data.attribution ? ` · ${data.attribution}` : ''}</p>
              <p class="mt-0.5 text-[9px] font-mono text-zinc-600">${lat.toFixed(5)}, ${lng.toFixed(5)}</p>
            </div>`,
          );
        })
        .catch((err: unknown) => {
          if (id !== reqId.current) return;
          const msg = err instanceof Error ? err.message : 'Falha na consulta';
          popup.setContent(
            `<div class="p-1 font-sans text-xs min-w-[200px]">
              <p class="mb-1 text-[10px] font-bold uppercase tracking-wide text-orange-300">Temperatura de superfície (LST)</p>
              <p class="text-[11px] text-rose-200">Não foi possível obter a LST neste ponto</p>
              <p class="mt-1 text-[9px] text-zinc-500">${msg}</p>
            </div>`,
          );
        });
    },
  });

  useEffect(() => {
    const container = map.getContainer();
    if (enabled) {
      container.style.cursor = 'crosshair';
    } else {
      container.style.cursor = '';
      map.closePopup();
      reqId.current += 1;
    }
    return () => {
      container.style.cursor = '';
    };
  }, [enabled, map]);

  return null;
}

/** Enquadra a malha municipal/bairros quando os dados chegam (evita zoom regional sem polígonos visíveis). */
function FitBoundsToBaseLayers({
  municipioFc,
  bairrosFc,
  selectedMunicipio,
  regionalActive,
}: {
  municipioFc?: any;
  bairrosFc?: any;
  selectedMunicipio: string;
  regionalActive: boolean;
}) {
  const map = useMap();
  const fittedFor = useRef<string | null>(null);

  useEffect(() => {
    fittedFor.current = null;
  }, [selectedMunicipio]);

  useEffect(() => {
    if (fittedFor.current === selectedMunicipio) return;
    const fc = bairrosFc?.features?.length ? bairrosFc : municipioFc;
    if (!fc?.features?.length) return;
    try {
      const layer = L.geoJSON(fc);
      const bounds = layer.getBounds();
      if (!bounds.isValid()) return;
      fittedFor.current = selectedMunicipio;
      map.fitBounds(bounds, {
        padding: [48, 48],
        maxZoom: regionalActive ? 12 : 13,
        animate: true,
      });
    } catch {
      // ignore invalid geometries
    }
  }, [map, selectedMunicipio, bairrosFc, municipioFc, regionalActive]);
  return null;
}

/** Enquadra o mapa na extensão das manchas de simulação. */
function FitBoundsToSimulation({ simGeoJSON }: { simGeoJSON: any | null }) {
  const map = useMap();
  const simKeyRef = useRef<string>('');

  useEffect(() => {
    if (!simGeoJSON?.features?.length) {
      simKeyRef.current = '';
      return;
    }
    const key = `${simGeoJSON.features.length}:${JSON.stringify(simGeoJSON.features[0]?.properties ?? {}).slice(0, 40)}`;
    if (simKeyRef.current === key) return;
    simKeyRef.current = key;
    try {
      const layer = L.geoJSON(simGeoJSON);
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [48, 48], maxZoom: 15, animate: true });
      }
    } catch {
      // geometria inválida
    }
  }, [map, simGeoJSON]);

  return null;
}

export default function MapContainer({
  activeLayers,
  mapFocus,
  zoom,
  simGeoJSON,
  simContours,
  simFlowPaths,
  simImpassableRoads,
  simCriticalAssets,
  simOverlays = {
    showFlood: true,
    showContours: true,
    showFlow: true,
    showImpassableRoads: true,
    showCriticalAssets: true,
  },
  contingencyOverlay = null,
  showContingencyOnMap = true,
  selectedMunicipio,
  socioSubcamada = 'renda',
  layerOptions = [],
  educacaoEtapa = 'todas',
  educacaoRaioM = 800,
  showEducacaoBuffer = true,
  territorioTipo = 'todas',
  layerAnoByTema = {},
}: MapProps) {
  const [layerData, setLayerData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);
  const [basemap, setBasemap] = useState<MapBasemapId>('satellite');
  const [failedLayers, setFailedLayers] = useState<string[]>([]);
  const [rasterConfigs, setRasterConfigs] = useState<Record<string, RasterRuntimeConfig>>({});
  const [rasterRescale, setRasterRescale] = useState<Record<ExternalRasterId, { min: number; max: number }>>(() => {
    const init = {} as Record<ExternalRasterId, { min: number; max: number }>;
    for (const layerId of EXTERNAL_RASTER_LAYER_IDS) {
      init[layerId] = {
        min: RASTER_RESCALE_UI[layerId].min,
        max: RASTER_RESCALE_UI[layerId].max,
      };
    }
    return init;
  });
  const [rasterLoading, setRasterLoading] = useState(false);
  const [regionalData, setRegionalData] = useState<RegionalOverlayResponse | null>(null);
  const [regionalLoading, setRegionalLoading] = useState(false);
  const [legendPanelCollapsed, setLegendPanelCollapsed] = useState(false);
  const [collapsedLegendSections, setCollapsedLegendSections] = useState<Record<string, boolean>>({});

  useEffect(() => {
    try {
      if (localStorage.getItem(LEGEND_PANEL_COLLAPSED_KEY) === 'true') {
        setLegendPanelCollapsed(true);
      }
      const raw = localStorage.getItem(LEGEND_SECTIONS_COLLAPSED_KEY);
      if (raw) setCollapsedLegendSections(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LEGEND_PANEL_COLLAPSED_KEY, String(legendPanelCollapsed));
    } catch {
      /* ignore */
    }
  }, [legendPanelCollapsed]);

  useEffect(() => {
    try {
      localStorage.setItem(LEGEND_SECTIONS_COLLAPSED_KEY, JSON.stringify(collapsedLegendSections));
    } catch {
      /* ignore */
    }
  }, [collapsedLegendSections]);

  const toggleLegendSection = (sectionId: string) => {
    setCollapsedLegendSections((prev) => ({ ...prev, [sectionId]: !prev[sectionId] }));
  };

  const showRegionalOverlay = useAppStore((s) => s.showRegionalOverlay);
  const regionalEscopo = useAppStore((s) => s.regionalEscopo);
  const setRegionalEscopo = useAppStore((s) => s.setRegionalEscopo);
  const setShowRegionalOverlay = useAppStore((s) => s.setShowRegionalOverlay);
  const setCompareModalOpen = useAppStore((s) => s.setCompareModalOpen);
  const layerOpacityById = useAppStore((s) => s.layerOpacityById);
  const setLayerOpacity = useAppStore((s) => s.setLayerOpacity);
  const moveActiveLayer = useAppStore((s) => s.moveActiveLayer);
  const toggleLayer = useAppStore((s) => s.toggleLayer);
  const showRegionalOverlayStore = useAppStore((s) => s.showRegionalOverlay);
  const setMapSpatialReady = useAppStore((s) => s.setMapSpatialReady);
  const equipamentoTiposAtivos = useAppStore((s) => s.equipamentoTiposAtivos);
  const toggleEquipamentoTipo = useAppStore((s) => s.toggleEquipamentoTipo);
  const setEquipamentoTiposAtivos = useAppStore((s) => s.setEquipamentoTiposAtivos);
  const equipamentoDepsAtivas = useAppStore((s) => s.equipamentoDepsAtivas);
  const toggleEquipamentoDep = useAppStore((s) => s.toggleEquipamentoDep);
  const setEquipamentoDepsAtivas = useAppStore((s) => s.setEquipamentoDepsAtivas);

  const activeRasterLayers = activeLayers.filter(isExternalRasterLayer);
  const lstIdentifyActive = activeRasterLayers.includes('lst_observada');
  // Chaves estáveis — array novo a cada render reiniciava o fetch e travava o loading.
  const activeRasterKey = activeRasterLayers.join(',');
  const rasterRescaleKey = activeRasterLayers
    .map((id) => `${id}:${rasterRescale[id]?.min ?? ''}-${rasterRescale[id]?.max ?? ''}`)
    .join('|');

  const layerMetaById = Object.fromEntries(layerOptions.map((opt) => [opt.id, opt]));

  // Só camadas vetoriais: ligar/desligar LST não deve recarregar bairros nem prender o spinner.
  const activeVectorKey = activeLayers.filter((id) => !isExternalRasterLayer(id)).join(',');
  const layerLoadGen = useRef(0);
  const loadedMunicipioRef = useRef<string | null>(null);

  // Fetch vector layers (raster layers use mosaicjson tile endpoints).
  useEffect(() => {
    const vectorLayers = activeVectorKey.split(',').filter(Boolean);

    if (vectorLayers.length === 0) {
      setLayerData({});
      setLoading(false);
      setMapSpatialReady(true);
      return;
    }

    const gen = ++layerLoadGen.current;
    const municipioChanged = loadedMunicipioRef.current !== selectedMunicipio;
    if (municipioChanged) {
      loadedMunicipioRef.current = selectedMunicipio;
      setLayerData({});
      setMapSpatialReady(false);
    }
    setLoading(true);
    setFailedLayers([]);

    let alive = true;
    const loadLayers = async () => {
      // Bairros primeiro — é a malha que o usuário espera ver.
      const ordered = [
        ...vectorLayers.filter((id) => id === 'bairros'),
        ...vectorLayers.filter((id) => id === 'municipio'),
        ...vectorLayers.filter((id) => id !== 'bairros' && id !== 'municipio'),
      ];

      try {
        for (const layerName of ordered) {
          if (!alive || layerLoadGen.current !== gen) return;
          try {
            const extraParams = buildLayerFetchParams(layerName, {
              educacaoEtapa,
              territorioTipo,
              layerAnoByTema,
            });
            const data = await api.getLayerGeoJSON(layerName, selectedMunicipio, extraParams);
            if (!alive || layerLoadGen.current !== gen) return;
            if (!data?.features || !Array.isArray(data.features)) {
              console.error(`Layer ${layerName} retornou payload inválido`, data);
              setFailedLayers((prev) => (prev.includes(layerName) ? prev : [...prev, layerName]));
              continue;
            }
            setLayerData((prev) => ({ ...prev, [layerName]: data }));
            if (layerName === 'bairros' || layerName === 'municipio') {
              setMapSpatialReady(true);
            }
          } catch (err) {
            console.error(`Error loading layer ${layerName}:`, err);
            if (alive && layerLoadGen.current === gen) {
              setFailedLayers((prev) => (prev.includes(layerName) ? prev : [...prev, layerName]));
            }
          }
        }
      } finally {
        // Sempre libera o spinner desta geração (evita travar se o effect for cancelado no meio).
        if (layerLoadGen.current === gen) {
          setLoading(false);
          setMapSpatialReady(true);
        }
      }
    };

    loadLayers().catch((err) => {
      console.error('Error loading layers:', err);
      if (layerLoadGen.current === gen) {
        setLoading(false);
        setMapSpatialReady(true);
      }
    });

    return () => {
      alive = false;
    };
    // Não incluir layerAnoByTema/educacao/territorio aqui: mudam no boot e cancelavam o fetch de bairros.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeVectorKey, selectedMunicipio, setMapSpatialReady]);

  // Recarrega só camadas que dependem de ano/etapa quando esses filtros mudam.
  useEffect(() => {
    const dependent = activeLayers.filter(
      (id) => id === 'cobertura' || id === 'socioeconomico' || id === 'educacao' || id === 'territorios_especiais',
    );
    if (dependent.length === 0) return;

    let alive = true;
    (async () => {
      for (const layerName of dependent) {
        if (!alive) return;
        try {
          const extraParams = buildLayerFetchParams(layerName, {
            educacaoEtapa,
            territorioTipo,
            layerAnoByTema,
          });
          const data = await api.getLayerGeoJSON(layerName, selectedMunicipio, extraParams);
          if (!alive || !data?.features) return;
          setLayerData((prev) => ({ ...prev, [layerName]: data }));
        } catch (err) {
          console.error(`Error reloading layer ${layerName}:`, err);
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, [educacaoEtapa, territorioTipo, layerAnoByTema, activeVectorKey, selectedMunicipio]);

  useEffect(() => {
    const rasterIds = activeRasterKey.split(',').filter(Boolean) as ExternalRasterId[];
    if (rasterIds.length === 0) {
      setRasterConfigs({});
      setRasterLoading(false);
      return;
    }

    let cancelled = false;
    const loadRasters = async () => {
      setRasterLoading(true);
      try {
        const entries = await Promise.all(
          rasterIds.map(async (layerId) => {
            const rescale = rasterRescale[layerId];
            const ano = layerId === 'lst_observada' ? layerAnoByTema.lst : undefined;
            const cfg = await api.getExternalRasterConfig(
              layerId,
              selectedMunicipio,
              rescale.min,
              rescale.max,
              ano,
            );
            return [
              layerId,
              {
                tileUrl: cfg.tile_url_template,
                minZoom: cfg.min_zoom,
                maxZoom: cfg.max_zoom,
                attribution: cfg.attribution,
              },
            ] as const;
          }),
        );
        if (!cancelled) {
          setRasterConfigs(Object.fromEntries(entries));
        }
      } catch (err) {
        console.error('Error loading external raster config:', err);
        if (!cancelled) setRasterConfigs({});
      } finally {
        if (!cancelled) setRasterLoading(false);
      }
    };

    loadRasters();
    return () => {
      cancelled = true;
    };
  }, [activeRasterKey, selectedMunicipio, rasterRescaleKey, layerAnoByTema.lst]);

  useEffect(() => {
    if (!showRegionalOverlay || !selectedMunicipio) {
      setRegionalData(null);
      setRegionalLoading(false);
      return;
    }

    let cancelled = false;
    const loadRegional = async () => {
      setRegionalLoading(true);
      try {
        const data = await api.getRegionalOverlay(selectedMunicipio, regionalEscopo);
        if (!cancelled) setRegionalData(data);
      } catch (err) {
        console.error('Error loading regional overlay:', err);
        if (!cancelled) setRegionalData(null);
      } finally {
        if (!cancelled) setRegionalLoading(false);
      }
    };

    loadRegional();
    return () => {
      cancelled = true;
    };
  }, [showRegionalOverlay, selectedMunicipio, regionalEscopo]);

  // Color functions for thematic vector layers
  const getLayerStyleForFeature = (layerName: string, feature: any) => {
    const style = getLayerStyle(layerName, feature, { socioSubcamada, educacaoEtapa, territorioTipo });
    const layerOpacity = layerOpacityById[layerName] ?? 1;
    const styleOpacity = 'opacity' in style ? Number((style as { opacity?: number }).opacity ?? 1) : 1;
    const withOpacity = {
      ...style,
      fillOpacity: (style.fillOpacity ?? 0.5) * layerOpacity,
      opacity: styleOpacity * layerOpacity,
    };
    // LST identify: polígonos não podem capturar o clique (senão abre popup do limite municipal).
    const passThrough = (s: Record<string, unknown>) =>
      (lstIdentifyActive ? { ...s, interactive: false } : s);
    const thematicOnTop = activeLayers.some((l) =>
      ['cobertura', 'inundacao', 'vulnerabilidade', 'risco_consolidado', 'saneamento_drenagem', 'prioridade_planejamento', 'adaptacao_climatica', 'saude_risco', 'seguranca_publica', 'vulnerabilidade_multidimensional', 'lst_observada'].includes(l)
    );
    const simActive = Boolean(simGeoJSON) || (simContours?.features?.length ?? 0) > 0;
    if (layerName === 'bairros' && simActive) {
      return passThrough({
        ...withOpacity,
        fillOpacity: 0,
        fillColor: 'transparent',
        weight: 0.55,
        color: '#475569',
        opacity: 0.4 * layerOpacity,
      });
    }
    if (layerName === 'bairros' && thematicOnTop) {
      const coberturaActive = activeLayers.includes('cobertura');
      if (coberturaActive) {
        return passThrough({
          ...withOpacity,
          fillOpacity: 0,
          fillColor: 'transparent',
          weight: 1.6,
          color: '#e2e8f0',
          opacity: 0.9 * layerOpacity,
        });
      }
      // Mantém contorno legível mesmo com temáticas por cima
      return passThrough({
        ...withOpacity,
        fillOpacity: Math.min(withOpacity.fillOpacity, 0.18),
        weight: 1.4,
        color: '#c7d2fe',
        opacity: 0.9 * layerOpacity,
      });
    }
    if (layerName === 'cobertura' && activeLayers.includes('bairros')) {
      return passThrough({ ...withOpacity, fillOpacity: Math.min(withOpacity.fillOpacity, 0.38) });
    }
    return passThrough(withOpacity);
  };

  const layerRenderOrder = buildVectorRenderOrder(activeLayers);

  const displayLayerData = useMemo(() => {
    const infra = layerData.infraestrutura;
    if (!infra?.features) return layerData;
    const filtered = infra.features.filter((f: any) =>
      matchEquipamentoFiltro(f?.properties || {}, equipamentoTiposAtivos, equipamentoDepsAtivas),
    );
    return {
      ...layerData,
      infraestrutura: { ...infra, features: filtered },
    };
  }, [layerData, equipamentoTiposAtivos, equipamentoDepsAtivas]);

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-border bg-zinc-950">
      {/* Loading Overlay — só bloqueia no fetch vetorial; raster LST não trava o mapa */}
      {loading ? (
        <div className="absolute inset-0 bg-background/60 backdrop-blur-sm z-[1000] flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
            <span className="text-zinc-300 text-sm font-medium">Carregando dados espaciais...</span>
          </div>
        </div>
      ) : null}

      {rasterLoading && !loading ? (
        <div className="map-ui-chrome pointer-events-none absolute left-1/2 top-4 z-[1100] -translate-x-1/2 rounded-lg border border-orange-500/40 bg-zinc-950/90 px-3 py-1.5 text-[11px] text-orange-100 shadow-lg backdrop-blur-md">
          Carregando LST…
        </div>
      ) : null}

      {!loading && failedLayers.length > 0 && (
        <div className="map-ui-chrome pointer-events-auto absolute left-1/2 top-4 z-[1200] flex max-w-[90%] -translate-x-1/2 items-start gap-2 rounded-xl border border-amber-500/50 bg-zinc-950/95 px-3 py-2 text-[11px] text-amber-100 shadow-lg backdrop-blur-md">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-400" />
          <div>
            <p className="font-bold text-amber-200">
              {failedLayers.length === 1 ? 'Uma camada não carregou' : `${failedLayers.length} camadas não carregaram`}
            </p>
            <p className="mt-0.5 text-amber-100/80">
              {failedLayers.map((id) => layerMetaById[id]?.label || id).join(', ')} — o mapa pode estar incompleto para este município.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setFailedLayers([])}
            className="ml-1 rounded p-0.5 text-amber-300/70 hover:text-amber-100"
            aria-label="Dispensar aviso"
          >
            <X size={13} />
          </button>
        </div>
      )}

      <LeafletMap
        center={mapFocus}
        zoom={zoom}
        className="w-full h-full"
        zoomControl={false}
      >
        <MapController center={mapFocus} zoom={zoom} />
        <LstPointIdentify
          enabled={lstIdentifyActive}
          codigoIbge={selectedMunicipio}
        />
        <FitBoundsToBaseLayers
          selectedMunicipio={selectedMunicipio}
          municipioFc={layerData.municipio}
          bairrosFc={layerData.bairros}
          regionalActive={showRegionalOverlay}
        />
        <FitBoundsToSimulation simGeoJSON={simGeoJSON} />
        
        <TileLayer
          key={basemap}
          attribution={MAP_TILE_URLS[basemap].attribution}
          url={MAP_TILE_URLS[basemap].url}
        />

        {activeRasterLayers.map((layerId) => {
          const cfg = rasterConfigs[layerId];
          if (!cfg) return null;
          const rescale = rasterRescale[layerId];
          return (
            <TileLayer
              key={`${layerId}-${rescale.min}-${rescale.max}`}
              url={cfg.tileUrl}
              minZoom={cfg.minZoom}
              maxZoom={cfg.maxZoom}
              opacity={0.82 * (layerOpacityById[layerId] ?? 1)}
              attribution={cfg.attribution}
            />
          );
        })}

        {/* Dynamic PostGIS geospatial layers, rendered in selection order for overlays */}
        {layerRenderOrder.map((layerName) => (
          displayLayerData[layerName] && (
            <GeoJSON
              key={`${layerName}-${lstIdentifyActive ? 'lst-id' : 'vec'}-${socioSubcamada}-${educacaoEtapa}-${territorioTipo}-${educacaoRaioM}-${showEducacaoBuffer}-${equipamentoTiposAtivos.join(',')}-${equipamentoDepsAtivas.join(',')}-${layerOpacityById[layerName] ?? 1}-${displayLayerData[layerName].features?.length || 0}`}
              data={displayLayerData[layerName]}
              style={(feature) => getLayerStyleForFeature(layerName, feature)}
              pointToLayer={createPointToLayer(layerName, { educacaoEtapa, showEducacaoBuffer, educacaoRaioM })}
              onEachFeature={createFeaturePopupHandler(layerName, lstIdentifyActive)}
            />
          )
        ))}

        {showRegionalOverlay && regionalData?.geojson?.features?.length ? (
          <GeoJSON
            key={`regional-${lstIdentifyActive ? 'lst-id' : 'vec'}-${regionalEscopo}-${regionalData.geojson.features.length}`}
            data={regionalData.geojson}
            style={(feature) => {
              const kind = feature?.properties?.feature_kind;
              const base =
                kind === 'referencia_comparacao'
                  ? {
                      fillColor: '#f59e0b',
                      fillOpacity: 0.08,
                      color: '#fbbf24',
                      weight: 2.2,
                      opacity: 0.9,
                      dashArray: '8,5',
                    }
                  : {
                      fillColor: '#22d3ee',
                      fillOpacity: 0.04,
                      color: '#22d3ee',
                      weight: 1.6,
                      opacity: 0.75,
                      dashArray: '6,4',
                    };
              return lstIdentifyActive ? { ...base, interactive: false } : base;
            }}
            onEachFeature={(feature, layer) => {
              if (lstIdentifyActive) return;
              layer.bindPopup(buildRegionalFeaturePopup(feature.properties || {}));
            }}
          />
        ) : null}

        {/* Manchas de simulação por profundidade */}
        {simGeoJSON && simOverlays.showFlood && (
          <GeoJSON
            key={`sim-${lstIdentifyActive ? 'lst-id' : 'vec'}-${JSON.stringify(simGeoJSON).slice(0, 80)}`}
            data={simGeoJSON}
            style={(feature) => {
              const base = getSimulationFeatureStyle(feature);
              return lstIdentifyActive ? { ...base, interactive: false } : base;
            }}
            onEachFeature={(feature, layer) => {
              if (lstIdentifyActive) return;
              layer.bindPopup(buildSimulationFeaturePopup(feature.properties || {}));
            }}
          />
        )}

        {/* Curvas de nível (DEM SRTM) */}
        {simOverlays.showContours && simContours?.features?.length > 0 && (
          <GeoJSON
            key={`contours-${simContours.features.length}`}
            data={simContours}
            style={(feature) => {
              const indexed = feature?.properties?.index_contour;
              return {
                fillOpacity: 0,
                color: indexed ? '#ecfccb' : '#84cc16',
                weight: indexed ? 2 : 0.9,
                opacity: indexed ? 0.95 : 0.6,
              };
            }}
            onEachFeature={(feature, layer) => {
              const tip = buildContourTooltip(feature);
              if (tip) layer.bindTooltip(tip, { sticky: true, className: 'text-[10px]' });
            }}
          />
        )}

        {simOverlays.showFlow && simFlowPaths?.features?.length > 0 && (
          <GeoJSON
            key={`flow-${simFlowPaths.features.length}`}
            data={simFlowPaths}
            style={() => ({
              fillOpacity: 0,
              color: '#22d3ee',
              weight: 2,
              opacity: 0.9,
              dashArray: '6,4',
            })}
          />
        )}

        {simOverlays.showImpassableRoads !== false && simImpassableRoads?.features?.length > 0 && (
          <GeoJSON
            key={`impassable-${simImpassableRoads.features.length}`}
            data={simImpassableRoads}
            style={() => ({
              fillOpacity: 0,
              color: '#ef4444',
              weight: 3.2,
              opacity: 0.92,
            })}
            onEachFeature={(feature, layer) => {
              const nome = feature.properties?.nome || 'Via';
              const km = feature.properties?.length_km;
              layer.bindPopup(
                `<div class="p-2 text-xs"><strong>${nome}</strong>`
                + `<p class="text-zinc-400">Intransitável (≥35 cm)`
                + (km != null ? ` · ${km} km` : '')
                + `</p></div>`,
              );
            }}
          />
        )}

        {simOverlays.showCriticalAssets !== false && simCriticalAssets?.features?.length > 0 && (
          <GeoJSON
            key={`critical-${simCriticalAssets.features.length}`}
            data={simCriticalAssets}
            pointToLayer={(feature, latlng) => {
              const cat = feature.properties?.categoria;
              const color =
                cat === 'escola' ? '#38bdf8' : cat === 'saude' ? '#22c55e' : '#fbbf24';
              return L.circleMarker(latlng, {
                radius: feature.properties?.depth_band === 'critica' ? 9 : 7,
                color: '#7f1d1d',
                weight: 1.5,
                fillColor: color,
                fillOpacity: 0.92,
              });
            }}
            onEachFeature={(feature, layer) => {
              const p = feature.properties || {};
              const cat =
                p.categoria === 'escola' ? 'Escola' : p.categoria === 'saude' ? 'Saúde' : 'Abrigo';
              const extra =
                p.matriculas_total != null
                  ? ` · ${p.matriculas_total} matrículas`
                  : p.leitos_sus != null
                    ? ` · ${p.leitos_sus} leitos SUS`
                    : '';
              layer.bindPopup(
                `<div class="p-2 text-xs"><strong>${p.nome || cat}</strong>`
                + `<p class="text-zinc-400">${cat} atingido`
                + (p.depth_band ? ` · ${p.depth_band}` : '')
                + `${extra}</p></div>`,
              );
            }}
          />
        )}

        {showContingencyOnMap && contingencyOverlay?.zonas?.features?.length ? (
          <GeoJSON
            key={`ctg-zonas-${contingencyOverlay.planId}-${contingencyOverlay.zonas.features.length}`}
            data={contingencyOverlay.zonas as any}
            style={() => ({
              color: '#f97316',
              fillColor: '#fb923c',
              fillOpacity: 0.32,
              weight: 2,
            })}
            onEachFeature={(feature, layer) => {
              const nome = feature.properties?.nome || 'Zona de evacuação';
              layer.bindPopup(`<div class="p-2 text-xs"><strong>${nome}</strong><p class="text-zinc-400">Plano ativo · ${contingencyOverlay.nivel}</p></div>`);
            }}
          />
        ) : null}

        {showContingencyOnMap && contingencyOverlay?.rotas?.features?.length ? (
          <GeoJSON
            key={`ctg-rotas-${contingencyOverlay.planId}-${contingencyOverlay.rotas.features.length}`}
            data={contingencyOverlay.rotas as any}
            style={(feature) => {
              const approx = feature?.properties?.aproximada;
              return {
                color: approx ? '#fbbf24' : '#38bdf8',
                weight: approx ? 3 : 4,
                opacity: 0.95,
                dashArray: approx ? '8 6' : undefined,
                fillOpacity: 0,
              };
            }}
            onEachFeature={(feature, layer) => {
              const nome = feature.properties?.nome || 'Rota de fuga';
              layer.bindPopup(`<div class="p-2 text-xs"><strong>${nome}</strong></div>`);
            }}
          />
        ) : null}

        {showContingencyOnMap && contingencyOverlay?.pontos?.features?.length ? (
          <GeoJSON
            key={`ctg-pontos-${contingencyOverlay.planId}-${contingencyOverlay.pontos.features.length}`}
            data={contingencyOverlay.pontos as any}
            pointToLayer={(_feature, latlng) =>
              L.circleMarker(latlng, {
                radius: 7,
                color: '#f59e0b',
                fillColor: '#fbbf24',
                fillOpacity: 0.95,
                weight: 2,
              })
            }
            onEachFeature={(feature, layer) => {
              const nome = feature.properties?.nome || 'Ponto de apoio';
              layer.bindPopup(`<div class="p-2 text-xs"><strong>${nome}</strong></div>`);
            }}
          />
        ) : null}

      </LeafletMap>

      <div
        className="map-ui-chrome pointer-events-auto absolute top-20 z-[1100] flex gap-1 rounded-xl border border-zinc-700/80 bg-zinc-950/95 p-1 shadow-lg backdrop-blur-md"
        style={{ left: MAP_CENTER_LEFT }}
      >
        {([
          ['dark', 'Escuro'],
          ['light', 'Claro'],
          ['satellite', 'Satélite'],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setBasemap(id)}
            className={`rounded-lg px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider ${
              basemap === id
                ? 'bg-indigo-600 text-white'
                : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {showContingencyOnMap && contingencyOverlay && (
        <div className="map-ui-chrome pointer-events-none absolute bottom-4 left-4 z-[1100] rounded-xl border border-orange-500/40 bg-zinc-950/95 px-3 py-2 text-[10px] text-orange-100 shadow-lg backdrop-blur-md">
          <p className="font-extrabold uppercase tracking-wider text-orange-300">Plano ativo no mapa</p>
          <p className="mt-0.5 text-zinc-400">
            {contingencyOverlay.cenario} · {contingencyOverlay.nivel} ·{' '}
            {contingencyOverlay.zonas.features.length} zona(s)
          </p>
        </div>
      )}

      {showRegionalOverlay && (
        <RegionalOverlayPanel
          data={regionalData}
          loading={regionalLoading}
          escopo={regionalEscopo}
          setEscopo={setRegionalEscopo}
          onClose={() => setShowRegionalOverlay(false)}
          onOpenCompare={() => setCompareModalOpen(true)}
        />
      )}

      {/* Coluna direita: camadas ativas + legenda */}
      <div className="pointer-events-auto absolute bottom-4 right-4 top-24 z-[1100] flex w-72 flex-col gap-2">
        <ActiveLayersPanel
          activeLayers={activeLayers}
          layerOptions={layerOptions}
          layerOpacityById={layerOpacityById}
          setLayerOpacity={setLayerOpacity}
          moveActiveLayer={moveActiveLayer}
          toggleLayer={toggleLayer}
          showRegionalOverlay={showRegionalOverlayStore}
        />

        {legendPanelCollapsed ? (
          <button
            type="button"
            onClick={() => setLegendPanelCollapsed(false)}
            className="map-ui-chrome flex w-full shrink-0 items-center justify-between rounded-xl border border-zinc-700/80 bg-zinc-950/95 px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-zinc-200 shadow-lg backdrop-blur-md hover:border-zinc-600"
          >
            <span>Legenda Territorial ({activeLayers.length})</span>
            <ChevronDown size={14} className="text-zinc-500" />
          </button>
        ) : (
        <div className="map-ui-chrome flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-zinc-700/80 bg-zinc-950/95 text-[11px] text-zinc-200 shadow-2xl shadow-black/50 backdrop-blur-md">
        <div className="flex shrink-0 items-start justify-between gap-2 border-b border-zinc-800 bg-zinc-950/95 px-4 py-3">
          <div className="min-w-0">
            <h5 className="text-sm font-extrabold text-zinc-50">Legenda Territorial</h5>
            <p className="mt-0.5 text-[10px] text-zinc-500">Camadas do município selecionado no header.</p>
          </div>
          <button
            type="button"
            onClick={() => setLegendPanelCollapsed(true)}
            title="Recolher legenda"
            className="rounded p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
          >
            <ChevronUp size={14} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 pr-5">
          {activeLayers.length === 0 && !simGeoJSON && (
            <span className="text-zinc-500 italic">Nenhuma camada ativada no momento.</span>
          )}
          {activeLayers.map((layerName) => {
            const sectionCollapsed = !!collapsedLegendSections[layerName];
            return (
            <div key={layerName} className="mb-3 last:mb-0 rounded-lg border border-zinc-800/80 bg-zinc-950/30">
              <button
                type="button"
                onClick={() => toggleLegendSection(layerName)}
                className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-zinc-900/50"
              >
                {sectionCollapsed ? (
                  <ChevronRight size={12} className="shrink-0 text-zinc-500" />
                ) : (
                  <ChevronDown size={12} className="shrink-0 text-zinc-500" />
                )}
                <span className="flex-1 text-[10px] font-extrabold uppercase tracking-wider text-indigo-300">
                  {layerTitles[layerName] || layerName}
                </span>
              </button>
              {!sectionCollapsed && (
              <div className="px-2 pb-2">
              {layerMetaById[layerName] && (
                <LayerMetaBlock layer={layerMetaById[layerName]} compact defaultCollapsed />
              )}
              {isExternalRasterLayer(layerName) ? (
                <div className="flex flex-col gap-2">
                  <div
                    className="h-3 w-full rounded-sm border border-white/20"
                    style={{ background: RASTER_RESCALE_UI[layerName].gradient }}
                  />
                  <div className="flex justify-between text-[9px] text-zinc-400">
                    <span>
                      {rasterRescale[layerName].min}
                      {RASTER_RESCALE_UI[layerName].unit}
                    </span>
                    <span>
                      {rasterRescale[layerName].max}
                      {RASTER_RESCALE_UI[layerName].unit}
                    </span>
                  </div>
                  <label className="flex flex-col gap-0.5 text-[9px] text-zinc-400">
                    Mínimo ({RASTER_RESCALE_UI[layerName].unit})
                    <input
                      type="range"
                      min={RASTER_RESCALE_UI[layerName].minBound}
                      max={RASTER_RESCALE_UI[layerName].minSliderMax}
                      step={RASTER_RESCALE_UI[layerName].step}
                      value={rasterRescale[layerName].min}
                      onChange={(e) => {
                        const next = Number(e.target.value);
                        setRasterRescale((prev) => ({
                          ...prev,
                          [layerName]: {
                            min: Math.min(next, prev[layerName].max - 1),
                            max: prev[layerName].max,
                          },
                        }));
                      }}
                      className="w-full accent-sky-500"
                    />
                  </label>
                  <label className="flex flex-col gap-0.5 text-[9px] text-zinc-400">
                    Máximo ({RASTER_RESCALE_UI[layerName].unit})
                    <input
                      type="range"
                      min={RASTER_RESCALE_UI[layerName].maxSliderMin}
                      max={RASTER_RESCALE_UI[layerName].maxBound}
                      step={RASTER_RESCALE_UI[layerName].step}
                      value={rasterRescale[layerName].max}
                      onChange={(e) => {
                        const next = Number(e.target.value);
                        setRasterRescale((prev) => ({
                          ...prev,
                          [layerName]: {
                            min: prev[layerName].min,
                            max: Math.max(next, prev[layerName].min + 1),
                          },
                        }));
                      }}
                      className="w-full accent-orange-500"
                    />
                  </label>
                  <p className="text-[9px] leading-snug text-zinc-500">
                    Clique no mapa para ler a temperatura (°C) no ponto — mosaico GeoReDUS / Landsat.
                    Raster externo (mosaicjson) — sem ingestão PostGIS no Sinidu.
                  </p>
                </div>
              ) : layerName === 'socioeconomico' ? (
                <div className="grid grid-cols-1 gap-1.5">
                  {(getSocioSubcamada(socioSubcamada).legend || []).map((item) => (
                    <div key={`${layerName}-${item.label}`} className="flex items-center gap-2">
                      <span
                        className="h-3.5 w-3.5 shrink-0 rounded-sm border border-white/30 shadow"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="leading-tight text-zinc-300">{item.label}</span>
                    </div>
                  ))}
                  <p className="mt-1 text-[9px] italic text-zinc-500">
                    Subcamada: {getSocioSubcamada(socioSubcamada).label}
                  </p>
                </div>
              ) : layerName === 'territorios_especiais' ? (
                <div className="grid grid-cols-1 gap-1.5">
                  {(legendByLayer[layerName] || []).map((item) => (
                    <div key={`${layerName}-${item.label}`} className="flex items-center gap-2">
                      <span
                        className="h-3.5 w-3.5 shrink-0 rounded-sm border border-white/30 shadow"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="leading-tight text-zinc-300">{item.label}</span>
                    </div>
                  ))}
                  <p className="mt-1 text-[9px] leading-snug text-zinc-500">
                    Filtro: {getTerritorioTipo(territorioTipo).label} · INCRA / FUNAI / IBGE
                  </p>
                </div>
              ) : layerName === 'educacao' ? (
                <div className="grid grid-cols-1 gap-1.5">
                  {(legendByLayer[layerName] || []).map((item) => (
                    <div key={`${layerName}-${item.label}`} className="flex items-center gap-2">
                      <span
                        className="h-3.5 w-3.5 shrink-0 rounded-sm border border-white/30 shadow"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="leading-tight text-zinc-300">{item.label}</span>
                    </div>
                  ))}
                  <p className="mt-1 text-[9px] leading-snug text-zinc-500">
                    Cor = dependência (federal / estadual / municipal / privada)
                    {educacaoEtapa !== 'todas' ? ` · filtro ${getEducacaoEtapa(educacaoEtapa).label}` : ''}
                    {' '}· tamanho ∝ matrículas
                  </p>
                  {showEducacaoBuffer && (
                    <p className="text-[9px] leading-snug text-indigo-300/80">
                      Buffer de influência: {educacaoRaioM} m
                    </p>
                  )}
                </div>
              ) : layerName === 'infraestrutura' ? (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[9px] font-bold uppercase tracking-wider text-teal-200">Tipo</p>
                    <button
                      type="button"
                      onClick={() => setEquipamentoTiposAtivos([...EQUIPAMENTO_TIPOS_DEFAULT])}
                      className="text-[8px] font-semibold text-teal-300/80 hover:text-teal-100"
                    >
                      Reset tipos
                    </button>
                  </div>
                  <div className="grid grid-cols-1 gap-1">
                    {EQUIPAMENTO_TIPOS.map((tipo) => {
                      const active = equipamentoTiposAtivos.includes(tipo.id);
                      return (
                        <button
                          key={tipo.id}
                          type="button"
                          onClick={() => toggleEquipamentoTipo(tipo.id)}
                          className={`flex items-center gap-2 rounded-md px-1 py-0.5 text-left transition ${
                            active ? 'bg-teal-500/10' : 'opacity-45'
                          }`}
                          title={active ? `Ocultar ${tipo.label}` : `Mostrar ${tipo.label}`}
                        >
                          <span
                            className="inline-flex h-4 min-w-[18px] items-center justify-center rounded-full border-2 border-white/40 px-1 text-[8px] font-extrabold text-white"
                            style={{ backgroundColor: tipo.color }}
                          >
                            {tipo.short}
                          </span>
                          <span className={`leading-tight ${active ? 'text-zinc-200' : 'text-zinc-500 line-through'}`}>
                            {tipo.label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  <div className="flex items-center justify-between gap-2 pt-1">
                    <p className="text-[9px] font-bold uppercase tracking-wider text-teal-200">Dependência (borda)</p>
                    <button
                      type="button"
                      onClick={() => setEquipamentoDepsAtivas([...EQUIPAMENTO_DEPS_DEFAULT])}
                      className="text-[8px] font-semibold text-teal-300/80 hover:text-teal-100"
                    >
                      Reset
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-1">
                    {(Object.keys(DEPENDENCIA_LABELS) as DependenciaId[]).map((dep) => {
                      const active = equipamentoDepsAtivas.includes(dep);
                      return (
                        <button
                          key={dep}
                          type="button"
                          onClick={() => toggleEquipamentoDep(dep)}
                          className={`flex items-center gap-1.5 rounded-md px-1 py-0.5 text-left ${
                            active ? 'bg-teal-500/10' : 'opacity-45'
                          }`}
                        >
                          <span
                            className="h-3 w-3 shrink-0 rounded-full border-2 border-zinc-900"
                            style={{ backgroundColor: DEPENDENCIA_COLORS[dep], boxShadow: `0 0 0 1.5px ${DEPENDENCIA_COLORS[dep]}` }}
                          />
                          <span className={`text-[10px] ${active ? 'text-zinc-200' : 'text-zinc-500 line-through'}`}>
                            {DEPENDENCIA_LABELS[dep]}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  <p className="text-[8px] leading-snug text-zinc-500">
                    Preenchimento = tipo · borda = esfera. Clique para ocultar/mostrar.
                    {displayLayerData.infraestrutura?.features
                      ? ` · ${displayLayerData.infraestrutura.features.length.toLocaleString('pt-BR')} visíveis`
                      : ''}
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-1.5">
                  {(legendByLayer[layerName] || []).map((item) => (
                    <div key={`${layerName}-${item.label}`} className="flex items-center gap-2">
                      <span
                        className="h-3.5 w-3.5 shrink-0 rounded-sm border border-white/30 shadow"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="leading-tight text-zinc-300">{item.label}</span>
                    </div>
                  ))}
                </div>
              )}
              </div>
              )}
            </div>
            );
          })}
          {simGeoJSON && (
            <div className="mt-3 rounded-lg border border-zinc-800/80 bg-zinc-950/30">
              <button
                type="button"
                onClick={() => toggleLegendSection('__simulacao__')}
                className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-zinc-900/50"
              >
                {collapsedLegendSections.__simulacao__ ? (
                  <ChevronRight size={12} className="shrink-0 text-zinc-500" />
                ) : (
                  <ChevronDown size={12} className="shrink-0 text-zinc-500" />
                )}
                <span className="flex-1 text-[10px] font-extrabold uppercase tracking-wider text-indigo-300">
                  Simulação hidrológica
                </span>
              </button>
              {!collapsedLegendSections.__simulacao__ && (
            <div className="flex flex-col gap-2 px-2 pb-2">
              <div className="flex items-center gap-2 text-zinc-400"><span className="h-3 w-3 rounded-sm border border-sky-900 bg-sky-400/50" />Alagamento superficial</div>
              <div className="flex items-center gap-2 text-zinc-400"><span className="h-3 w-3 rounded-sm border border-sky-800 bg-sky-600/60" />Alagamento moderado</div>
              <div className="flex items-center gap-2 text-zinc-400"><span className="h-3 w-3 rounded-sm border border-indigo-950 bg-indigo-900/70" />Alagamento crítico</div>
              <div className="flex items-center gap-2 text-zinc-400"><span className="h-3 w-3 rounded-sm border border-red-900 bg-red-600/55" />Deslizamento / ilha de calor</div>
              {simContours?.features?.length > 0 && simOverlays.showContours && (
                <div className="flex items-center gap-2 text-zinc-400"><span className="h-0.5 w-4 bg-lime-300" />Curvas indexadas (DEM)</div>
              )}
              {simContours?.features?.length > 0 && simOverlays.showContours && (
                <div className="flex items-center gap-2 text-zinc-400"><span className="h-0.5 w-4 bg-lime-500" />Curvas intermediárias</div>
              )}
              {simFlowPaths?.features?.length > 0 && (
                <div className="flex items-center gap-2 text-zinc-400"><span className="h-0.5 w-4 border-t-2 border-dashed border-cyan-400" />Escoamento superficial</div>
              )}
            </div>
              )}
            </div>
          )}
          {showRegionalOverlay && (
            <div className="mt-3 rounded-lg border border-zinc-800/80 bg-zinc-950/30">
              <button
                type="button"
                onClick={() => toggleLegendSection('__regional__')}
                className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-zinc-900/50"
              >
                {collapsedLegendSections.__regional__ ? (
                  <ChevronRight size={12} className="shrink-0 text-zinc-500" />
                ) : (
                  <ChevronDown size={12} className="shrink-0 text-zinc-500" />
                )}
                <span className="flex-1 text-[10px] font-extrabold uppercase tracking-wider text-teal-300">
                  Contexto regional
                </span>
              </button>
              {!collapsedLegendSections.__regional__ && (
              <div className="flex flex-col gap-2 px-2 pb-2">
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="h-0.5 w-4 border-t-2 border-dashed border-cyan-400" />
                Municípios do escopo
              </div>
              <div className="flex items-center gap-2 text-zinc-400">
                <span className="h-0.5 w-4 border-t-2 border-dashed border-amber-400" />
                Referência de comparação
              </div>
              </div>
              )}
            </div>
          )}
        </div>
        </div>
        )}
      </div>
    </div>
  );
}
