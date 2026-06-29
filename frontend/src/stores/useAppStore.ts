import { create } from 'zustand';

import { DEFAULT_LAYER_OPTIONS, type ActiveTab, type LayerOption } from '@/config/platformTabs';
import { DEFAULT_MAP_LAYERS } from '@/utils/municipalitySync';
import type { MunicipalityOption } from '@/utils/api';
import { SEED_MUNICIPALITIES } from '@/data/municipalities_seed';

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
};

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
}));
