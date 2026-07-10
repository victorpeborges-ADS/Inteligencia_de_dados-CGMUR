import { create } from 'zustand';

import { DEFAULT_LAYER_OPTIONS, type ActiveTab, type LayerOption } from '@/config/platformTabs';
import { DEFAULT_SOCIO_SUBCAMADA, type SocioSubcamadaId } from '@/config/socioeconomicoSubcamadas';
import type { TemporalTemaId, TemporalOptionsResponse } from '@/config/layerTemporal';
import {
  DEFAULT_EDUCACAO_ETAPA,
  DEFAULT_EDUCACAO_RAIO_M,
  type EducacaoEtapaId,
} from '@/config/educacaoInep';
import {
  DEFAULT_TERRITORIO_TIPO,
  type TerritorioTipoId,
} from '@/config/territoriosEspeciais';
import { DEFAULT_MAP_LAYERS } from '@/utils/municipalitySync';
import { moveLayerInStack } from '@/utils/activeLayerOrder';
import type { MunicipalityOption } from '@/utils/api';
import { SEED_MUNICIPALITIES } from '@/data/municipalities_seed';

export type AgentMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  ts: number;
  proactive?: boolean;
};

type AppStore = {
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  selectedMunicipio: string;
  setSelectedMunicipio: (codigo: string) => void;
  municipalities: MunicipalityOption[];
  setMunicipalities: (
    value: MunicipalityOption[] | ((prev: MunicipalityOption[]) => MunicipalityOption[]),
  ) => void;
  activeLayers: string[];
  setActiveLayers: (layers: string[] | ((prev: string[]) => string[])) => void;
  toggleLayer: (layerId: string) => void;
  layerOpacityById: Record<string, number>;
  setLayerOpacity: (layerId: string, opacity: number) => void;
  moveActiveLayer: (layerId: string, direction: 'up' | 'down') => void;
  layerOptions: LayerOption[];
  setLayerOptions: (
    value: LayerOption[] | ((prev: LayerOption[]) => LayerOption[]),
  ) => void;
  mapFocus: [number, number];
  setMapFocus: (coords: [number, number]) => void;
  zoom: number;
  setZoom: (zoom: number) => void;
  apiOnline: boolean | null;
  setApiOnline: (online: boolean | null) => void;
  municipioEnsuring: boolean;
  setMunicipioEnsuring: (value: boolean) => void;
  municipioEnsureError: string | null;
  setMunicipioEnsureError: (value: string | null) => void;
  /** True quando malha municipal/bairros já chegou — painel deve esperar para não saturar o backend. */
  mapSpatialReady: boolean;
  setMapSpatialReady: (value: boolean) => void;
  alertNivel: string;
  setAlertNivel: (nivel: string) => void;
  resetMapLayers: () => void;
  socioSubcamada: SocioSubcamadaId;
  setSocioSubcamada: (id: SocioSubcamadaId) => void;
  educacaoEtapa: EducacaoEtapaId;
  setEducacaoEtapa: (id: EducacaoEtapaId) => void;
  educacaoRaioM: number;
  setEducacaoRaioM: (value: number) => void;
  showEducacaoBuffer: boolean;
  setShowEducacaoBuffer: (value: boolean) => void;
  territorioTipo: TerritorioTipoId;
  setTerritorioTipo: (id: TerritorioTipoId) => void;
  temporalOptions: TemporalOptionsResponse | null;
  setTemporalOptions: (value: TemporalOptionsResponse | null) => void;
  layerAnoByTema: Partial<Record<TemporalTemaId, number>>;
  setLayerAnoForTema: (temaId: TemporalTemaId, ano: number | null) => void;
  initLayerAnoFromTemporal: (temas: Record<string, { tema_id: string; padrao: number | null }>) => void;
  showRegionalOverlay: boolean;
  setShowRegionalOverlay: (value: boolean) => void;
  regionalEscopo: 'regiao_imediata' | 'mesorregiao';
  setRegionalEscopo: (escopo: 'regiao_imediata' | 'mesorregiao') => void;
  compareModalOpen: boolean;
  setCompareModalOpen: (open: boolean) => void;
  agenteAberto: boolean;
  setAgenteAberto: (aberto: boolean) => void;
  agenteMensagens: AgentMessage[];
  addAgenteMensagem: (msg: Omit<AgentMessage, 'id' | 'ts'> & Partial<Pick<AgentMessage, 'id' | 'ts'>>) => void;
  clearAgenteMensagens: () => void;
  agenteNaoLidas: number;
  markAgenteLidas: () => void;
  pushAgenteProativo: (content: string) => void;
  agenteLoading: boolean;
  setAgenteLoading: (loading: boolean) => void;
  proactiveShownKeys: string[];
  markProactiveShown: (key: string) => void;
  hasProactiveShown: (key: string) => boolean;
  notifyDiagnosticGenerated: (payload: {
    versao?: string;
    score?: number;
    prioridade?: string;
    riscos?: string[];
  }) => void;
  reportRequest: 'rapido' | 'completo' | null;
  requestReport: (type: 'rapido' | 'completo') => void;
  clearReportRequest: () => void;
  focusMode: boolean;
  setFocusMode: (value: boolean) => void;
  toggleFocusMode: () => void;
};

