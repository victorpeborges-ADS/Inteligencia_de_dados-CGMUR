'use client';

import { Box, Crosshair, FileDown, Layers, Sparkles, CheckCircle2 } from 'lucide-react';

type SimulationNextStepsProps = {
  scenarioLabel: string;
  isVolumeSim: boolean;
  auto3dApplied: boolean;
  fromCache?: boolean;
  onView3D: () => void;
  onFocusWorkshop: () => void;
  onCrossRiskLayers: () => void;
  onExportPdf: () => void;
  exportPdfLoading?: boolean;
};

export default function SimulationNextSteps({
  scenarioLabel,
  isVolumeSim,
  auto3dApplied,
  fromCache,
  onView3D,
  onFocusWorkshop,
  onCrossRiskLayers,
  onExportPdf,
  exportPdfLoading = false,
}: SimulationNextStepsProps) {
  return (
    <div className="rounded-xl border border-teal-500/35 bg-teal-950/15 p-4">
      <div className="mb-3 flex items-start gap-2">
        <Sparkles size={16} className="mt-0.5 shrink-0 text-teal-300" />
        <div>
          <p className="text-xs font-extrabold uppercase tracking-wide text-teal-200">
            Próximos passos na oficina
          </p>
          <p className="mt-1 text-[10px] leading-relaxed text-zinc-400">
            Cenário <strong className="text-zinc-200">{scenarioLabel}</strong> calculado
            {fromCache ? ' (cache)' : ''}. Use o fluxo abaixo para apresentar gestores.
          </p>
        </div>
      </div>

      <ol className="space-y-2">
        {isVolumeSim && (
          <li className="flex items-center gap-2 rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-3 py-2 text-[10px] text-zinc-300">
            {auto3dApplied ? (
              <CheckCircle2 size={14} className="shrink-0 text-emerald-400" />
            ) : (
              <Box size={14} className="shrink-0 text-teal-300" />
            )}
            <span className="flex-1">
              {auto3dApplied
                ? 'Terreno 3D ativado automaticamente — clique na mancha para inspecionar profundidade.'
                : 'Visualize o volume de água ou calor no terreno 3D.'}
            </span>
            {!auto3dApplied && (
              <button
                type="button"
                onClick={onView3D}
                className="shrink-0 rounded-md border border-teal-500/40 bg-teal-500/15 px-2 py-1 font-bold uppercase text-teal-200 hover:bg-teal-500/25"
              >
                Abrir 3D
              </button>
            )}
          </li>
        )}

        <li className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-3 py-2">
          <Crosshair size={14} className="shrink-0 text-indigo-300" />
          <span className="flex-1 text-[10px] text-zinc-300">
            Modo Focus (tecla <kbd className="rounded border border-zinc-700 px-1 font-mono text-[9px]">F</kbd>) — mapa em tela cheia para sala de situação.
          </span>
          <button
            type="button"
            onClick={onFocusWorkshop}
            className="rounded-md border border-indigo-500/40 bg-indigo-500/15 px-2 py-1 text-[10px] font-bold uppercase text-indigo-200 hover:bg-indigo-500/25"
          >
            Modo Focus
          </button>
        </li>

        <li className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-3 py-2">
          <Layers size={14} className="shrink-0 text-indigo-300" />
          <span className="flex-1 text-[10px] text-zinc-300">
            Sobrepor malha de bairros com vulnerabilidade e inundação (preset Cruzar riscos).
          </span>
          <button
            type="button"
            onClick={onCrossRiskLayers}
            className="rounded-md border border-indigo-500/40 bg-indigo-500/15 px-2 py-1 text-[10px] font-bold uppercase text-indigo-200 hover:bg-indigo-500/25"
          >
            Cruzar riscos
          </button>
        </li>

        <li className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-3 py-2">
          <FileDown size={14} className="shrink-0 text-sky-300" />
          <span className="flex-1 text-[10px] text-zinc-300">
            Exporte PDF da simulação para ata de reunião ou compartilhamento externo.
          </span>
          <button
            type="button"
            onClick={onExportPdf}
            disabled={exportPdfLoading}
            className="rounded-md border border-sky-500/40 bg-sky-500/15 px-2 py-1 text-[10px] font-bold uppercase text-sky-200 hover:bg-sky-500/25 disabled:opacity-50"
          >
            {exportPdfLoading ? 'Gerando…' : 'PDF oficina'}
          </button>
        </li>
      </ol>
    </div>
  );
}
