'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  api,
  type ExecutiveDiagnostic,
  type WorkshopDiagnostic,
} from '@/utils/api';
import { FileText, Loader2, PlayCircle, Sparkles, ChevronDown } from 'lucide-react';
import RotatingLoader, { PDF_DIAGNOSTIC_MESSAGES, PRESENTATION_MESSAGES } from '@/components/UI/RotatingLoader';
import CompareModal from '@/components/Compare/CompareModal';
import { useAppStore } from '@/stores/useAppStore';
import { MAP_CENTER_LEFT, MAP_CENTER_RIGHT } from '@/config/mapOverlayLayout';

type WorkshopCenterProps = {
  selectedMunicipio: string;
  municipioNome?: string;
  municipalities: Array<{ codigo_ibge: string; nome: string; uf?: string }>;
  diagnostic: WorkshopDiagnostic | null;
  setDiagnostic: (d: WorkshopDiagnostic | null) => void;
  setActiveLayers: (layers: string[]) => void;
  setMapFocus: (coords: [number, number]) => void;
  setZoom: (z: number) => void;
  scoreConfiabilidade?: string | null;
  onGenerateCompleto?: () => void;
  onGenerateRapido?: () => void;
};

export default function WorkshopCenter({
  selectedMunicipio,
  municipioNome,
  municipalities,
  diagnostic,
  setDiagnostic,
  setActiveLayers,
  setMapFocus,
  setZoom,
  scoreConfiabilidade,
  onGenerateCompleto,
  onGenerateRapido,
}: WorkshopCenterProps) {
  const router = useRouter();
  const [diagnosticLoading, setDiagnosticLoading] = useState(false);
  const [presentationLoading, setPresentationLoading] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const compareOpen = useAppStore((s) => s.compareModalOpen);
  const setCompareModalOpen = useAppStore((s) => s.setCompareModalOpen);
  const [lastDiagnostic, setLastDiagnostic] = useState<ExecutiveDiagnostic | null>(null);
  const reportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!selectedMunicipio) return;
    api.getExecutiveDiagnostic(selectedMunicipio).then(setLastDiagnostic).catch(() => setLastDiagnostic(null));
  }, [selectedMunicipio, diagnosticLoading]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (reportRef.current && !reportRef.current.contains(e.target as Node)) {
        setReportOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const diagnosticToday =
    lastDiagnostic?.gerado_em &&
    new Date(lastDiagnostic.gerado_em).toDateString() === new Date().toDateString();

  const diagnosticTooltip = lastDiagnostic?.gerado_em
    ? `Diagnóstico atual gerado em ${new Date(lastDiagnostic.gerado_em).toLocaleString('pt-BR')}. Clique para reatualizar.`
    : 'Gerar diagnóstico executivo com narrativa IA';

  const loadDiagnostic = async () => {
    setDiagnosticLoading(true);
    try {
      const [exec, workshop] = await Promise.all([
        api.generateExecutiveDiagnostic(selectedMunicipio),
        api.getWorkshopDiagnostic(selectedMunicipio),
      ]);
      setLastDiagnostic(exec);
      setDiagnostic({ ...workshop, headline: exec.headline || workshop.headline });
      setActiveLayers(workshop.recommended_layers);
      if (workshop.critical_areas[0]) {
        setMapFocus(workshop.critical_areas[0].coordinates);
        setZoom(13);
      }
    } finally {
      setDiagnosticLoading(false);
    }
  };

  const openPresentation = async () => {
    if (!selectedMunicipio) return;
    setPresentationLoading(true);
    try {
      await api.getPresentationData(selectedMunicipio).catch(() => null);
      router.push(`/apresentacao/${selectedMunicipio}`);
    } finally {
      setPresentationLoading(false);
    }
  };

  return (
    <>
      <div
        className="absolute top-4 z-[1000] rounded-xl border border-indigo-500/30 bg-zinc-950/90 p-3 shadow-2xl backdrop-blur-md"
        style={{ left: MAP_CENTER_LEFT, right: MAP_CENTER_RIGHT }}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wider text-indigo-300">
              <Sparkles size={13} /> Central da Oficina Sinidu+Clima
            </p>
            <p className="mt-1 line-clamp-2 text-xs text-zinc-300">
              {diagnostic?.headline || 'Gere um diagnóstico automático, apresente a narrativa guiada e exporte relatório executivo.'}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <button
              onClick={loadDiagnostic}
              disabled={diagnosticLoading}
              title={diagnosticTooltip}
              className="inline-flex items-center gap-1 rounded-lg border border-indigo-500/40 bg-indigo-500/15 px-3 py-2 text-[10px] font-bold uppercase text-indigo-200 hover:bg-indigo-500/25 disabled:opacity-60"
            >
              {diagnosticLoading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : null}
              {diagnosticLoading ? 'Gerando…' : diagnosticToday ? 'Rediagnosticar' : 'Diagnóstico'}
            </button>

            <button
              onClick={openPresentation}
              disabled={presentationLoading}
              className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-3 py-2 text-[10px] font-bold uppercase text-emerald-200 hover:bg-emerald-500/25 disabled:opacity-60"
            >
              {presentationLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <PlayCircle size={12} />}
              Apresentar
            </button>

            <div className="relative" ref={reportRef}>
              <button
                type="button"
                onClick={() => setReportOpen((v) => !v)}
                className="inline-flex items-center gap-1 rounded-lg border border-zinc-600 bg-zinc-900 px-3 py-2 text-[10px] font-bold uppercase text-zinc-200 hover:bg-zinc-800"
              >
                <FileText size={12} /> Relatório <ChevronDown size={10} />
              </button>
              {reportOpen && (
                <div className="absolute right-0 top-full z-10 mt-1 min-w-[220px] rounded-lg border border-zinc-700 bg-zinc-900 py-1 shadow-xl">
                  <button
                    type="button"
                    className="block w-full px-3 py-2 text-left text-[11px] text-zinc-200 hover:bg-zinc-800"
                    onClick={() => {
                      setReportOpen(false);
                      onGenerateRapido?.();
                    }}
                  >
                    Relatório Executivo (rápido)
                  </button>
                  <button
                    type="button"
                    className="block w-full px-3 py-2 text-left text-[11px] text-zinc-200 hover:bg-zinc-800"
                    onClick={() => {
                      setReportOpen(false);
                      onGenerateCompleto?.();
                    }}
                  >
                    Relatório Completo (8 págs)
                  </button>
                </div>
              )}
            </div>

            <button
              onClick={() => setCompareModalOpen(true)}
              className="rounded-lg border border-sky-500/40 bg-sky-500/15 px-3 py-2 text-[10px] font-bold uppercase text-sky-200 hover:bg-sky-500/25"
            >
              Comparar
            </button>
          </div>
        </div>

        {diagnosticLoading && (
          <div className="mt-2 rounded-lg border border-indigo-500/20 bg-indigo-950/30 px-3 py-2">
            <RotatingLoader messages={PDF_DIAGNOSTIC_MESSAGES} className="text-indigo-200" />
          </div>
        )}

        {presentationLoading && (
          <div className="mt-2 rounded-lg border border-emerald-500/20 bg-emerald-950/30 px-3 py-2">
            <RotatingLoader messages={PRESENTATION_MESSAGES} className="text-emerald-200" />
          </div>
        )}

        {diagnostic && (
          <div className="mt-3 grid grid-cols-3 gap-2">
            {diagnostic.critical_areas.map((item, idx) => (
              <button
                key={item.bairro}
                onClick={() => {
                  setMapFocus(item.coordinates);
                  setZoom(14);
                  setActiveLayers(['bairros', 'prioridade_planejamento', 'vulnerabilidade', 'inundacao']);
                }}
                className="rounded-lg border border-zinc-700 bg-zinc-900/80 p-2 text-left hover:border-indigo-400/60"
              >
                <span className="text-[9px] font-bold uppercase text-zinc-500">Prioridade {idx + 1}</span>
                <div className="mt-1 flex items-center justify-between">
                  <strong className="text-xs text-zinc-100">{item.bairro}</strong>
                  <span className="flex items-center gap-1">
                    <span className="rounded-full bg-rose-500/20 px-2 py-0.5 text-[10px] font-extrabold text-rose-200">{item.score_sinidu}</span>
                    {scoreConfiabilidade && (
                      <span className="text-[8px] text-amber-300" title={`Confiança: ${scoreConfiabilidade}`}>
                        {scoreConfiabilidade === 'ALTA' ? '● Alta' : '○ Estimado'}
                      </span>
                    )}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-[10px] leading-snug text-zinc-400">{item.acao_recomendada}</p>
              </button>
            ))}
          </div>
        )}
      </div>

      <CompareModal
        open={compareOpen}
        onClose={() => setCompareModalOpen(false)}
        codigoA={selectedMunicipio}
        nomeA={municipioNome || selectedMunicipio}
        municipalities={municipalities}
      />
    </>
  );
}