export const FOCUS_MODE_STORAGE_KEY = 'sinidu-focus-mode';

let msgCounter = 0;

function nextMsgId() {
  msgCounter += 1;
  return `agent-${Date.now()}-${msgCounter}`;
}

export const useAppStore = create<AppStore>((set, get) => ({
  activeTab: 'dashboard',
  setActiveTab: (tab) => set({ activeTab: tab }),
  selectedMunicipio: '2611606',
  setSelectedMunicipio: (codigo) =>
    set({ selectedMunicipio: codigo, mapSpatialReady: false }),
  municipalities: SEED_MUNICIPALITIES,
  setMunicipalities: (value) =>
    set({
      municipalities: typeof value === 'function' ? value(get().municipalities) : value,
    }),
  activeLayers: [...DEFAULT_MAP_LAYERS],
  setActiveLayers: (value) =>
    set({
      activeLayers: typeof value === 'function' ? value(get().activeLayers) : value,
    }),
  toggleLayer: (layerId) =>
    set((state) => ({
      activeLayers: state.activeLayers.includes(layerId)
        ? state.activeLayers.filter((id) => id !== layerId)
        : [...state.activeLayers, layerId],
    })),
  layerOpacityById: {},
  setLayerOpacity: (layerId, opacity) =>
    set((state) => ({
      layerOpacityById: {
        ...state.layerOpacityById,
        [layerId]: Math.min(1, Math.max(0.15, opacity)),
      },
    })),
  moveActiveLayer: (layerId, direction) =>
    set((state) => {
      const next = moveLayerInStack(state.activeLayers, layerId, direction);
      return next ? { activeLayers: next } : state;
    }),
  layerOptions: DEFAULT_LAYER_OPTIONS,
  setLayerOptions: (value) =>
    set({
      layerOptions: typeof value === 'function' ? value(get().layerOptions) : value,
    }),
  mapFocus: [-8.0578, -34.9004],
  setMapFocus: (coords) => set({ mapFocus: coords }),
  zoom: 12,
  setZoom: (zoom) => set({ zoom }),
  apiOnline: null,
  setApiOnline: (online) => set({ apiOnline: online }),
  municipioEnsuring: false,
  setMunicipioEnsuring: (value) => set({ municipioEnsuring: value }),
  municipioEnsureError: null,
  setMunicipioEnsureError: (value) => set({ municipioEnsureError: value }),
  mapSpatialReady: false,
  setMapSpatialReady: (value) => set({ mapSpatialReady: value }),
  alertNivel: 'VERDE',
  setAlertNivel: (nivel) => set({ alertNivel: nivel }),
  resetMapLayers: () => set({ activeLayers: [...DEFAULT_MAP_LAYERS] }),
  socioSubcamada: DEFAULT_SOCIO_SUBCAMADA,
  setSocioSubcamada: (id) => set({ socioSubcamada: id }),
  educacaoEtapa: DEFAULT_EDUCACAO_ETAPA,
  setEducacaoEtapa: (id) => set({ educacaoEtapa: id }),
  educacaoRaioM: DEFAULT_EDUCACAO_RAIO_M,
  setEducacaoRaioM: (value) => set({ educacaoRaioM: value }),
  showEducacaoBuffer: true,
  setShowEducacaoBuffer: (value) => set({ showEducacaoBuffer: value }),
  territorioTipo: DEFAULT_TERRITORIO_TIPO,
  setTerritorioTipo: (id) => set({ territorioTipo: id }),
  temporalOptions: null,
  setTemporalOptions: (value) => set({ temporalOptions: value }),
  layerAnoByTema: {},
  setLayerAnoForTema: (temaId, ano) =>
    set((state) => {
      const next = { ...state.layerAnoByTema };
      if (ano == null) {
        delete next[temaId];
      } else {
        next[temaId] = ano;
      }
      return { layerAnoByTema: next };
    }),
  initLayerAnoFromTemporal: (temas) => {
    const next: Partial<Record<TemporalTemaId, number>> = {};
    Object.values(temas).forEach((tema) => {
      if (tema.padrao != null) {
        next[tema.tema_id as TemporalTemaId] = tema.padrao;
      }
    });
    set((state) => {
      const prev = state.layerAnoByTema;
      const prevKeys = Object.keys(prev);
      const nextKeys = Object.keys(next);
      if (
        prevKeys.length === nextKeys.length
        && nextKeys.every((key) => prev[key as TemporalTemaId] === next[key as TemporalTemaId])
      ) {
        return state;
      }
      return { layerAnoByTema: next };
    });
  },
  showRegionalOverlay: false,
  setShowRegionalOverlay: (value) => set({ showRegionalOverlay: value }),
  regionalEscopo: 'regiao_imediata',
  setRegionalEscopo: (escopo) => set({ regionalEscopo: escopo }),
  compareModalOpen: false,
  setCompareModalOpen: (open) => set({ compareModalOpen: open }),
  agenteAberto: false,
  setAgenteAberto: (aberto) =>
    set((state) => ({
      agenteAberto: aberto,
      agenteNaoLidas: aberto ? 0 : state.agenteNaoLidas,
    })),
  agenteMensagens: [],
  addAgenteMensagem: (msg) =>
    set((state) => ({
      agenteMensagens: [
        ...state.agenteMensagens,
        {
          id: msg.id || nextMsgId(),
          ts: msg.ts ?? Date.now(),
          role: msg.role,
          content: msg.content,
          proactive: msg.proactive,
        },
      ],
    })),
  clearAgenteMensagens: () => set({ agenteMensagens: [], agenteNaoLidas: 0 }),
  agenteNaoLidas: 0,
  markAgenteLidas: () => set({ agenteNaoLidas: 0 }),
  pushAgenteProativo: (content) =>
    set((state) => ({
      agenteMensagens: [
        ...state.agenteMensagens,
        {
          id: nextMsgId(),
          ts: Date.now(),
          role: 'assistant',
          content,
          proactive: true,
        },
      ],
      agenteNaoLidas: state.agenteAberto ? 0 : state.agenteNaoLidas + 1,
    })),
  agenteLoading: false,
  setAgenteLoading: (loading) => set({ agenteLoading: loading }),
  proactiveShownKeys: [],
  markProactiveShown: (key) =>
    set((state) => ({
      proactiveShownKeys: state.proactiveShownKeys.includes(key)
        ? state.proactiveShownKeys
        : [...state.proactiveShownKeys, key],
    })),
  hasProactiveShown: (key) => get().proactiveShownKeys.includes(key),
  notifyDiagnosticGenerated: (payload) => {
    const versao = payload.versao || 'v12';
    const score = payload.score ?? '?';
    const prioridade = payload.prioridade || 'Alta';
    const riscos = (payload.riscos || []).slice(0, 3).join(', ') || 'não listados';
    const content =
      `Diagnóstico **${versao}** gerado. Score **${score}** = prioridade **${prioridade}**. ` +
      `Principais riscos: ${riscos}. Quer que eu prepare um resumo executivo para apresentação?`;
    get().pushAgenteProativo(content);
    if (!get().agenteAberto) {
      set({ agenteAberto: true, agenteNaoLidas: 0 });
    }
  },
  reportRequest: null,
  requestReport: (type) => set({ reportRequest: type, activeTab: 'dashboard' }),
  clearReportRequest: () => set({ reportRequest: null }),
  focusMode: false,
  setFocusMode: (value) => set({ focusMode: value }),
  toggleFocusMode: () => set((state) => ({ focusMode: !state.focusMode })),
}));
