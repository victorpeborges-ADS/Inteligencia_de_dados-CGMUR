import { create } from 'zustand';

import { DEFAULT_LAYER_OPTIONS, type ActiveTab, type LayerOption } from '@/config/platformTabs';
import { DEFAULT_MAP_LAYERS } from '@/utils/municipalitySync';
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
  alertNivel: string;
  setAlertNivel: (nivel: string) => void;
  resetMapLayers: () => void;
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
  setSelectedMunicipio: (codigo) => set({ selectedMunicipio: codigo }),
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
  alertNivel: 'VERDE',
  setAlertNivel: (nivel) => set({ alertNivel: nivel }),
  resetMapLayers: () => set({ activeLayers: [...DEFAULT_MAP_LAYERS] }),
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
