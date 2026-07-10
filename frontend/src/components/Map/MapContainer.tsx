'use client';

import { useEffect, useRef, useState } from 'react';
import { MapContainer as LeafletMap, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import { api } from '@/utils/api';
import { getLayerStyle, getSimulationFeatureStyle } from './layerStyles';
import { getSocioSubcamada, type SocioSubcamadaId } from '@/config/socioeconomicoSubcamadas';
import {
  DEPENDENCIA_LABELS,
  EDUCACAO_ETAPAS,
  getEducacaoEtapa,
  markerRadiusFromMatriculas,
  type EducacaoEtapaId,
} from '@/config/educacaoInep';
import {
  TERRITORIO_LEGEND,
  getTerritorioTipo,
  type TerritorioTipoId,
} from '@/config/territoriosEspeciais';
import type { LayerOption } from '@/config/platformTabs';
import type { RegionalOverlayResponse } from '@/config/regionalContext';
import { useAppStore } from '@/stores/useAppStore';
import LayerMetaBlock from './LayerMetaBlock';
import RegionalOverlayPanel from './RegionalOverlayPanel';
import ActiveLayersPanel from './ActiveLayersPanel';
import { buildVectorRenderOrder } from '@/utils/activeLayerOrder';
import {
  EXTERNAL_RASTER_LAYER_IDS,
  isExternalRasterLayer,
  RASTER_RESCALE_UI,
  type ExternalRasterId,
} from '@/config/externalRasters';
import { buildLayerFetchParams } from '@/config/layerTemporal';

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
  simOverlays?: { showFlood: boolean; showContours: boolean; showFlow: boolean };
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

const layerTitles: Record<string, string> = {
  municipio: 'Limite Municipal',
  bairros: 'Bairros',
  territorios_especiais: 'Territórios Especiais',
  infraestrutura: 'Equipamentos e Redes',
  educacao: 'Educação (INEP)',
  socioeconomico: 'Socioeconômico',
  cobertura: 'Uso do Solo',
  lst_observada: 'LST observada',
  vulnerabilidade: 'Vulnerabilidade',
  inundacao: 'Risco de Inundação',
  alertas: 'Alertas',
  desastres: 'Desastres',
  saneamento_drenagem: 'Saneamento e Drenagem',
  adaptacao_climatica: 'Adaptação Climática',
  prioridade_planejamento: 'Prioridade de Planejamento',
  lacunas_dados: 'Lacunas de Dados',
  saude_risco: 'Saúde × Risco',
  seguranca_publica: 'Segurança Pública',
  vulnerabilidade_multidimensional: 'Vulnerabilidade Multidimensional',
};

const legendByLayer: Record<string, LegendItem[]> = {
  municipio: [{ color: '#38bdf8', label: 'Limite municipal' }],
  bairros: [{ color: '#6366f1', label: 'Malha de bairros' }],
  territorios_especiais: TERRITORIO_LEGEND,
  infraestrutura: [
    { color: '#ef4444', label: 'Hospitais / UPAs' },
    { color: '#3b82f6', label: 'Escolas' },
    { color: '#c4b5fd', label: 'Vias arteriais' },
  ],
  educacao: EDUCACAO_ETAPAS.filter((e) => e.id !== 'todas').map((e) => ({
    color: e.color,
    label: e.label,
  })),
  socioeconomico: [
    { color: '#22c55e', label: 'Renda alta (terço superior)' },
    { color: '#eab308', label: 'Renda média (terço médio)' },
    { color: '#f97316', label: 'Renda baixa (terço inferior)' }
  ],
  cobertura: [
    { color: '#10b981', label: 'Vegetação / parque' },
    { color: '#0ea5e9', label: 'Corpo d\'água' },
    { color: '#71717a', label: 'Área construída/outros' }
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

export default function MapContainer({
  activeLayers,
  mapFocus,
  zoom,
  simGeoJSON,
  simContours,
  simFlowPaths,
  simOverlays = { showFlood: true, showContours: true, showFlow: true },
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

  const activeRasterLayers = activeLayers.filter(isExternalRasterLayer);

  const layerMetaById = Object.fromEntries(layerOptions.map((opt) => [opt.id, opt]));

  const activeLayersKey = activeLayers.join(',');
  const layerLoadGen = useRef(0);
  const loadedMunicipioRef = useRef<string | null>(null);

  // Fetch vector layers (raster layers use mosaicjson tile endpoints).
  useEffect(() => {
    const vectorLayers = activeLayersKey
      .split(',')
      .filter(Boolean)
      .filter((layerName) => !isExternalRasterLayer(layerName));

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

    let alive = true;
    const loadLayers = async () => {
      // Bairros primeiro — é a malha que o usuário espera ver.
      const ordered = [
        ...vectorLayers.filter((id) => id === 'bairros'),
        ...vectorLayers.filter((id) => id === 'municipio'),
        ...vectorLayers.filter((id) => id !== 'bairros' && id !== 'municipio'),
      ];

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
            continue;
          }
          setLayerData((prev) => ({ ...prev, [layerName]: data }));
          if (layerName === 'bairros' || layerName === 'municipio') {
            setMapSpatialReady(true);
          }
        } catch (err) {
          console.error(`Error loading layer ${layerName}:`, err);
        }
      }
      if (alive && layerLoadGen.current === gen) {
        setLoading(false);
        setMapSpatialReady(true);
      }
    };

    loadLayers().catch((err) => {
      console.error('Error loading layers:', err);
      if (alive && layerLoadGen.current === gen) {
        setLoading(false);
        setMapSpatialReady(true);
      }
    });

    return () => {
      alive = false;
    };
    // Não incluir layerAnoByTema/educacao/territorio aqui: mudam no boot e cancelavam o fetch de bairros.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeLayersKey, selectedMunicipio, setMapSpatialReady]);

  // Recarrega só camadas que dependem de ano/etapa quando esses filtros mudam.
  useEffect(() => {
    const dependent = activeLayers.filter(
      (id) => id === 'cobertura' || id === 'socioeconomico' || id === 'educacao' || id === 'territorios_especiais' || id === 'lst_observada',
    ).filter((id) => !isExternalRasterLayer(id));
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
  }, [educacaoEtapa, territorioTipo, layerAnoByTema, activeLayersKey, selectedMunicipio]);

  useEffect(() => {
    if (activeRasterLayers.length === 0) {
      setRasterConfigs({});
      setRasterLoading(false);
      return;
    }

    let cancelled = false;
    const loadRasters = async () => {
      setRasterLoading(true);
      try {
        const entries = await Promise.all(
          activeRasterLayers.map(async (layerId) => {
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
  }, [activeRasterLayers, selectedMunicipio, rasterRescale, layerAnoByTema.lst]);

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
    const thematicOnTop = activeLayers.some((l) =>
      ['cobertura', 'inundacao', 'vulnerabilidade', 'saneamento_drenagem', 'prioridade_planejamento', 'adaptacao_climatica', 'saude_risco', 'seguranca_publica', 'vulnerabilidade_multidimensional', 'lst_observada'].includes(l)
    );
    const simActive = Boolean(simGeoJSON) || (simContours?.features?.length ?? 0) > 0;
    if (layerName === 'bairros' && simActive) {
      return {
        ...withOpacity,
        fillOpacity: 0,
        fillColor: 'transparent',
        weight: 0.55,
        color: '#475569',
        opacity: 0.4 * layerOpacity,
      };
    }
    if (layerName === 'bairros' && thematicOnTop) {
      const coberturaActive = activeLayers.includes('cobertura');
      if (coberturaActive) {
        return {
          ...withOpacity,
          fillOpacity: 0,
          fillColor: 'transparent',
          weight: 1.6,
          color: '#e2e8f0',
          opacity: 0.9 * layerOpacity,
        };
      }
      // Mantém contorno legível mesmo com temáticas por cima
      return {
        ...withOpacity,
        fillOpacity: Math.min(withOpacity.fillOpacity, 0.18),
        weight: 1.4,
        color: '#c7d2fe',
        opacity: 0.9 * layerOpacity,
      };
    }
    if (layerName === 'cobertura' && activeLayers.includes('bairros')) {
      return { ...withOpacity, fillOpacity: Math.min(withOpacity.fillOpacity, 0.38) };
    }
    return withOpacity;
  };

  const layerRenderOrder = buildVectorRenderOrder(activeLayers);

  // Popup contents depending on layer properties
  const onEachFeature = (layerName: string) => (feature: any, layer: any) => {
    const props = feature.properties || {};
    let popupContent = '<div class="p-1 font-sans text-xs min-w-[180px]">';
    popupContent += `<p class="mb-1 text-[10px] font-bold uppercase tracking-wide text-indigo-300">${layerTitles[layerName] || layerName}</p>`;
    
    if (props.nome) {
      popupContent += `<h4 class="font-bold text-sm text-zinc-100 border-b border-zinc-700 pb-1 mb-1">${props.nome}</h4>`;
    }
    
    if (props.tipo) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Tipo:</span> <span class="capitalize">${props.tipo}</span></p>`;
      if (props.subgrupo) popupContent += `<p class="mb-1"><span class="text-zinc-400">Subgrupo:</span> <span class="capitalize text-zinc-300">${props.subgrupo.replace('_', ' ')}</span></p>`;
    }

    if (props.tipo_label || props.tipo) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Tipo:</span> <span class="font-semibold text-fuchsia-200">${props.tipo_label || props.tipo}</span></p>`;
    }
    if (props.populacao_estimada != null) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">População est.:</span> ${Number(props.populacao_estimada).toLocaleString('pt-BR')}</p>`;
    }
    if (props.codigo_oficial) {
      popupContent += `<p class="mb-1 text-[10px] text-zinc-500">Código: ${props.codigo_oficial}</p>`;
    }

    if (props.codigo_inep) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Código INEP:</span> ${props.codigo_inep}</p>`;
    }
    if (props.dependencia) {
      const dep = DEPENDENCIA_LABELS[props.dependencia] || props.dependencia;
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Dependência:</span> ${dep}</p>`;
    }
    if (props.matriculas_ativas != null) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Matrículas (etapa):</span> <span class="font-semibold text-sky-200">${Number(props.matriculas_ativas).toLocaleString('pt-BR')}</span></p>`;
    }
    if (props.matriculas_total != null) {
      popupContent += `<p class="mb-1 text-[10px] text-zinc-500">Total escola: ${Number(props.matriculas_total).toLocaleString('pt-BR')} · Inf ${props.matriculas_infantil ?? 0} · Fund ${props.matriculas_fundamental ?? 0} · Méd ${props.matriculas_medio ?? 0}</p>`;
    }
    
    if (props.codigo_bairro) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Código Bairro:</span> ${props.codigo_bairro}</p>`;
    }
    
    if (props.populacao) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">População:</span> ${props.populacao.toLocaleString()}</p>`;
    }
    
    if (props.renda_media) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Renda Média:</span> R$ ${props.renda_media.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>`;
    }
    if (props.classe_renda) {
      const cls = props.classe_renda === 'ALTA' ? 'alta' : props.classe_renda === 'MEDIA' ? 'média' : 'baixa';
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Classe (no município):</span> <span class="font-semibold">${cls}</span></p>`;
    }
    if (props.deficits_censo && typeof props.deficits_censo === 'object') {
      const d = props.deficits_censo as Record<string, number>;
      const labels: Record<string, string> = {
        arborizacao: 'Sem arborização',
        calcada: 'Sem calçada',
        iluminacao: 'Sem iluminação',
        agua: 'Sem rede de água',
        esgoto: 'Esgoto inadequado',
        lixo: 'Lixo sem coleta',
        alfabetizacao: 'Baixa alfabetização',
      };
      popupContent += `<p class="mt-2 mb-1 text-[10px] font-bold uppercase text-amber-300">Déficits Censo 2022</p>`;
      Object.entries(labels).forEach(([key, label]) => {
        if (d[key] != null) {
          popupContent += `<p class="mb-0.5 text-[10px] text-zinc-400">${label}: <span class="text-amber-200">${d[key]}%</span></p>`;
        }
      });
    }

    if (props.densidade_demografica) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Densidade:</span> ${props.densidade_demografica.toLocaleString()} hab/km²</p>`;
    }
    
    if (props.nivel_alerta) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Nível do Alerta:</span> <span class="font-bold text-red-400">${props.nivel_alerta}</span></p>`;
      if (props.descricao) popupContent += `<p class="mt-2 text-zinc-300 italic border-l-2 border-amber-500 pl-2 text-[10px]">${props.descricao}</p>`;
    }
    
    if (props.classe_uso) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Uso do Solo (MapBiomas):</span> <span class="font-semibold text-zinc-300">${props.classe_uso}</span></p>`;
    }

    if (props.indice_vulnerabilidade !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">IVC:</span> <span class="font-bold text-rose-300">${props.indice_vulnerabilidade}</span></p>`;
    }

    if (props.indice_risco_inundacao !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">IRI:</span> <span class="font-bold text-sky-300">${props.indice_risco_inundacao}</span></p>`;
      if (props.hidrografia_proximidade_score !== undefined) {
        popupContent += `<p class="mb-1 text-[10px] text-zinc-500">Prox. hidrografia: ${props.hidrografia_proximidade_score} · Impermeab.: ${props.impermeabilizacao_score ?? '—'}</p>`;
      }
    }

    if (props.capacidade_adaptacao !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Adaptação:</span> <span class="font-bold text-emerald-300">${props.capacidade_adaptacao}</span></p>`;
    }

    if (props.prioridade_planejamento !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Prioridade:</span> <span class="font-bold text-fuchsia-300">${props.prioridade_planejamento}</span>`;
      if (props.classe_prioridade) {
        popupContent += ` <span class="text-[10px] text-fuchsia-200/80">(${props.classe_prioridade})</span>`;
      }
      popupContent += `</p>`;
      if (props.classificacao_relativa) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-500">Classe relativa ao município (tertil intra-urbano)</p>`;
      }
    }

    if (props.risco_drenagem !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Risco drenagem:</span> <span class="font-bold text-cyan-300">${props.risco_drenagem}</span>`;
      if (props.classe_drenagem) {
        popupContent += ` <span class="text-[10px] text-cyan-200/80">(${props.classe_drenagem})</span>`;
      }
      popupContent += `</p>`;
      if (props.impermeabilizacao_score !== undefined) {
        popupContent += `<p class="mb-1 text-[10px] text-zinc-500">IRI ${props.indice_risco_inundacao ?? '—'} · Impermeab. ${props.impermeabilizacao_score} · Hidrografia ${props.hidrografia_proximidade_score ?? '—'}</p>`;
      }
      if (props.snis?.deficit_saneamento_pct !== undefined) {
        popupContent += `<p class="mb-1 text-[10px] text-zinc-500">Déficit SNIS esgoto/água: ${props.snis.deficit_saneamento_pct}% (${props.snis.ano_referencia ?? '—'})</p>`;
      }
      if (props.score_explicacao) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-600">${props.score_explicacao}</p>`;
      }
    }

    if (props.maturidade_dados !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Maturidade dos dados:</span> <span class="font-bold text-indigo-300">${props.maturidade_dados}%</span></p>`;
      if (props.lacunas_prioritarias) {
        popupContent += `<p class="mb-1"><span class="text-zinc-400">Lacunas:</span> <span class="text-zinc-300">${props.lacunas_prioritarias}</span></p>`;
      }
    }

    if (props.tipo && props.feature_kind === 'estabelecimento') {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Tipo:</span> ${props.tipo}${props.leitos_sus ? ` · ${props.leitos_sus} leitos SUS` : ''}</p>`;
    }
    if (props.pressao_assistencial !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Pressão assistencial:</span> <span class="font-bold">${props.pressao_assistencial}</span></p>`;
    }
    if (props.cobertura_classe) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Classe:</span> <span class="font-bold">${props.cobertura_classe}</span></p>`;
    }

    if (props.bairro) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Bairro:</span> ${props.bairro}</p>`;
    }
    if (props.cobertura_classe) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Cobertura:</span> <span class="font-bold">${props.cobertura_classe}</span></p>`;
    }
    if (props.distancia_maior_risco_km !== undefined && props.distancia_maior_risco_km !== null) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Dist. maior risco:</span> ${props.distancia_maior_risco_km} km</p>`;
    }
    if (props.taxa_violenta_100k !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Taxa violenta / 100k:</span> ${props.taxa_violenta_100k}</p>`;
    }
    if (props.intensidade_seguranca !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Intensidade local:</span> <span class="font-bold text-orange-300">${props.intensidade_seguranca}</span>`;
      if (props.classe_intensidade) {
        popupContent += ` <span class="text-[10px] text-orange-200/80">(${props.classe_intensidade})</span>`;
      }
      popupContent += `</p>`;
      if (props.classificacao_relativa) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-500">Classe relativa ao município (tertil intra-urbano)</p>`;
      }
      if (props.score_explicacao) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-600">${props.score_explicacao}</p>`;
      }
    }

    if (props.indice_vm !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Índice VM:</span> <span class="font-bold text-purple-300">${props.indice_vm}</span>`;
      if (props.classe_vm) {
        popupContent += ` <span class="text-[10px] text-purple-200/80">(${props.classe_vm})</span>`;
      }
      popupContent += `</p>`;
      if (props.classificacao_relativa) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-500">Classe relativa ao município (tertil intra-urbano)</p>`;
      }
      if (props.score_explicacao) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-600">${props.score_explicacao}</p>`;
      }
    }
    if (props.vulnerabilidade_multidimensional) {
      popupContent += `<p class="mb-1 font-bold text-fuchsia-300">⚠ Vulnerabilidade multidimensional</p>`;
    }

    if (props.score_componentes && props.layer === 'prioridade_planejamento') {
      popupContent += `
        <div class="mt-2 rounded-md border border-fuchsia-500/30 bg-fuchsia-950/30 p-2">
          <p class="mb-1 text-[10px] font-bold uppercase text-fuchsia-200">Composição do score</p>
          <p class="text-[10px] text-zinc-300">Vulnerabilidade: +${props.score_componentes.vulnerabilidade_pct} pts</p>
          <p class="text-[10px] text-zinc-300">Inundação: +${props.score_componentes.inundacao_pct} pts</p>
          <p class="text-[10px] text-zinc-300">Déficit de adaptação: +${props.score_componentes.deficit_adaptacao_pct} pts</p>
          ${props.score_explicacao ? `<p class="mt-1 text-[9px] text-zinc-500">${props.score_explicacao}</p>` : ''}
        </div>
      `;
    } else if (props.score_componentes) {
      popupContent += `
        <div class="mt-2 rounded-md border border-fuchsia-500/30 bg-fuchsia-950/30 p-2">
          <p class="mb-1 text-[10px] font-bold uppercase text-fuchsia-200">Por que este score?</p>
          <p class="text-[10px] text-zinc-300">Vulnerabilidade: +${props.score_componentes.vulnerabilidade_pct} pts</p>
          <p class="text-[10px] text-zinc-300">Inundação: +${props.score_componentes.inundacao_pct} pts</p>
          <p class="text-[10px] text-zinc-300">Déficit de adaptação: +${props.score_componentes.deficit_adaptacao_pct} pts</p>
          ${props.score_explicacao ? `<p class="mt-1 text-[9px] text-zinc-500">${props.score_explicacao}</p>` : ''}
        </div>
      `;
    }

    if (props.qualidade_dado) {
      const q = props.qualidade_dado;
      const qualityColor =
        q === 'Oficial'
          ? 'text-emerald-300 border-emerald-500/40 bg-emerald-950/30'
          : q === 'Referencia'
            ? 'text-sky-300 border-sky-500/40 bg-sky-950/30'
            : q === 'Estimado'
              ? 'text-amber-300 border-amber-500/40 bg-amber-950/30'
              : 'text-zinc-300 border-zinc-500/40 bg-zinc-950/30';
      popupContent += `<p class="mt-2"><span class="rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase ${qualityColor}">${props.qualidade_dado}</span></p>`;
    }

    if (props.fonte_referencia) {
      popupContent += `<p class="mt-2 border-t border-zinc-800 pt-1 text-[10px] text-zinc-500">${props.fonte_referencia}</p>`;
    }

    popupContent += '</div>';
    layer.bindPopup(popupContent);
  };

  const pointToLayer = (layerName: string) => (feature: any, latlng: L.LatLngExpression) => {
    if (layerName === 'saude_risco') {
      if (feature?.properties?.feature_kind !== 'estabelecimento') {
        return L.circleMarker(latlng, { radius: 0, fillOpacity: 0, opacity: 0 });
      }
      const cls = feature?.properties?.cobertura_classe;
      const color = cls === 'ADEQUADA' ? '#16a34a' : cls === 'ATENCAO' ? '#eab308' : '#ef4444';
      const tipo = feature?.properties?.tipo;
      const radius = tipo === 'HOSPITAL' ? 10 : tipo === 'SAMU' ? 9 : 7;
      return L.circleMarker(latlng, { radius, fillColor: color, color: '#fff', weight: 2, fillOpacity: 0.95 });
    }
    if (layerName === 'infraestrutura') {
      const tipo = feature?.properties?.tipo;
      if (tipo === 'hospital') {
        return L.circleMarker(latlng, { radius: 8, fillColor: '#ef4444', color: '#fff', weight: 2, fillOpacity: 0.9 });
      }
      if (tipo === 'escola') {
        return L.circleMarker(latlng, { radius: 6, fillColor: '#3b82f6', color: '#fff', weight: 2, fillOpacity: 0.9 });
      }
      return L.circleMarker(latlng, { radius: 5, fillColor: '#a78bfa', color: '#fff', weight: 1.5, fillOpacity: 0.85 });
    }
    if (layerName === 'educacao') {
      const props = feature?.properties || {};
      const color = getEducacaoEtapa(educacaoEtapa).color;
      const matriculas = Number(props.matriculas_ativas ?? props.matriculas_total ?? 0);
      const radius = markerRadiusFromMatriculas(matriculas);
      const marker = L.circleMarker(latlng, {
        radius,
        fillColor: color,
        color: '#fff',
        weight: 2,
        fillOpacity: 0.9,
      });
      if (!showEducacaoBuffer) return marker;
      const buffer = L.circle(latlng, {
        radius: educacaoRaioM,
        color,
        weight: 1,
        opacity: 0.45,
        fillColor: color,
        fillOpacity: 0.06,
      });
      return L.layerGroup([buffer, marker]);
    }
    const color = layerName === 'desastres' ? '#ef4444' : '#a78bfa';
    return L.circleMarker(latlng, {
      radius: layerName === 'desastres' ? 7 : 5,
      fillColor: color,
      color: '#f8fafc',
      weight: 1.5,
      opacity: 1,
      fillOpacity: 0.85
    });
  };

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-border bg-zinc-950">
      {/* Loading Overlay */}
      {loading || rasterLoading ? (
        <div className="absolute inset-0 bg-background/60 backdrop-blur-sm z-[1000] flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
            <span className="text-zinc-300 text-sm font-medium">Carregando dados espaciais...</span>
          </div>
        </div>
      ) : null}

      <LeafletMap
        center={mapFocus}
        zoom={zoom}
        className="w-full h-full"
        zoomControl={false}
      >
        <MapController center={mapFocus} zoom={zoom} />
        <FitBoundsToBaseLayers
          selectedMunicipio={selectedMunicipio}
          municipioFc={layerData.municipio}
          bairrosFc={layerData.bairros}
          regionalActive={showRegionalOverlay}
        />
        
        {/* Custom Dark-Themed Basemap */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
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
          layerData[layerName] && (
            <GeoJSON
              key={`${layerName}-${socioSubcamada}-${educacaoEtapa}-${territorioTipo}-${educacaoRaioM}-${showEducacaoBuffer}-${layerOpacityById[layerName] ?? 1}-${layerData[layerName].features?.length || 0}`}
              data={layerData[layerName]}
              style={(feature) => getLayerStyleForFeature(layerName, feature)}
              pointToLayer={pointToLayer(layerName)}
              onEachFeature={onEachFeature(layerName)}
            />
          )
        ))}

        {showRegionalOverlay && regionalData?.geojson?.features?.length ? (
          <GeoJSON
            key={`regional-${regionalEscopo}-${regionalData.geojson.features.length}`}
            data={regionalData.geojson}
            style={(feature) => {
              const kind = feature?.properties?.feature_kind;
              if (kind === 'referencia_comparacao') {
                return {
                  fillColor: '#f59e0b',
                  fillOpacity: 0.08,
                  color: '#fbbf24',
                  weight: 2.2,
                  opacity: 0.9,
                  dashArray: '8,5',
                };
              }
              return {
                fillColor: '#22d3ee',
                fillOpacity: 0.04,
                color: '#22d3ee',
                weight: 1.6,
                opacity: 0.75,
                dashArray: '6,4',
              };
            }}
            onEachFeature={(feature, layer) => {
              const props = feature.properties || {};
              const kind = props.feature_kind === 'referencia_comparacao' ? 'Referência de comparação' : 'Município regional';
              let content = `<div class="p-2 font-sans text-xs min-w-[180px]">
                <p class="mb-1 text-[10px] font-bold uppercase tracking-wide text-teal-300">${kind}</p>
                <h4 class="font-bold text-sm text-zinc-100 border-b border-zinc-700 pb-1 mb-1">${props.nome || 'Município'}</h4>`;
              if (props.uf) content += `<p class="text-zinc-400">${props.uf}</p>`;
              content += '</div>';
              layer.bindPopup(content);
            }}
          />
        ) : null}

        {/* Manchas de simulação por profundidade */}
        {simGeoJSON && simOverlays.showFlood && (
          <GeoJSON
            key={`sim-${JSON.stringify(simGeoJSON).slice(0, 80)}`}
            data={simGeoJSON}
            style={(feature) => getSimulationFeatureStyle(feature)}
            onEachFeature={(feature, layer) => {
              const props = feature.properties || {};
              let content = `<div class="p-2 font-sans text-xs">
                <h4 class="font-bold text-sm text-zinc-100 mb-1 border-b border-zinc-700 pb-1">${props.name || 'Mancha Simulada'}</h4>`;
              if (props.temp_increase_celsius != null) {
                content += `<p class="text-red-400 font-semibold">ΔT: +${props.temp_increase_celsius}°C</p>`;
                if (props.temp_surface_celsius != null) {
                  content += `<p class="text-orange-300">Superfície est.: ${props.temp_surface_celsius}°C</p>`;
                }
                if (props.heat_band) {
                  content += `<p class="text-amber-300">Faixa: ${props.heat_band}</p>`;
                }
                if (props.vegetacao_pct != null) {
                  content += `<p class="text-lime-300">Vegetação: ${props.vegetacao_pct}%</p>`;
                }
              }
              if (props.precipitation_mm) {
                content += `<p class="text-sky-400 font-semibold">Chuva: ${props.precipitation_mm} mm</p>`;
              }
              if (props.water_level_m) {
                content += `<p class="text-sky-300">Cota simulada: ${props.water_level_m} m</p>`;
              }
              if (props.depth_band) {
                content += `<p class="text-blue-300">Faixa: ${props.depth_band}</p>`;
              }
              if (props.intensity_pct) {
                content += `<p class="text-sky-400 font-semibold">Impermeabilização: +${props.intensity_pct}%</p>`;
              }
              if (props.description) content += `<p class="mt-1 text-zinc-400 text-[10px]">${props.description}</p>`;
              content += '</div>';
              layer.bindPopup(content);
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
              const elev = feature.properties?.elevation_m;
              const res = feature.properties?.dem_resolution_m;
              const indexed = feature.properties?.index_contour;
              if (elev != null) {
                const tip = res != null
                  ? `${indexed ? 'Cota indexada ' : 'Cota '}${elev} m · DEM ~${res} m`
                  : `Cota ${elev} m`;
                layer.bindTooltip(tip, { sticky: true, className: 'text-[10px]' });
              }
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

      </LeafletMap>

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

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-zinc-700/80 bg-zinc-950/95 text-[11px] text-zinc-200 shadow-2xl shadow-black/50 backdrop-blur-md">
        <div className="shrink-0 border-b border-zinc-800 bg-zinc-950/95 px-4 py-3">
          <h5 className="text-sm font-extrabold text-zinc-50">Legenda Territorial</h5>
          <p className="mt-0.5 text-[10px] text-zinc-500">Camadas do município selecionado no header.</p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 pr-5">
          {activeLayers.length === 0 && !simGeoJSON && (
            <span className="text-zinc-500 italic">Nenhuma camada ativada no momento.</span>
          )}
          {activeLayers.map((layerName) => (
            <div key={layerName} className="mb-3 last:mb-0">
              <p className="mb-1.5 text-[10px] font-extrabold uppercase tracking-wider text-indigo-300">
                {layerTitles[layerName] || layerName}
              </p>
              {layerMetaById[layerName] && (
                <LayerMetaBlock layer={layerMetaById[layerName]} compact />
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
                    Raster externo (mosaicjson GeoReDUS) — sem ingestão PostGIS no Sinidu.
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
                    Etapa: {getEducacaoEtapa(educacaoEtapa).label} · Tamanho ∝ matrículas
                  </p>
                  {showEducacaoBuffer && (
                    <p className="text-[9px] leading-snug text-indigo-300/80">
                      Buffer de influência: {educacaoRaioM} m
                    </p>
                  )}
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
          ))}
          {simGeoJSON && (
            <div className="mt-3 border-t border-zinc-800 pt-3 flex flex-col gap-2">
              <p className="mb-1 text-[10px] font-extrabold uppercase tracking-wider text-indigo-300">Simulação hidrológica</p>
              <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm border border-sky-900 bg-sky-400/50" />Alagamento superficial</div>
              <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm border border-sky-800 bg-sky-600/60" />Alagamento moderado</div>
              <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm border border-indigo-950 bg-indigo-900/70" />Alagamento crítico</div>
              <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm border border-red-900 bg-red-600/55" />Deslizamento / ilha de calor</div>
              {simContours?.features?.length > 0 && simOverlays.showContours && (
                <div className="flex items-center gap-2"><span className="h-0.5 w-4 bg-lime-300" />Curvas indexadas (DEM)</div>
              )}
              {simContours?.features?.length > 0 && simOverlays.showContours && (
                <div className="flex items-center gap-2"><span className="h-0.5 w-4 bg-lime-500" />Curvas intermediárias</div>
              )}
              {simFlowPaths?.features?.length > 0 && (
                <div className="flex items-center gap-2"><span className="h-0.5 w-4 border-t-2 border-dashed border-cyan-400" />Escoamento superficial</div>
              )}
            </div>
          )}
          {showRegionalOverlay && (
            <div className="mt-3 border-t border-zinc-800 pt-3 flex flex-col gap-2">
              <p className="mb-1 text-[10px] font-extrabold uppercase tracking-wider text-teal-300">Contexto regional</p>
              <div className="flex items-center gap-2">
                <span className="h-0.5 w-4 border-t-2 border-dashed border-cyan-400" />
                Municípios do escopo
              </div>
              <div className="flex items-center gap-2">
                <span className="h-0.5 w-4 border-t-2 border-dashed border-amber-400" />
                Referência de comparação
              </div>
            </div>
          )}
        </div>
        </div>
      </div>
    </div>
  );
}
