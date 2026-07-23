'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Info } from 'lucide-react';
import type { LayerOption, LayerQuality } from '@/config/platformTabs';

type LayerMetaBlockProps = {
  layer: LayerOption;
  compact?: boolean;
  /** Quando true, inicia recolhido (só badge + chevron). */
  defaultCollapsed?: boolean;
};

function qualityTone(quality: LayerQuality) {
  if (quality === 'Oficial') return 'border-emerald-400/40 bg-emerald-500/10 text-emerald-300';
  if (quality === 'Observado') return 'border-sky-400/40 bg-sky-500/10 text-sky-300';
  if (quality === 'Referencia') return 'border-cyan-400/40 bg-cyan-500/10 text-cyan-300';
  if (quality === 'Estimado') return 'border-amber-400/40 bg-amber-500/10 text-amber-300';
  if (quality === 'Indisponível') return 'border-rose-400/40 bg-rose-500/10 text-rose-300';
  return 'border-indigo-400/40 bg-indigo-500/10 text-indigo-300';
}

export default function LayerMetaBlock({
  layer,
  compact = false,
  defaultCollapsed = false,
}: LayerMetaBlockProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  if (!layer.descricao && !layer.source && !layer.tooltipEstimado) return null;

  return (
    <div
      className={`rounded-lg border border-zinc-800/80 bg-zinc-900/40 ${
        compact ? 'mt-1.5' : 'mt-2'
      }`}
    >
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        title={collapsed ? 'Expandir detalhes' : 'Recolher detalhes'}
        className={`flex w-full items-center gap-1.5 text-left hover:bg-zinc-800/40 ${
          compact ? 'px-2 py-1.5' : 'px-2.5 py-2'
        }`}
      >
        {collapsed ? (
          <ChevronRight size={12} className="shrink-0 text-zinc-500" />
        ) : (
          <ChevronDown size={12} className="shrink-0 text-zinc-500" />
        )}
        <span className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
          <span className={`rounded-md border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide ${qualityTone(layer.quality)}`}>
            {layer.quality}
          </span>
          {layer.count != null && (
            <span className="text-[8px] text-zinc-500">{layer.count.toLocaleString('pt-BR')} feições</span>
          )}
          {collapsed && layer.source && (
            <span className="truncate text-[8px] text-zinc-500">{layer.source}</span>
          )}
        </span>
      </button>

      {!collapsed && (
        <div className={compact ? 'px-2 pb-2' : 'px-2.5 pb-2.5'}>
          {layer.source && (
            <p className={`leading-snug text-zinc-400 ${compact ? 'text-[9px]' : 'text-[10px]'}`}>
              <span className="font-semibold text-zinc-500">Fonte: </span>
              {layer.source}
            </p>
          )}

          {layer.descricao && (
            <p className={`mt-1 leading-relaxed text-zinc-400 ${compact ? 'text-[9px]' : 'text-[10px]'}`}>
              {layer.descricao}
            </p>
          )}

          {layer.tooltipEstimado && (
            <p className={`mt-1.5 flex items-start gap-1 leading-snug text-amber-200/90 ${compact ? 'text-[8px]' : 'text-[9px]'}`}>
              <Info size={10} className="mt-0.5 shrink-0" />
              <span>{layer.tooltipEstimado}</span>
            </p>
          )}

          {layer.fontesCatalogo && layer.fontesCatalogo.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {layer.fontesCatalogo.map((fonte) => (
                <span
                  key={fonte.id}
                  title={fonte.descricao_curta || fonte.nome}
                  className="rounded border border-zinc-700/80 bg-zinc-950/60 px-1.5 py-0.5 text-[8px] text-zinc-500"
                >
                  {fonte.nome}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
