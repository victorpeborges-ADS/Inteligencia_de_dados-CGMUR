'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Building2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  CloudRain,
  Eye,
  HeartPulse,
  Layers,
  Map,
  type LucideIcon,
} from 'lucide-react';
import type { LayerOption } from '@/config/platformTabs';

/** Presets documentados — ver CHECKLIST_FASE_13.md */
export const LAYER_PRESETS = {
  cruzarRiscos: {
    id: 'cruzar_riscos',
    label: 'Cruzar riscos',
    description: 'Bairros + vulnerabilidade climática + risco de inundação',
    layers: ['bairros', 'vulnerabilidade', 'inundacao'],
  },
} as const;

const GROUP_ICONS: Record<LayerOption['group'], LucideIcon> = {
  Base: Map,
  'Dados urbanos': Building2,
  'Clima e riscos': CloudRain,
  Planejamento: ClipboardList,
  'Saúde e segurança': HeartPulse,
};

const PANEL_COLLAPSED_KEY = 'sinidu-layer-panel-collapsed';
const GROUPS_COLLAPSED_KEY = 'sinidu-layer-groups-collapsed';

type LayerPanelProps = {
  activeLayers: string[];
  setActiveLayers: (layers: string[]) => void;
  toggleLayer: (layerId: string) => void;
  layerOptions: LayerOption[];
  malhaIndisponivel?: boolean;
  className?: string;
};

function qualityTone(quality: LayerOption['quality']) {
  if (quality === 'Oficial') return 'border-emerald-400/40 bg-emerald-500/10 text-emerald-300';
  if (quality === 'Referencia') return 'border-cyan-400/40 bg-cyan-500/10 text-cyan-300';
  if (quality === 'Estimado') return 'border-amber-400/40 bg-amber-500/10 text-amber-300';
  if (quality === 'Indisponível') return 'border-rose-400/40 bg-rose-500/10 text-rose-300';
  return 'border-sky-400/40 bg-sky-500/10 text-sky-300';
}

