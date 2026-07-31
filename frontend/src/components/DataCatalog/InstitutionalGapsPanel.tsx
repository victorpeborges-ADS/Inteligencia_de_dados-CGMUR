'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Building2, Loader2, MapPin, RefreshCw, Sparkles } from 'lucide-react';
import { INSTITUTIONAL_GAPS, gapStatusFromCatalog } from '@/config/institutionalGaps';
import type { DataCatalogBase, InstitutionalGapsNational } from '@/utils/api';
import { api } from '@/utils/api';
import { Badge } from '@/design-system';

type Props = {
  bases: DataCatalogBase[];
  nacional?: InstitutionalGapsNational | null;
  isGestorOrAdmin?: boolean;
  onAnalyzeGap: (fonteId: string) => void;
  onBatchComplete?: () => void;
};

const STATUS_TONE: Record<string, 'success' | 'warning' | 'info' | 'gap' | 'neutral'> = {
  Integrado: 'success',
  Estimado: 'warning',
  'Em integracao': 'info',
  Ausente: 'gap',
};

function progressTone(pct: number): string {
  if (pct >= 75) return 'bg-emerald-500';
  if (pct >= 25) return 'bg-amber-500';
  return 'bg-rose-500';
}

export default function InstitutionalGapsPanel({
  bases,
  nacional,
  isGestorOrAdmin = false,
  onAnalyzeGap,
  onBatchComplete,
}: Props) {
  const router = useRouter();
  const [batchRunning, setBatchRunning] = useState(false);
  const [ctmRunning, setCtmRunning] = useState(false);
  const [batchMessage, setBatchMessage] = useState<string | null>(null);

  const nacionalByFonte = new Map(nacional?.gaps.map((row) => [row.fonte_id, row]) ?? []);

  const handleExternalSourcesBatch = useCallback(async () => {
    setBatchRunning(true);
    setBatchMessage('Iniciando sync de fontes externas…');
    try {
      const { job_id } = await api.startExternalSourcesBatchJob(61);
      setBatchMessage(`Job ${job_id} em fila — acompanhe no painel Sistema`);
      onBatchComplete?.();
    } catch (e) {
      setBatchMessage(e instanceof Error ? e.message : 'Falha no batch');
    } finally {
      setBatchRunning(false);
    }
  }, [onBatchComplete]);

  const handleCtmBatch = useCallback(async () => {
    setCtmRunning(true);
    setBatchMessage('Importando malhas CTM dos geoportais cadastrados…');
    try {
      const { job_id } = await api.startCtmBatchJob(false);
      setBatchMessage(`Job CTM ${job_id} em fila — acompanhe no painel Sistema`);
      onBatchComplete?.();
    } catch (e) {
      setBatchMessage(e instanceof Error ? e.message : 'Falha no batch CTM');
    } finally {
      setCtmRunning(false);
    }
  }, [onBatchComplete]);

  return (
    <div className="rounded-xl border border-violet-500/25 bg-violet-950/10 p-3">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-violet-300">
            <Building2 size={13} />
            Trâmite institucional — lacunas nacionais
          </h3>
          <p className="mt-1 text-[10px] leading-relaxed text-zinc-500">
            Fontes que exigem convênio ou credencial MCID. Impacto estimado no Score Sinidu+Clima.
          </p>
          {nacional && (
            <p className="mt-1 text-[9px] text-violet-300/80">
              {nacional.resumo} · {nacional.meta_maturidade.label}
            </p>
          )}
        </div>
        {isGestorOrAdmin && (
          <div className="flex flex-wrap gap-1">
            <button
              type="button"
              onClick={handleExternalSourcesBatch}
              disabled={batchRunning || ctmRunning}
              className="inline-flex items-center gap-1 rounded border border-violet-600/40 px-2 py-1 text-[8px] font-bold uppercase text-violet-200 hover:bg-violet-950/40 disabled:opacity-50"
            >
              {batchRunning ? <Loader2 size={10} className="animate-spin" /> : <RefreshCw size={10} />}
              Sync fontes externas
            </button>
            <button
              type="button"
              onClick={handleCtmBatch}
              disabled={batchRunning || ctmRunning}
              className="inline-flex items-center gap-1 rounded border border-indigo-600/40 px-2 py-1 text-[8px] font-bold uppercase text-indigo-200 hover:bg-indigo-950/40 disabled:opacity-50"
            >
              {ctmRunning ? <Loader2 size={10} className="animate-spin" /> : <MapPin size={10} />}
              Importar CTM (24)
            </button>
          </div>
        )}
      </div>

      {batchMessage && (
        <p className="mb-2 text-[9px] text-zinc-500">{batchMessage}</p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-[10px]">
          <thead>
            <tr className="border-b border-violet-900/30 text-zinc-500">
              <th className="py-1 pr-2">#</th>
              <th className="py-1 pr-2">Fonte</th>
              <th className="py-1 pr-2">Nacional</th>
              <th className="py-1 pr-2">Município</th>
              <th className="py-1 pr-2">Impacto</th>
              <th className="py-1 pr-2">Responsável</th>
              <th className="py-1 pr-2">Prazo</th>
              <th className="py-1">Ação</th>
            </tr>
          </thead>
          <tbody>
            {INSTITUTIONAL_GAPS.map((gap) => {
              const localStatus = gapStatusFromCatalog(gap.fonteId, bases);
              const row = nacionalByFonte.get(gap.fonteId);
              const pct = row?.integrado_pct ?? 0;
              const canAnalyze = gap.fonteId !== 'ctm_utb' && bases.some((b) => b.id === gap.fonteId);

              return (
                <tr key={gap.fonteId} className="border-b border-zinc-900/50 text-zinc-300">
                  <td className="py-2 pr-2 font-mono text-zinc-500">{gap.rank}</td>
                  <td className="py-2 pr-2">
                    <p className="font-semibold text-zinc-100">{gap.nome}</p>
                    <p className="mt-0.5 line-clamp-2 text-[9px] text-zinc-500">{gap.acao}</p>
                    {row?.proxy_ativo && (
                      <p className="mt-0.5 text-[8px] text-amber-400">Proxy ETL ativo (Estimado)</p>
                    )}
                    {row?.etl_ready && gap.fonteId !== 'ctm_utb' && (
                      <p className="mt-0.5 text-[8px] text-teal-400">ETL pronto — aguarda convênio/dado</p>
                    )}
                    {gap.fonteId === 'ctm_utb' && row && (
                      <p className="mt-0.5 text-[8px] text-zinc-500">
                        {row.ctm_cadastrada_count ?? 0}/{row.total_municipios ?? 24} CTM cadastradas
                        {typeof row.ctm_sem_fonte_count === 'number' ? ` · ${row.ctm_sem_fonte_count} sem REST` : ''}
                        {' · '}
                        {row.malha_operacional_count ?? 0} com malha operacional
                        {row.escopo_label ? ` · ${row.escopo_label}` : ''}
                      </p>
                    )}
                  </td>
                  <td className="py-2 pr-2">
                    {row ? (
                      <div className="min-w-[88px]">
                        <p className="font-mono text-[9px] text-zinc-300">{row.progress_label}</p>
                        <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-zinc-800">
                          <div
                            className={`h-full rounded-full ${progressTone(pct)}`}
                            style={{ width: `${Math.max(pct, 2)}%` }}
                          />
                        </div>
                        <p className="mt-0.5 text-[8px] text-zinc-600">
                          {row.lacuna_municipios} lacunas
                        </p>
                      </div>
                    ) : (
                      <span className="text-zinc-600">—</span>
                    )}
                  </td>
                  <td className="py-2 pr-2">
                    {localStatus ? (
                      <Badge tone={STATUS_TONE[localStatus] || 'neutral'}>{localStatus}</Badge>
                    ) : gap.fonteId === 'ctm_utb' ? (
                      <span className="text-[9px] text-zinc-500">Geoportal</span>
                    ) : (
                      <span className="text-zinc-600">—</span>
                    )}
                  </td>
                  <td className="py-2 pr-2 text-amber-300">{gap.impactoScore}</td>
                  <td className="py-2 pr-2 text-zinc-400">{gap.responsavel}</td>
                  <td className="py-2 pr-2 text-zinc-400">{gap.prazo}</td>
                  <td className="py-2">
                    {canAnalyze ? (
                      <button
                        type="button"
                        onClick={() => onAnalyzeGap(gap.fonteId)}
                        className="inline-flex items-center gap-0.5 rounded border border-violet-600/40 px-1.5 py-0.5 text-[8px] font-bold uppercase text-violet-200 hover:bg-violet-950/40"
                      >
                        <Sparkles size={10} />
                        Impacto IA
                      </button>
                    ) : gap.fonteId === 'ctm_utb' ? (
                      <button
                        type="button"
                        onClick={() => router.push('/municipios')}
                        className="inline-flex items-center gap-0.5 rounded border border-indigo-600/40 px-1.5 py-0.5 text-[8px] font-bold uppercase text-indigo-200 hover:bg-indigo-950/40"
                      >
                        <MapPin size={10} />
                        Geoportal
                      </button>
                    ) : (
                      <span className="text-[8px] text-zinc-600">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-[9px] text-zinc-600">
        Referência: PLANO_LACUNAS_INSTITUCIONAIS.md · Meta maturidade nacional 77% → 84% (GeoSGB + Brasil MAIS)
      </p>
    </div>
  );
}
