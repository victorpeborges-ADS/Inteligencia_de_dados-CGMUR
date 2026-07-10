'use client';

import type { TemporalTemaId, TemporalTemaOption } from '@/config/layerTemporal';

type TemporalYearPanelProps = {
  activeTemas: TemporalTemaOption[];
  layerAnoByTema: Partial<Record<TemporalTemaId, number>>;
  setLayerAnoForTema: (temaId: TemporalTemaId, ano: number) => void;
};

export default function TemporalYearPanel({
  activeTemas,
  layerAnoByTema,
  setLayerAnoForTema,
}: TemporalYearPanelProps) {
  if (activeTemas.length === 0) return null;

  return (
    <div className="rounded-lg border border-violet-500/25 bg-violet-950/15 p-2">
      <p className="mb-1.5 text-[9px] font-bold uppercase tracking-wider text-violet-200">
        Ano de referência
      </p>
      <div className="flex flex-col gap-2">
        {activeTemas.map((tema) => {
          const selected = layerAnoByTema[tema.tema_id] ?? tema.padrao ?? null;
          return (
            <label
              key={tema.tema_id}
              className="flex flex-col gap-0.5 text-[9px] text-zinc-400"
            >
              <span className="font-semibold text-zinc-300">
                {tema.label}
                {tema.context_only ? (
                  <span className="ml-1 font-normal text-zinc-500">(contexto)</span>
                ) : null}
              </span>
              <select
                value={selected == null ? '' : String(selected)}
                onChange={(e) => {
                  const val = e.target.value;
                  setLayerAnoForTema(tema.tema_id, val ? Number(val) : null);
                }}
                className="rounded-md border border-zinc-700 bg-zinc-950/80 px-2 py-1 text-[10px] text-zinc-200 focus:border-violet-500/40 focus:outline-none"
              >
                {tema.tema_id === 's2id' && (
                  <option value="">Todos os anos</option>
                )}
                {tema.anos.map((ano) => (
                  <option key={`${tema.tema_id}-${ano}`} value={ano}>
                    {ano}
                  </option>
                ))}
              </select>
              {tema.nota && (
                <span className="text-[8px] leading-snug text-zinc-500">{tema.nota}</span>
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
}