export default function LayerPanel({
  activeLayers,
  setActiveLayers,
  toggleLayer,
  layerOptions,
  malhaIndisponivel = false,
  className = '',
}: LayerPanelProps) {
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  const layerGroups = useMemo(
    () => Array.from(new Set(layerOptions.map((opt) => opt.group))),
    [layerOptions],
  );

  useEffect(() => {
    try {
      if (localStorage.getItem(PANEL_COLLAPSED_KEY) === 'true') {
        setPanelCollapsed(true);
      }
      const raw = localStorage.getItem(GROUPS_COLLAPSED_KEY);
      if (raw) setCollapsedGroups(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(PANEL_COLLAPSED_KEY, String(panelCollapsed));
    } catch {
      /* ignore */
    }
  }, [panelCollapsed]);

  useEffect(() => {
    try {
      localStorage.setItem(GROUPS_COLLAPSED_KEY, JSON.stringify(collapsedGroups));
    } catch {
      /* ignore */
    }
  }, [collapsedGroups]);

  const toggleGroup = (group: string) => {
    setCollapsedGroups((prev) => ({ ...prev, [group]: !prev[group] }));
  };

  if (panelCollapsed) {
    return (
      <div className={`absolute top-4 left-4 z-[999] ${className}`}>
        <button
          type="button"
          onClick={() => setPanelCollapsed(false)}
          title="Expandir camadas espaciais"
          className="flex items-center gap-2 rounded-xl border border-border bg-card/90 px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-indigo-300 shadow-2xl backdrop-blur-md transition hover:border-indigo-500/40"
        >
          <Layers size={14} />
          Camadas
          <span className="rounded-full bg-indigo-500/20 px-1.5 py-0.5 text-[9px] text-indigo-200">
            {activeLayers.length}
          </span>
        </button>
      </div>
    );
  }

  return (
    <div
      className={`absolute top-4 left-4 z-[999] flex w-72 flex-col gap-2 rounded-xl border border-border bg-card/85 p-3 shadow-2xl backdrop-blur-md transition-all duration-300 ${className}`}
    >
      <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5">
        <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-400">
          <Layers size={12} className="text-indigo-400" />
          Camadas Espaciais
        </span>
        <div className="flex items-center gap-2">
          <span className="text-[9px] italic text-zinc-500">{activeLayers.length} ativa(s)</span>
          <button
            type="button"
            onClick={() => setPanelCollapsed(true)}
            title="Recolher painel"
            className="rounded-md p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
          >
            <ChevronDown size={14} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <button
          type="button"
          onClick={() => setActiveLayers([...LAYER_PRESETS.cruzarRiscos.layers])}
          title={LAYER_PRESETS.cruzarRiscos.description}
          className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-2 py-1 text-[10px] font-bold text-indigo-300 hover:bg-indigo-500/20"
        >
          {LAYER_PRESETS.cruzarRiscos.label}
        </button>
        <button
          type="button"
          onClick={() => setActiveLayers([])}
          className="rounded-lg border border-zinc-700 bg-zinc-950/70 px-2 py-1 text-[10px] font-bold text-zinc-400 hover:text-zinc-100"
        >
          Limpar
        </button>
      </div>

      <div className="flex max-h-[58vh] flex-col gap-2 overflow-y-auto pr-1">
        {malhaIndisponivel && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-950/30 px-2.5 py-2 text-[10px] leading-relaxed text-amber-100">
            Malha de bairros indisponível — camadas socioeconômicas e por bairro desativadas.
          </div>
        )}

        {layerGroups.map((group) => {
          const GroupIcon = GROUP_ICONS[group];
          const isGroupCollapsed = collapsedGroups[group];
          const groupLayers = layerOptions.filter((opt) => opt.group === group);
          const activeInGroup = groupLayers.filter((opt) => activeLayers.includes(opt.id)).length;

          return (
            <div key={group} className="rounded-lg border border-zinc-800/80 bg-zinc-950/30">
              <button
                type="button"
                onClick={() => toggleGroup(group)}
                className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-zinc-900/50"
              >
                {isGroupCollapsed ? (
                  <ChevronRight size={12} className="shrink-0 text-zinc-500" />
                ) : (
                  <ChevronDown size={12} className="shrink-0 text-zinc-500" />
                )}
                <GroupIcon size={12} className="shrink-0 text-indigo-400" />
                <span className="flex-1 text-[9px] font-extrabold uppercase tracking-wider text-zinc-400">
                  {group}
                </span>
                {activeInGroup > 0 && (
                  <span className="rounded-full bg-indigo-500/20 px-1.5 text-[8px] font-bold text-indigo-200">
                    {activeInGroup}
                  </span>
                )}
              </button>

              {!isGroupCollapsed && (
                <div className="flex flex-col gap-1 px-1 pb-1.5">
                  {groupLayers.map((opt) => {
                    const isActive = activeLayers.includes(opt.id);
                    const isDisabled = opt.disponivel === false;
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => !isDisabled && toggleLayer(opt.id)}
                        disabled={isDisabled}
                        title={
                          opt.tooltipEstimado
                          || (isDisabled ? 'Camada indisponível — malha territorial ausente' : undefined)
                        }
                        className={`flex w-full items-center justify-between rounded-lg border px-2 py-1.5 text-left text-xs transition-all ${
                          isDisabled
                            ? 'cursor-not-allowed border-zinc-800 bg-zinc-950/40 text-zinc-600 opacity-60'
                            : isActive
                              ? 'border-indigo-500/40 bg-zinc-900 font-bold text-indigo-300'
                              : 'border-transparent text-zinc-400 hover:bg-zinc-900/40 hover:text-zinc-200'
                        }`}
                      >
                        <span className="flex min-w-0 flex-1 flex-col gap-1 pr-2">
                          <span className="truncate">{opt.label}</span>
                          <span className="flex flex-wrap gap-1">
                            <span
                              className={`rounded-md border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide ${
                                isActive
                                  ? 'border-indigo-400/40 bg-indigo-500/15 text-indigo-200'
                                  : 'border-zinc-700 bg-zinc-950/70 text-zinc-500'
                              }`}
                            >
                              {opt.source.split('/')[0].trim()}
                            </span>
                            <span className={`rounded-md border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide ${qualityTone(opt.quality)}`}>
                              {opt.quality === 'Oficial' && opt.id === 'bairros'
                                ? 'IBGE 2022'
                                : opt.quality}
                            </span>
                          </span>
                        </span>
                        <span
                          className={`flex h-4 w-4 items-center justify-center rounded border ${
                            isActive ? 'border-indigo-400 bg-indigo-500/20 text-indigo-200' : 'border-zinc-700'
                          }`}
                        >
                          {isActive && <Eye size={11} />}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
