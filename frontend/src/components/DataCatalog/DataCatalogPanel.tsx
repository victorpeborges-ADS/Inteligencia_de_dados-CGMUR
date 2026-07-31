'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  api,
  type DataCatalogBase,
  type DataCoverage,
  type DataCatalogNational,
  type FonteImpactAnalysis,
  type InstitutionalGapsNational,
} from '@/utils/api';
import InstitutionalGapsPanel from '@/components/DataCatalog/InstitutionalGapsPanel';
import GeoReDusReferenceCard from '@/components/DataCatalog/GeoReDusReferenceCard';
import SingedLabPanel from '@/components/DataCatalog/SingedLabPanel';
import {
  Database,
  Eye,
  HelpCircle,
  Loader2,
  RefreshCw,
  Sparkles,
  X,
} from 'lucide-react';
import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from 'recharts';

const STATUS_STYLE: Record<string, string> = {
  Integrado: 'bg-emerald-500/15 text-emerald-300 border-emerald-700/40',
  Estimado: 'bg-amber-500/15 text-amber-300 border-amber-700/40',
  'Em integracao': 'bg-sky-500/15 text-sky-300 border-sky-700/40',
  Ausente: 'bg-rose-500/15 text-rose-300 border-rose-700/40',
  'Nao aplicavel': 'bg-zinc-700/30 text-zinc-400 border-zinc-600/40',
};

