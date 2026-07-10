'use client';

import { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, EyeOff, Layers } from 'lucide-react';
import type { LayerOption } from '@/config/platformTabs';
import { layerChipColor } from '@/config/layerChipColors';
import { canReorderLayer, displayStackOrder } from '@/utils/activeLayerOrder';

type Props = {
  activeLayers: string[];
  layerOptions: LayerOption[];
  layerOpacityById: Record<string, number>;
  setLayerOpacity: (layerId: string, opacity: number) => void;
  moveActiveLayer: (layerId: string, direction: 'up' | 'down') => void;
  toggleLayer: (layerId: string) => void;
  showRegionalOverlay?: boolean;
  className?: string;
};

export default function ActiveLayersPanel({
  activeLayers,
  layerOptions,
  layerOpacityById,
  setLayerOpacity,
  moveActiveLayer,
  toggleLayer,
  showRegionalOverlay = false,
  className = '',
}: Props) {
  const [collapsed, setCollapsed] = useState(false);

  const labelById = useMemo(
    () => Object.fromEntries(layerOptions.map((opt) => [opt.id, opt.label])),
    [layerOptions],
  );

  const stackItems = useMemo(() => {
    const items = displayStackOrder(activeLayers).map((id) => ({
      id,
      label: labelById[id] || id,
      opacity: layerOpacityById[id] ?? 1,
      reorderable: canReorderLayer(id),
    }));
    if (showRegionalOverlay) {
      items.unshift({
        id: '__regional_overlay__',
        label: 'Contexto regional',
        opacity: 0.85,
        reorderable: false,
      });
    }
    return items;
  }, [activeLayers, labelById, layerOpacityById, showRegionalOverlay]);

  const count = activeLayers.length + (showRegionalOverlay ? 1 : 0);

  if (count === 0) return null;

  if (collapsed) {
    return (
      <div className={className}>
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          className="flex w-full items-center justify-between rounded-xl border border-indigo-500/30 bg-zinc-950/95 px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-indigo-200 shadow-lg backdrop-blur-md hover:border-indigo-400/50"
        >
          <span className="flex items-center gap-1.5">
            <Layers size={12} />
            Camadas ativas ({count})
          </span>
          <ChevronDown size={14} className="text-zinc-500" />
        </button>
      </div>
    );
  }

  return (
    <div
      className={`flex max-h-44 flex-col overflow-hidden rounded-xl border border-indigo-500/25 bg-zinc-950/95 shadow-lg backdrop-blur-md ${className}`}
    >
      <div className="flex shrink-0 items-center justify-between border-b border-zinc-800 px-3 py-2">
        <span className="flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wider text-indigo-200">
          <Layers size={12} />
          Camadas ativas ({count})
        </span>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          title="Recolher"
          className="rounded p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
        >
          <ChevronUp size={14} />
        </button>
      </div>

      <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto px-2 py-2">
        {stackItems.map((item) => (
          <li
            key={item.id}
            className="rounded-lg border border-zinc-800/80 bg-zinc-900/50 px-2 py-1.5"
          >
            <div className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-sm border border-white/20"
                style={{ backgroundColor: layerChipColor(item.id) }}
              />
              <span className="min-w-0 flex-1 truncate text-[10px] font-semibold text-zinc-100">
                {item.label}
              </span>
              {item.id !== '__regional_overlay__' && (
                <div className="flex shrink-0 items-center gap-0.5">
                  {item.reorderable && (
                    <>
                      <button
                        type="button"
                        title="Subir (frente)"
                        onClick={() => moveActiveLayer(item.id, 'up')}
                        className="rounded p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-indigo-200"
                      >
                        <ChevronUp size={12} />
                      </button>
                      <button
                        type="button"
                        title="Descer (fundo)"
                        onClick={() => moveActiveLayer(item.id, 'down')}
                        className="rounded p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-indigo-200"
                      >
                        <ChevronDown size={12} />
                      </button>
                    </>
                  )}
                  <button
                    type="button"
                    title="Ocultar camada"
                    onClick={() => toggleLayer(item.id)}
                    className="rounded p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-rose-300"
                  >
                    <EyeOff size={12} />
                  </button>
                </div>
              )}
            </div>
            {item.id !== '__regional_overlay__' && (
              <label className="mt-1.5 flex items-center gap-2 text-[9px] text-zinc-500">
                <span className="w-12 shrink-0">Opacidade</span>
                <input
                  type="range"
                  min={0.15}
                  max={1}
                  step={0.05}
                  value={item.opacity}
                  onChange={(e) => setLayerOpacity(item.id, Number(e.target.value))}
                  className="h-1 flex-1 accent-indigo-500"
                />
                <span className="w-8 shrink-0 text-right tabular-nums text-zinc-400">
                  {Math.round(item.opacity * 100)}%
                </span>
              </label>
            )}
          </li>
        ))}
      </ul>
      <p className="shrink-0 border-t border-zinc-800/80 px-3 py-1.5 text-[8px] leading-snug text-zinc-600">
        Ordem: topo da lista = camada à frente no mapa.
      </p>
    </div>
  );
}
