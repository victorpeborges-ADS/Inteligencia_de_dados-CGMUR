'use client';

import { Info } from 'lucide-react';
import type { LayerOption, LayerQuality } from '@/config/platformTabs';

type LayerMetaBlockProps = {
  layer: LayerOption;
  compact?: boolean;
};

function qualityTone(quality: LayerQuality) {
  if (quality === 'Oficial') return 'border-emerald-400/40 bg-emerald-500/10 text-emerald-300';
  if (quality === 'Observado') return 'border-sky-400/40 bg-sky-500/10 text-sky-300';
  if (quality === 'Referencia') return 'border-cyan-400/40 bg-cyan-500/10 text-cyan-300';
  if (quality === 'Estimado') return 'border-amber-400/40 bg-amber-500/10 text-amber-300';
  if (quality === 'Indisponível') return 'border-rose-400/40 bg-rose-500/10 text-rose-300';
  return 'border-indigo-400/40 bg-indigo-500/10 text-indigo-300';
}

export default function LayerMetaBlock({ layer, compact = false }: LayerMetaBlockProps) {
  if (!layer.descricao && !layer.source && !layer.tooltipEstimado) return null;

  return (
    <div
      className={`rounded-lg border border-zinc-800/80 bg-zinc-900/40 ${
        compact ? 'mt-1.5 p-2' : 'mt-2 p-2.5'
      }`}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`rounded-md border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide ${qualityTone(layer.quality)}`}>
          {layer.quality}
        </span>
        {layer.count != null && (
          <span className="text-[8px] text-zinc-500">{layer.count.toLocaleString('pt-BR')} feições</span>
        )}
      </div>

      {layer.source && (
        <p className={`mt-1.5 leading-snug text-zinc-400 ${compact ? 'text-[9px]' : 'text-[10px]'}`}>
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
  );
}