function StatusPill({ status }: { status: string }) {
  const label = status === 'Nao aplicavel' ? 'N/A' : status;
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[8px] font-bold uppercase ${STATUS_STYLE[status] || 'bg-zinc-800 text-zinc-400'}`}>
      {label}
    </span>
  );
}

function formatSync(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
  } catch {
    return iso;
  }
}

type ModalState =
  | { type: 'preview'; base: DataCatalogBase; rows: Record<string, unknown>[] }
  | { type: 'impact'; base: DataCatalogBase; analysis: FonteImpactAnalysis }
  | { type: 'improve'; base: DataCatalogBase; analysis: FonteImpactAnalysis }
  | null;

type DataCatalogPanelProps = {
  codigoIbge: string;
  isGestorOrAdmin: boolean;
};

export default function DataCatalogPanel({ codigoIbge, isGestorOrAdmin }: DataCatalogPanelProps) {
  const [coverage, setCoverage] = useState<DataCoverage | null>(null);
  const [national, setNational] = useState<DataCatalogNational | null>(null);
  const [institutionalGaps, setInstitutionalGaps] = useState<InstitutionalGapsNational | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalState>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [sourceLoading, setSourceLoading] = useState<string | null>(null);
  const [refreshJobId, setRefreshJobId] = useState<string | null>(null);
  const [refreshProgress, setRefreshProgress] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const municipal = await api.getDataCoverage(codigoIbge);
      setCoverage(municipal);
      if (isGestorOrAdmin) {
        try {
          const [nat, gaps] = await Promise.all([
            api.getNationalDataCatalog(),
            api.getInstitutionalGapsNational(),
          ]);
          setNational(nat);
          setInstitutionalGaps(gaps);
        } catch {
          setNational(null);
          setInstitutionalGaps(null);
        }
      } else {
        setNational(null);
        setInstitutionalGaps(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao carregar catálogo');
      setCoverage(null);
    } finally {
      setLoading(false);
    }
  }, [codigoIbge, isGestorOrAdmin]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const pollRefreshJob = (jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const job = await api.getCatalogRefreshJob(jobId);
        const sources = job.result?.sources || [];
        const done = job.result?.done ?? sources.filter((s) => s.status !== 'running').length;
        const total = job.result?.total ?? sources.length;
        const parts = sources
          .filter((s) => s.status !== 'running')
          .map((s) => `${s.nome.split('/')[0]}: ${s.status === 'ok' ? 'OK' : 'erro'}`)
          .join(' · ');
        setRefreshProgress(`${done}/${total} fontes · ${parts || 'processando…'}`);

        if (job.status === 'completed' || job.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setRefreshJobId(null);
          await load();
          setTimeout(() => setRefreshProgress(null), 8000);
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
      }
    }, 2000);
  };

  const handleRefreshAll = async () => {
    setRefreshProgress('Iniciando…');
    try {
      const { job_id } = await api.refreshAllCatalogSources(codigoIbge);
      setRefreshJobId(job_id);
      pollRefreshJob(job_id);
    } catch (e) {
      setRefreshProgress(e instanceof Error ? e.message : 'Falha no job');
    }
  };

  const handleRefreshSource = async (base: DataCatalogBase) => {
    setSourceLoading(base.id);
    try {
      await api.refreshCatalogSource(codigoIbge, base.id, true);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao atualizar');
    } finally {
      setSourceLoading(null);
    }
  };

  const openPreview = async (base: DataCatalogBase) => {
    setModalLoading(true);
    try {
      const data = await api.getFontePreview(codigoIbge, base.id);
      setModal({ type: 'preview', base, rows: data.registros });
    } finally {
      setModalLoading(false);
    }
  };

  const openImpact = async (base: DataCatalogBase, improve = false) => {
    setModalLoading(true);
    try {
      const analysis = await api.getFonteImpactAnalysis(codigoIbge, base.id);
      setModal({ type: improve ? 'improve' : 'impact', base, analysis });
    } finally {
      setModalLoading(false);
    }
  };

  const openImpactByFonteId = (fonteId: string) => {
    const base = coverage?.bases.find((b) => b.id === fonteId);
    if (base) openImpact(base);
  };

  if (loading && !coverage) {
    return (
      <div className="flex h-full items-center justify-center text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Carregando catálogo de dados…
      </div>
    );
  }

  if (error && !coverage) {
    return (
      <div className="rounded-xl border border-rose-800/50 bg-rose-950/30 p-4 text-sm text-rose-200">
        {error}
      </div>
    );
  }

  if (!coverage) return null;

  const maturity = coverage.maturity_detail;
  const ranking = coverage.lacunas_ranking || maturity?.lacunas_ranking || [];

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pr-1">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-indigo-300">
            <Database className="h-4 w-4" />
            Catálogo de Dados
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            Maturidade informacional e lacunas — {coverage.municipio.nome}/{coverage.municipio.uf}.
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <button
            type="button"
            onClick={handleRefreshAll}
            disabled={!!refreshJobId || loading}
            className="inline-flex items-center gap-1 rounded-lg border border-teal-600/40 bg-teal-950/30 px-2 py-1 text-xs text-teal-200 hover:bg-teal-900/40 disabled:opacity-50"
          >
            {refreshJobId ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Atualizar Tudo
          </button>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 px-2 py-1 text-[10px] text-zinc-400 hover:bg-zinc-800"
          >
            Recarregar painel
          </button>
        </div>
      </div>

      {refreshProgress && (
        <div className="rounded-lg border border-teal-700/40 bg-teal-950/20 px-3 py-2 text-[10px] text-teal-200">
          {refreshProgress}
        </div>
      )}

      {/* Maturity widget */}
      {maturity && (
        <div className="rounded-xl border border-indigo-500/25 bg-indigo-950/15 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase text-indigo-300">Maturidade informacional</span>
            <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-bold text-indigo-200">
              {coverage.classificacao} · {coverage.maturidade_percentual}%
            </span>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[180px_1fr]">
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={maturity.radar}>
                  <PolarGrid stroke="#334155" />
                  <PolarAngleAxis dataKey="eixo" tick={{ fill: '#94a3b8', fontSize: 9 }} />
                  <Radar dataKey="valor" stroke="#818cf8" fill="#6366f1" fillOpacity={0.35} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-2 text-[10px] text-zinc-400">
              <p>{maturity.timeline.label}</p>
              <p className="text-teal-300/90">{maturity.projecao.label}</p>
              <p className="flex gap-1 leading-relaxed text-zinc-300">
                <Sparkles className="mt-0.5 h-3 w-3 shrink-0 text-teal-400" />
                {maturity.explicacao_ia}
              </p>
            </div>
          </div>
        </div>
      )}

      <GeoReDusReferenceCard codigoIbge={codigoIbge} municipioNome={coverage.municipio.nome} />

      <SingedLabPanel
        codigoIbge={codigoIbge}
        municipioNome={coverage.municipio.nome}
        uf={coverage.municipio.uf}
        isGestorOrAdmin={isGestorOrAdmin}
        singedlabBase={coverage.bases.find((b) => b.id === 'ibge_singedlab_rs')}
        onImported={load}
      />

      <InstitutionalGapsPanel
        bases={coverage.bases}
        nacional={institutionalGaps}
        isGestorOrAdmin={isGestorOrAdmin}
        onAnalyzeGap={openImpactByFonteId}
        onBatchComplete={load}
      />

      {/* Source cards */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
        <p className="mb-3 text-xs text-zinc-400">{coverage.resumo}</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {coverage.bases.map((base) => (
            <div key={base.id} className="rounded-lg border border-zinc-800 bg-zinc-950/80 p-2.5">
              <div className="flex items-center justify-between gap-2">
                <strong className="truncate text-[10px] text-zinc-200">{base.nome}</strong>
                <StatusPill status={base.status} />
              </div>

              {base.status === 'Integrado' && (
                <p className="mt-1 text-[9px] text-zinc-500">
                  Última sync: {formatSync(base.ultima_sync)} · {base.registros ?? 0} registros
                </p>
              )}
              {base.status === 'Estimado' && base.impacto_confiabilidade_label && (
                <p className="mt-1 text-[9px] text-amber-400/90">Impacto no Score: {base.impacto_confiabilidade_label}</p>
              )}
              {base.status === 'Em integracao' && (
                <p className="mt-1 text-[9px] text-sky-400/80">Previsto: quando disponível via convênio institucional</p>
              )}
              {base.status === 'Ausente' && base.requisito && (
                <p className="mt-1 text-[9px] text-rose-400/80">O que falta: {base.requisito}</p>
              )}
              {base.id === 'gemeo_digital_3d' && base.modelo_3d && (
                <p className="mt-1 text-[9px] text-zinc-500">
                  {base.modelo_3d.lod || 'LOD1'} · maturidade {base.modelo_3d.maturidade_3d_pct ?? 0}%
                  {base.modelo_3d.fonte_altura_predominante
                    ? ` · altura: ${base.modelo_3d.fonte_altura_predominante}`
                    : ''}
                  {base.modelo_3d.tileset_url || base.modelo_3d.cityjson_url ? ' · export pronto' : ''}
                </p>
              )}

              <div className="mt-2 flex flex-wrap gap-1">
                {base.status === 'Integrado' && (
                  <>
                    <button
                      type="button"
                      disabled={sourceLoading === base.id}
                      onClick={() => handleRefreshSource(base)}
                      className="rounded border border-emerald-700/40 px-1.5 py-0.5 text-[8px] font-bold uppercase text-emerald-300 hover:bg-emerald-950/40"
                    >
                      ↻ Atualizar agora
                    </button>
                    <button
                      type="button"
                      onClick={() => openPreview(base)}
                      className="inline-flex items-center gap-0.5 rounded border border-zinc-700 px-1.5 py-0.5 text-[8px] text-zinc-300 hover:bg-zinc-900"
                    >
                      <Eye className="h-2.5 w-2.5" /> Ver dados
                    </button>
                  </>
                )}
                {base.status === 'Estimado' && (
                  <button
                    type="button"
                    onClick={() => openImpact(base, true)}
                    className="inline-flex items-center gap-0.5 rounded border border-amber-700/40 px-1.5 py-0.5 text-[8px] text-amber-200 hover:bg-amber-950/30"
                  >
                    <HelpCircle className="h-2.5 w-2.5" /> Como melhorar?
                  </button>
                )}
                {base.status === 'Em integracao' && (
                  <button
                    type="button"
                    onClick={() => openImpact(base)}
                    className="rounded border border-sky-700/40 px-1.5 py-0.5 text-[8px] text-sky-200 hover:bg-sky-950/30"
                  >
                    Ver progresso
                  </button>
                )}
                {base.status === 'Ausente' && (
                  <button
                    type="button"
                    onClick={() => openImpact(base)}
                    className="inline-flex items-center gap-0.5 rounded border border-rose-700/40 px-1.5 py-0.5 text-[8px] text-rose-200 hover:bg-rose-950/30"
                  >
                    <Sparkles className="h-2.5 w-2.5" /> Entender impacto
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Gap ranking */}
      {ranking.length > 0 && (
        <div className="rounded-xl border border-amber-900/40 bg-amber-950/20 p-3">
          <div className="mb-2 text-[10px] font-bold uppercase text-amber-600/80">
            Lacunas prioritárias — por impacto no Score
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[320px] text-left text-[10px]">
              <thead>
                <tr className="border-b border-amber-900/30 text-zinc-500">
                  <th className="py-1 pr-2">#</th>
                  <th className="py-1 pr-2">Fonte</th>
                  <th className="py-1 pr-2">Impacto est.</th>
                  <th className="py-1">Dificuldade</th>
                </tr>
              </thead>
              <tbody>
                {ranking.slice(0, 8).map((row) => (
                  <tr key={row.id} className="border-b border-zinc-900/60 text-zinc-300">
                    <td className="py-1.5 pr-2 font-mono">{row.rank}</td>
                    <td className="py-1.5 pr-2">{row.nome}</td>
                    <td className="py-1.5 pr-2 text-amber-300">{row.impacto_label}</td>
                    <td className="py-1.5">{row.dificuldade}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {national && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 text-[10px] font-bold uppercase text-zinc-500">
            Panorama nacional ({national.total_municipios} prioritários)
          </div>
          <p className="text-xs text-zinc-500">{national.resumo}</p>
        </div>
      )}

      {/* Modal */}
      {(modal || modalLoading) && (
        <div className="fixed inset-0 z-[9998] flex items-center justify-center bg-black/70 p-4">
          <div className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-xl border border-zinc-700 bg-zinc-950 p-4 shadow-2xl">
            <div className="mb-3 flex items-start justify-between gap-2">
              <h3 className="text-sm font-bold text-zinc-100">
                {modal?.base.nome || 'Carregando…'}
              </h3>
              <button type="button" onClick={() => setModal(null)} className="text-zinc-500 hover:text-zinc-300">
                <X className="h-4 w-4" />
              </button>
            </div>
            {modalLoading && (
              <div className="flex items-center gap-2 text-sm text-zinc-400">
                <Loader2 className="h-4 w-4 animate-spin" /> Analisando…
              </div>
            )}
            {modal?.type === 'preview' && (
              <div className="space-y-2">
                <p className="text-[10px] text-zinc-500">Últimos registros</p>
                {modal.rows.length === 0 ? (
                  <p className="text-xs text-zinc-500">Nenhum registro disponível.</p>
                ) : (
                  modal.rows.map((row, i) => (
                    <pre key={i} className="overflow-x-auto rounded bg-zinc-900 p-2 text-[9px] text-zinc-300">
                      {JSON.stringify(row, null, 2)}
                    </pre>
                  ))
                )}
              </div>
            )}
            {(modal?.type === 'impact' || modal?.type === 'improve') && modal.analysis && (
              <div className="space-y-3 text-xs text-zinc-300">
                <p>
                  <span className="text-zinc-500">Status:</span> {modal.analysis.status_atual} ·{' '}
                  <span className="text-zinc-500">Impacto:</span> ±{modal.analysis.impacto_score_estimado} pts Score
                </p>
                <p>
                  <span className="text-zinc-500">Campos do Score:</span>{' '}
                  {modal.analysis.campos_score.join(', ')}
                </p>
                <p className="leading-relaxed rounded-lg border border-teal-800/40 bg-teal-950/20 p-3 text-zinc-200">
                  {modal.analysis.explicacao_ia}
                </p>
                <p className="text-[9px] text-zinc-600">
                  Análise Sinidu·IA ({modal.analysis.ai_provider || 'Mistral'}) · Use com critério
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
