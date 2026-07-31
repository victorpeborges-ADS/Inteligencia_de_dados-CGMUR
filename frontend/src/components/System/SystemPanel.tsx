'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, type BackgroundJob, type SystemOverview } from '@/utils/api';
import {
  Activity,
  Building2,
  Database,
  ExternalLink,
  Loader2,
  Play,
  RefreshCw,
  Server,
  Shield,
  Zap,
} from 'lucide-react';

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${
        ok
          ? 'border-emerald-700/50 bg-emerald-950/40 text-emerald-300'
          : 'border-rose-700/50 bg-rose-950/40 text-rose-300'
      }`}
    >
      {label}
    </span>
  );
}

export default function SystemPanel() {
  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [batchRunning, setBatchRunning] = useState(false);
  const [mapbiomasSyncing, setMapbiomasSyncing] = useState(false);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [exportsRunning, setExportsRunning] = useState(false);
  const [fontesRunning, setFontesRunning] = useState(false);
  const [ctmRunning, setCtmRunning] = useState(false);
  const [homologationRunning, setHomologationRunning] = useState(false);
  const [demBatchRunning, setDemBatchRunning] = useState(false);
  const [demUploading, setDemUploading] = useState(false);
  const [activeJob, setActiveJob] = useState<BackgroundJob | null>(null);
  const [recentJobs, setRecentJobs] = useState<BackgroundJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [mlStatus, setMlStatus] = useState<{
    ready_count: number;
    total: number;
    note?: string;
    models?: Array<{
      codigo_ibge: string;
      ready: boolean;
      model_kind?: string | null;
      auc_roc_cv?: number | null;
      threshold_mm_24h?: number | null;
    }>;
  } | null>(null);
  const [mlBootstrapping, setMlBootstrapping] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, jobs, flood] = await Promise.all([
        api.getSystemOverview(),
        api.listBackgroundJobs(8).catch(() => ({ items: [] as BackgroundJob[] })),
        api.getFloodModelStatus().catch(() => null),
      ]);
      setOverview(data);
      setRecentJobs(jobs.items);
      setMlStatus(flood);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao carregar visão do sistema');
      setOverview(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const runIntegrationSync = async () => {
    setSyncing(true);
    setSyncMessage(null);
    try {
      const result = await api.syncIntegrations();
      const summary = result.summary;
      setSyncMessage(
        `Sync concluído — IBGE: ${summary.ibge}, SICONFI: ${summary.siconfi}, CAPAG: ${summary.capag}, SNIS: ${summary.snis}`,
      );
      await load();
    } catch (e) {
      setSyncMessage(e instanceof Error ? e.message : 'Falha no sync de integrações');
    } finally {
      setSyncing(false);
    }
  };

  const pollJob = useCallback(async (jobId: string) => {
    for (let i = 0; i < 120; i++) {
      const job = await api.getBackgroundJob(jobId);
      setActiveJob(job);
      if (job.status === 'completed' || job.status === 'failed') {
        await load();
        return job;
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
    return null;
  }, [load]);

  const runBatchOnboarding = async () => {
    setBatchRunning(true);
    setSyncMessage(null);
    try {
      const { job_id } = await api.startOnboardingBatchJob(6, 'pendente');
      setSyncMessage(`Onboarding em background (job ${job_id})…`);
      const job = await pollJob(job_id);
      if (job?.status === 'completed') {
        const result = job.result as { processed?: number; requested?: number };
        setSyncMessage(`Onboarding — ${result?.processed ?? '?'}/${result?.requested ?? '?'} processados`);
      } else if (job?.status === 'failed') {
        setSyncMessage(job.error || 'Onboarding falhou');
      }
    } catch (e) {
      setSyncMessage(e instanceof Error ? e.message : 'Falha no onboarding em lote');
    } finally {
      setBatchRunning(false);
    }
  };

  const runPipeline = async () => {
    setPipelineRunning(true);
    setSyncMessage(null);
    try {
      const { job_id } = await api.startPipelineJob(6);
      setSyncMessage(`Pipeline territorial em execução (job ${job_id})…`);
      const job = await pollJob(job_id);
      if (job?.status === 'completed') {
        setSyncMessage('Pipeline concluído — ETL + onboarding + MapBiomas');
      } else if (job?.status === 'failed') {
        setSyncMessage(job.error || 'Pipeline falhou');
      }
    } catch (e) {
      setSyncMessage(e instanceof Error ? e.message : 'Falha no pipeline');
    } finally {
      setPipelineRunning(false);
    }
  };

  const runExportsBatch = async (kind: 'diagnostics' | 'reports', codigos?: string[]) => {
    setExportsRunning(true);
    setSyncMessage(null);
    try {
      const starter =
        kind === 'diagnostics'
          ? () => api.startDiagnosticsBatchJob(6)
          : () => api.startReportsBatchJob(6, true, codigos);
      const { job_id } = await starter();
      setSyncMessage(`${kind === 'diagnostics' ? 'Diagnósticos' : 'PDFs'} em lote (job ${job_id})…`);
      const job = await pollJob(job_id);
      if (job?.status === 'completed') {
        const result = job.result as { processed?: number; requested?: number };
        setSyncMessage(`${kind === 'diagnostics' ? 'Diagnósticos' : 'PDFs'} — ${result?.processed ?? '?'}/${result?.requested ?? '?'} processados`);
      } else if (job?.status === 'failed') {
        setSyncMessage(job.error || 'Exportação em lote falhou');
      }
    } catch (e) {
      setSyncMessage(e instanceof Error ? e.message : 'Falha na exportação em lote');
    } finally {
      setExportsRunning(false);
    }
  };

  const runDemBatch = async () => {
    setDemBatchRunning(true);
    setSyncMessage(null);
    try {
      const { job_id } = await api.startDemBatchJob(6, false);
      setSyncMessage(`Batch DEM em execução (job ${job_id})…`);
      const job = await pollJob(job_id);
      if (job?.status === 'completed') {
        const result = job.result as { processed?: number; local_or_refined?: number };
        setSyncMessage(
          `DEM — ${result?.processed ?? '?'}/6 processados` +
            (result?.local_or_refined != null ? ` (${result.local_or_refined} local/refinado)` : ''),
        );
      } else if (job?.status === 'failed') {
        setSyncMessage(job.error || 'Batch DEM falhou');
      }
    } catch (e) {
      setSyncMessage(e instanceof Error ? e.message : 'Falha no batch DEM');
    } finally {
      setDemBatchRunning(false);
    }
  };

  const runHomologationFull = async () => {
    setHomologationRunning(true);
    setSyncMessage(null);
    try {
      const { job_id } = await api.startHomologationFullJob(6, false);
      setSyncMessage(`Pipeline MCID completo em execução (job ${job_id})…`);
      const job = await pollJob(job_id);
      if (job?.status === 'completed') {
        const result = job.result as {
          onboarding?: { processed?: number };
          dem?: { processed?: number };
          diagnostics?: { processed?: number };
        };
        setSyncMessage(
          `Homologação concluída — onboarding ${result?.onboarding?.processed ?? '?'}, ` +
            `DEM ${result?.dem?.processed ?? '?'}, diagnósticos ${result?.diagnostics?.processed ?? '?'}`,
        );
      } else if (job?.status === 'failed') {
        setSyncMessage(job.error || 'Pipeline MCID falhou');
      }
    } catch (e) {
      setSyncMessage(e instanceof Error ? e.message : 'Falha no pipeline MCID completo');
    } finally {
      setHomologationRunning(false);
    }
  };

  const runDemUpload = async (file: File) => {
    if (!overview?.municipalities.piloto_ibge) return;
    setDemUploading(true);
    setSyncMessage(null);
    try {
      const result = await api.importLocalDem(overview.municipalities.piloto_ibge, file, true);
      const cfg = result.config as { dem_source?: string; dem_resolution_m?: number } | undefined;
      setSyncMessage(
        `LiDAR importado — ${cfg?.dem_source ?? 'DEM local'}${cfg?.dem_resolution_m != null ? ` (${cfg.dem_resolution_m} m)` : ''}`,
      );
    } catch (e) {
      setSyncMessage(e instanceof Error ? e.message : 'Falha no upload LiDAR');
    } finally {
      setDemUploading(false);
    }
  };

  const runFontesExternas = async () => {
    setFontesRunning(true);
    setSyncMessage(null);
    try {
      const { job_id } = await api.startExternalSourcesBatchJob(6);
      setSyncMessage(`Fontes externas (job ${job_id})…`);
      const job = await pollJob(job_id);
      if (job?.status === 'completed') {
        const result = job.result as { processed?: number; requested?: number };
        setSyncMessage(`Fontes externas — ${result?.processed ?? '?'}/${result?.requested ?? '?'} sincronizados`);
      } else if (job?.status === 'failed') {
        setSyncMessage(job.error || 'Sync fontes externas falhou');
      }
    } catch (e) {
      setSyncMessage(e instanceof Error ? e.message : 'Falha no sync de fontes externas');
    } finally {
      setFontesRunning(false);
    }
  };

  const runCtmBatch = async (force = false) => {
    setCtmRunning(true);
    setSyncMessage(null);
    try {
      const { job_id } = await api.startCtmBatchJob(force);
      setSyncMessage(`CTM / geoportal${force ? ' (forçar)' : ''} (job ${job_id})…`);
      const job = await pollJob(job_id);
      if (job?.status === 'completed') {
        const result = job.result as { ok?: number; erro?: number; pulados?: number };
        setSyncMessage(
          `CTM concluído — ${result?.ok ?? 0} importados, ${result?.pulados ?? 0} pulados, ${result?.erro ?? 0} erros`,
        );
        await load();
      } else if (job?.status === 'failed') {
        setSyncMessage(job.error || 'Batch CTM falhou');
      }
    } catch (e) {
      setSyncMessage(e instanceof Error ? e.message : 'Falha no batch CTM');
    } finally {
      setCtmRunning(false);
    }
  };

  const runMapBiomasBatch = async () => {
    setMapbiomasSyncing(true);
    setSyncMessage(null);
    try {
      const { job_id } = await api.startMapBiomasBatchJob(6, false);
      setSyncMessage(`MapBiomas em background (job ${job_id})…`);
      const job = await pollJob(job_id);
      if (job?.status === 'completed') {
        const result = job.result as { processed?: number; requested?: number; errors?: unknown[] };
        setSyncMessage(
          `MapBiomas — ${result?.processed ?? '?'}/${result?.requested ?? '?'} processados` +
            (Array.isArray(result?.errors) && result.errors.length ? ` (${result.errors.length} skip/erro)` : ''),
        );
      } else if (job?.status === 'failed') {
        setSyncMessage(job.error || 'MapBiomas falhou');
      }
    } catch (e) {
      setSyncMessage(e instanceof Error ? e.message : 'Falha no sync MapBiomas');
    } finally {
      setMapbiomasSyncing(false);
    }
  };

  if (loading && !overview) {
    return (
      <div className="flex h-full items-center justify-center text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Carregando status operacional…
      </div>
    );
  }

  if (error && !overview) {
    return (
      <div className="rounded-xl border border-rose-800/50 bg-rose-950/30 p-4 text-sm text-rose-200">
        {error}
      </div>
    );
  }

  if (!overview) return null;

  const dbOk = overview.checks.database.ok;
  const ollamaOk = overview.checks.ollama.ok;

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pr-1">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-cyan-300">
            <Server className="h-4 w-4" />
            Operação do sistema
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            Saúde da stack, integrações ETL, onboarding e auditoria — homologação MCID.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={runBatchOnboarding}
            disabled={batchRunning}
            className="inline-flex items-center gap-1 rounded-lg border border-indigo-800 bg-indigo-950/40 px-2 py-1 text-xs text-indigo-200 hover:bg-indigo-900/40 disabled:opacity-50"
          >
            {batchRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Building2 className="h-3.5 w-3.5" />}
            Onboarding (6)
          </button>
          <button
            type="button"
            onClick={runDemBatch}
            disabled={demBatchRunning}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-950/40 px-2 py-1 text-xs text-slate-200 hover:bg-slate-900/40 disabled:opacity-50"
          >
            {demBatchRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Database className="h-3.5 w-3.5" />}
            DEM (6)
          </button>
          <button
            type="button"
            onClick={runHomologationFull}
            disabled={homologationRunning}
            className="inline-flex items-center gap-1 rounded-lg border border-amber-800 bg-amber-950/40 px-2 py-1 text-xs text-amber-200 hover:bg-amber-900/40 disabled:opacity-50"
          >
            {homologationRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Pipeline MCID (6)
          </button>
          <label
            className={`inline-flex cursor-pointer items-center gap-1 rounded-lg border border-sky-800 bg-sky-950/40 px-2 py-1 text-xs text-sky-200 hover:bg-sky-900/40 ${demUploading ? 'opacity-50' : ''}`}
          >
            {demUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Database className="h-3.5 w-3.5" />}
            LiDAR piloto
            <input
              type="file"
              accept=".tif,.tiff,.geotiff"
              className="hidden"
              disabled={demUploading}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void runDemUpload(file);
                e.target.value = '';
              }}
            />
          </label>
          <button
            type="button"
            onClick={runPipeline}
            disabled={pipelineRunning}
            className="inline-flex items-center gap-1 rounded-lg border border-violet-800 bg-violet-950/40 px-2 py-1 text-xs text-violet-200 hover:bg-violet-900/40 disabled:opacity-50"
          >
            {pipelineRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            Pipeline
          </button>
          <button
            type="button"
            onClick={() => runExportsBatch('diagnostics')}
            disabled={exportsRunning}
            className="inline-flex items-center gap-1 rounded-lg border border-cyan-800 bg-cyan-950/40 px-2 py-1 text-xs text-cyan-200 hover:bg-cyan-900/40 disabled:opacity-50"
          >
            Diagnósticos (6)
          </button>
          <button
            type="button"
            onClick={() => runExportsBatch('reports')}
            disabled={exportsRunning}
            className="inline-flex items-center gap-1 rounded-lg border border-rose-800 bg-rose-950/40 px-2 py-1 text-xs text-rose-200 hover:bg-rose-900/40 disabled:opacity-50"
          >
            PDFs (6)
          </button>
          <button
            type="button"
            onClick={runFontesExternas}
            disabled={fontesRunning}
            className="inline-flex items-center gap-1 rounded-lg border border-teal-800 bg-teal-950/40 px-2 py-1 text-xs text-teal-200 hover:bg-teal-900/40 disabled:opacity-50"
          >
            Fontes ext.
          </button>
          <button
            type="button"
            onClick={() => runCtmBatch(false)}
            disabled={ctmRunning}
            className="inline-flex items-center gap-1 rounded-lg border border-violet-800 bg-violet-950/40 px-2 py-1 text-xs text-violet-200 hover:bg-violet-900/40 disabled:opacity-50"
          >
            {ctmRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Building2 className="h-3.5 w-3.5" />}
            CTM (24)
          </button>
          <button
            type="button"
            onClick={() => runCtmBatch(true)}
            disabled={ctmRunning}
            title="Reimporta mesmo com malha densa existente"
            className="inline-flex items-center gap-1 rounded-lg border border-violet-900/60 px-2 py-1 text-[10px] text-violet-300/80 hover:bg-violet-950/30 disabled:opacity-50"
          >
            CTM forçar
          </button>
          <button
            type="button"
            onClick={runMapBiomasBatch}
            disabled={mapbiomasSyncing}
            className="inline-flex items-center gap-1 rounded-lg border border-emerald-800 bg-emerald-950/40 px-2 py-1 text-xs text-emerald-200 hover:bg-emerald-900/40 disabled:opacity-50"
          >
            {mapbiomasSyncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Database className="h-3.5 w-3.5" />}
            MapBiomas
          </button>
          <button
            type="button"
            onClick={runIntegrationSync}
            disabled={syncing}
            className="inline-flex items-center gap-1 rounded-lg border border-cyan-800 bg-cyan-950/40 px-2 py-1 text-xs text-cyan-200 hover:bg-cyan-900/40 disabled:opacity-50"
          >
            {syncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
            Sync ETL
          </button>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Atualizar
          </button>
        </div>
      </div>

      {syncMessage && (
        <div className="rounded-lg border border-cyan-800/40 bg-cyan-950/30 px-3 py-2 text-xs text-cyan-100">
          {syncMessage}
        </div>
      )}

      {activeJob && activeJob.status === 'running' && (
        <div className="rounded-lg border border-violet-800/40 bg-violet-950/30 px-3 py-2 text-xs text-violet-100">
          Job {activeJob.label} — em execução…
        </div>
      )}

      {overview.scheduler?.running && overview.scheduler.jobs.length > 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 text-[10px] font-bold uppercase text-zinc-500">Scheduler (APScheduler)</div>
          <ul className="space-y-1 text-xs text-zinc-400">
            {overview.scheduler.jobs.slice(0, 5).map((job) => (
              <li key={job.id} className="flex justify-between gap-2">
                <span className="font-mono">{job.id}</span>
                <span className="truncate text-zinc-500">{job.next_run || '—'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {recentJobs.length > 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 text-[10px] font-bold uppercase text-zinc-500">Jobs recentes</div>
          <ul className="space-y-1 text-xs text-zinc-400">
            {recentJobs.map((job) => (
              <li key={job.id} className="flex items-center justify-between gap-2">
                <span className="truncate">{job.label}</span>
                <StatusBadge
                  ok={job.status === 'completed'}
                  label={job.status === 'running' ? '…' : job.status}
                />
              </li>
            ))}
          </ul>
        </div>
      )}

      {overview.routing && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase text-zinc-500">Malha viária OSRM</span>
            <StatusBadge ok={overview.routing.available} label={overview.routing.available ? 'online' : 'off'} />
          </div>
          <ul className="space-y-1 text-xs text-zinc-400">
            <li>Região PBF: {overview.routing.region}</li>
            <li>UFs cobertas: {overview.routing.covered_ufs.join(', ') || '—'}</li>
            <li className="truncate text-zinc-500">{overview.routing.detail}</li>
            {!overview.routing.available && overview.routing.setup_hint && (
              <li className="mt-1 font-mono text-[10px] text-amber-400/90">{overview.routing.setup_hint}</li>
            )}
          </ul>
        </div>
      )}

      {mlStatus && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="text-[10px] font-bold uppercase text-zinc-500">ML alagamento</span>
            <div className="flex items-center gap-2">
              <StatusBadge
                ok={mlStatus.ready_count >= mlStatus.total}
                label={`${mlStatus.ready_count}/${mlStatus.total}`}
              />
              <button
                type="button"
                disabled={mlBootstrapping}
                onClick={async () => {
                  setMlBootstrapping(true);
                  try {
                    await api.bootstrapFloodModels();
                    const flood = await api.getFloodModelStatus();
                    setMlStatus(flood);
                    setSyncMessage('Modelos ML de alagamento preparados.');
                  } catch (e) {
                    setError(e instanceof Error ? e.message : 'Falha no bootstrap ML');
                  } finally {
                    setMlBootstrapping(false);
                  }
                }}
                className="inline-flex items-center gap-1 rounded border border-zinc-700 px-2 py-0.5 text-[10px] font-bold uppercase text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
              >
                {mlBootstrapping ? <Loader2 className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
                Bootstrap
              </button>
            </div>
          </div>
          <p className="text-[10px] leading-relaxed text-zinc-500">
            {mlStatus.note || `${mlStatus.total} municípios-alvo com artefato dedicado; demais on-demand.`}
          </p>
          {mlStatus.models && mlStatus.models.length > 0 && (
            <ul className="mt-2 max-h-36 space-y-1 overflow-y-auto text-[10px] text-zinc-400">
              {mlStatus.models.map((m) => (
                <li
                  key={m.codigo_ibge}
                  className="flex flex-wrap items-center justify-between gap-1 rounded border border-zinc-800/80 bg-zinc-900/40 px-2 py-1"
                >
                  <span className="font-mono text-zinc-300">{m.codigo_ibge}</span>
                  <span className={m.ready ? 'text-emerald-400' : 'text-zinc-600'}>
                    {m.ready ? 'pronto' : 'pendente'}
                  </span>
                  <span className="text-zinc-500">
                    {m.model_kind || '—'}
                    {m.threshold_mm_24h != null ? ` · limiar ${m.threshold_mm_24h} mm` : ''}
                    {m.auc_roc_cv != null ? ` · AUC ${Number(m.auc_roc_cv).toFixed(2)}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="rounded-xl border border-amber-900/40 bg-amber-950/20 p-3">
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-[10px] font-bold uppercase text-amber-600/80">Ecossistema MCID</span>
          <a
            href="https://www.gov.br/cidades/pt-br/acesso-a-informacao/participacao-social/pro-cidades"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[10px] text-amber-300 hover:text-amber-200"
          >
            Pro-Cidades <ExternalLink className="h-3 w-3" />
          </a>
        </div>
        <p className="text-xs text-zinc-400">
          Parecer de mérito FGTS (IN MCID 18/2025) permanece no sistema dedicado Pro-Cidades. Sinidu+Clima
          concentra inteligência territorial, mapa e integrações climáticas.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase text-zinc-500">Plataforma</span>
            <StatusBadge ok={overview.checks.overall === 'healthy'} label={overview.checks.overall} />
          </div>
          <p className="text-xs text-zinc-300">{overview.platform}</p>
          <p className="mt-1 text-[10px] text-zinc-500">Ambiente: {overview.environment}</p>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 flex items-center gap-1 text-[10px] font-bold uppercase text-zinc-500">
            <Shield className="h-3 w-3" /> Auth
          </div>
          <ul className="space-y-1 text-xs text-zinc-300">
            <li>JWT: {overview.auth.enabled ? 'ligado' : 'desligado'}</li>
            <li>Multi-tenant: {overview.auth.multi_tenant ? 'sim' : 'não'}</li>
            <li>OIDC: {overview.auth.oidc_enabled ? 'sim' : 'não'}</li>
            {overview.checks.oidc.configured && (
              <li className={overview.checks.oidc.reachable ? 'text-emerald-300' : 'text-amber-300'}>
                IdP: {overview.checks.oidc.reachable ? 'acessível' : 'offline'}
              </li>
            )}
            <li className="truncate text-zinc-500">URL: {overview.auth.public_base_url}</li>
          </ul>
        </div>
      </div>

      {overview.homologation && (
        <div className="rounded-xl border border-sky-900/40 bg-sky-950/10 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="text-[10px] font-bold uppercase text-sky-300">
              Prontidão homologação (protótipo)
            </span>
            <div className="flex flex-wrap gap-2">
              <StatusBadge
                ok={Boolean(overview.homologation.ready_for_demo)}
                label={overview.homologation.ready_for_demo ? 'Demo OK' : 'Demo pendente'}
              />
              <StatusBadge
                ok={overview.homologation.ready_for_sso_test}
                label={overview.homologation.ready_for_sso_test ? 'SSO Keycloak' : 'Auth local'}
              />
              <StatusBadge
                ok={overview.homologation.score_pct >= 70}
                label={`${overview.homologation.score_pct}%`}
              />
            </div>
          </div>
          {overview.homologation.note ? (
            <p className="mb-2 text-[10px] text-zinc-500">{overview.homologation.note}</p>
          ) : null}
          <ul className="grid gap-1 sm:grid-cols-2">
            {overview.homologation.items
              .filter((i) => i.status !== 'na')
              .map((item) => (
                <li
                  key={item.id}
                  className={`rounded border px-2 py-1 text-[11px] ${
                    item.status === 'ok'
                      ? 'border-emerald-900/40 text-emerald-200'
                      : item.status === 'warn'
                        ? 'border-amber-900/40 text-amber-200'
                        : 'border-rose-900/40 text-rose-200'
                  }`}
                >
                  <span className="font-medium">{item.label}</span>
                  {item.detail ? (
                    <span className="block truncate text-[10px] opacity-80">{item.detail}</span>
                  ) : null}
                </li>
              ))}
          </ul>
          {overview.homologation.next_steps.length > 0 && (
            <p className="mt-2 text-[10px] text-zinc-500">
              Próximo: {overview.homologation.next_steps[0]}
            </p>
          )}
        </div>
      )}

      <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
        <div className="mb-2 flex items-center gap-1 text-[10px] font-bold uppercase text-zinc-500">
          <Activity className="h-3 w-3" /> Checks
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-lg border border-zinc-800 p-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-zinc-400">PostgreSQL</span>
              <StatusBadge ok={dbOk} label={dbOk ? 'ok' : 'erro'} />
            </div>
            <p className="mt-1 truncate text-[10px] text-zinc-500">{overview.checks.database.detail}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 p-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-zinc-400">Ollama</span>
              <StatusBadge ok={ollamaOk} label={ollamaOk ? 'ok' : 'off'} />
            </div>
            <p className="mt-1 text-[10px] text-zinc-500">
              VRAM: {overview.checks.ollama.total_vram_gb ?? '—'} GB
            </p>
          </div>
          <div className="rounded-lg border border-zinc-800 p-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-zinc-400">Fallback IA</span>
              <StatusBadge
                ok={overview.checks.ai_fallback.fallback_available}
                label={overview.checks.ai_fallback.gemini_configured ? 'Gemini' : 'local'}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 flex items-center gap-1 text-[10px] font-bold uppercase text-zinc-500">
            <Database className="h-3 w-3" /> Municípios
          </div>
          <ul className="space-y-1 text-xs text-zinc-300">
            <li>Prioritários (seed): {overview.municipalities.prioritarios_seed}</li>
            <li>Carregados no banco: {overview.municipalities.carregados_db}</li>
            <li>
              Piloto: {overview.municipalities.piloto_nome} ({overview.municipalities.piloto_ibge})
            </li>
            <li className="text-zinc-500">
              Onboarding — concluídos: {overview.onboarding.concluidos}, pendentes:{' '}
              {overview.onboarding.pendentes}
            </li>
          </ul>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 text-[10px] font-bold uppercase text-zinc-500">Boot</div>
          <ul className="space-y-1 text-xs text-zinc-300">
            <li>DB ready: {overview.boot.db_ready ? 'sim' : 'não'}</li>
            <li>Migrations: {overview.boot.migrations_applied.length}</li>
            <li>Scheduler integrações: {overview.boot.integration_scheduler ? 'ativo' : 'off'}</li>
            {overview.boot.errors.length > 0 && (
              <li className="text-amber-300">{overview.boot.errors.length} aviso(s) no boot</li>
            )}
          </ul>
        </div>
      </div>

      {overview.batch_coverage && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase text-zinc-500">Homologação — diagnósticos e PDFs</span>
            <div className="flex gap-2">
              <StatusBadge
                ok={overview.batch_coverage.diagnosticos_ok}
                label={`Diag ${overview.batch_coverage.com_diagnostico}/${overview.batch_coverage.municipios_total}`}
              />
              <StatusBadge
                ok={overview.batch_coverage.relatorios_ok}
                label={`PDF ${overview.batch_coverage.com_relatorio}/${overview.batch_coverage.municipios_total}`}
              />
            </div>
          </div>
          {overview.batch_coverage.sem_relatorio.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <p className="text-xs text-amber-200">
                Sem PDF:{' '}
                {overview.batch_coverage.sem_relatorio
                  .map((m) => `${m.nome}/${m.uf}`)
                  .join(', ')}
              </p>
              <button
                type="button"
                onClick={() =>
                  runExportsBatch(
                    'reports',
                    overview.batch_coverage!.sem_relatorio.map((m) => m.codigo_ibge),
                  )
                }
                disabled={exportsRunning}
                className="rounded border border-rose-800 bg-rose-950/40 px-2 py-0.5 text-[10px] text-rose-200 hover:bg-rose-900/40 disabled:opacity-50"
              >
                Gerar PDFs pendentes
              </button>
            </div>
          )}
        </div>
      )}

      {overview.ctm && (
        <div className="rounded-xl border border-violet-900/40 bg-violet-950/10 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="text-[10px] font-bold uppercase text-violet-300">CTM / UTB — malha municipal</span>
            <div className="flex flex-wrap gap-2">
              <StatusBadge
                ok={
                  overview.ctm.importado_prefeitura + overview.ctm.malha_operacional >=
                  Math.floor(overview.ctm.total_alvo * 0.6)
                }
                label={`Malha ${
                  overview.ctm.importado_prefeitura + overview.ctm.malha_operacional
                }/${overview.ctm.total_alvo}`}
              />
              <StatusBadge
                ok={overview.ctm.fontes_cadastradas >= overview.ctm.total_alvo}
                label={`Fontes ${overview.ctm.fontes_cadastradas}/${overview.ctm.total_alvo}`}
              />
            </div>
          </div>
          <p className="text-xs text-zinc-400">
            {overview.ctm.progress_label} · {overview.ctm.malha_operacional} com malha operacional ·{' '}
            {overview.ctm.sem_fonte} sem REST · {overview.ctm.lacuna_municipios} lacunas
          </p>
          <p className="mt-1 text-[10px] text-zinc-600">{overview.ctm.escopo_label}</p>
        </div>
      )}

      {overview.integrations.sources.length > 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase text-zinc-500">Integrações ETL</span>
            <span className="text-[10px] text-zinc-500">
              {overview.integrations.integradas}/{overview.integrations.total} OK
            </span>
          </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-zinc-800 text-zinc-500">
                <th className="py-1 pr-2">Fonte</th>
                <th className="py-1 pr-2">Status</th>
                <th className="py-1 pr-2">Registros</th>
                <th className="py-1">Último sucesso</th>
              </tr>
            </thead>
            <tbody>
              {overview.integrations.sources.map((src) => (
                <tr key={src.source} className="border-b border-zinc-900/80 text-zinc-300">
                  <td className="py-1.5 pr-2 font-mono uppercase">{src.source}</td>
                  <td className="py-1.5 pr-2">
                    <StatusBadge ok={src.status === 'OK'} label={src.status} />
                  </td>
                  <td className="py-1.5 pr-2">{src.records_count}</td>
                  <td className="py-1.5 text-zinc-500">{src.last_success_at || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      )}

      <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
        <div className="mb-2 text-[10px] font-bold uppercase text-zinc-500">MapBiomas</div>
        <ul className="space-y-1 text-xs text-zinc-300">
          <li>Coleção: {overview.mapbiomas?.colecao ?? '—'}</li>
          <li>Municípios com série: {overview.mapbiomas?.municipios ?? 0}</li>
          <li>Registros: {overview.mapbiomas?.records ?? 0}</li>
          <li>CSV oficial: {overview.mapbiomas?.csv_configured ? 'configurado' : 'não (usa calibrado)'}</li>
        </ul>
      </div>

      {overview.dem && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 text-[10px] font-bold uppercase text-zinc-500">DEM / LiDAR</div>
          <ul className="space-y-1 text-xs text-zinc-300">
            <li>
              Processados: {overview.dem.processados}/{overview.dem.prioritarios}
            </li>
            <li>LiDAR/local: {overview.dem.local_ou_lidar}</li>
            <li>Refinado piloto: {overview.dem.refinado_piloto}</li>
            {overview.dem.resolucao_media_m != null && (
              <li>Resolução média: {overview.dem.resolucao_media_m} m</li>
            )}
            {overview.dem.piloto && (
              <li className="text-zinc-400">
                Piloto {overview.dem.piloto.nome}: {overview.dem.piloto.dem_source ?? 'pendente'}
                {overview.dem.piloto.dem_resolution_m != null
                  ? ` (${overview.dem.piloto.dem_resolution_m} m)`
                  : ''}
              </li>
            )}
            <li className="truncate text-zinc-500">Dir: {overview.dem.local_dem_dir}</li>
          </ul>
        </div>
      )}

      {overview.tls && overview.tls.status !== 'unavailable' && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase text-zinc-500">Certificado TLS</span>
            <StatusBadge
              ok={overview.tls.status === 'ok'}
              label={overview.tls.status === 'warning' ? 'expira' : overview.tls.status}
            />
          </div>
          <ul className="space-y-1 text-xs text-zinc-300">
            {overview.tls.subject && <li className="truncate">{overview.tls.subject}</li>}
            {overview.tls.not_after && <li>Expira: {overview.tls.not_after}</li>}
            {overview.tls.days_until_expiry != null && (
              <li className={overview.tls.days_until_expiry < 14 ? 'text-amber-300' : 'text-zinc-500'}>
                {overview.tls.days_until_expiry} dias restantes
              </li>
            )}
            {overview.tls.homolog_self_signed && (
              <li className="text-amber-300">Certificado autoassinado de homologação</li>
            )}
          </ul>
        </div>
      )}

      {overview.audit.total_eventos > 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 text-[10px] font-bold uppercase text-zinc-500">
            Auditoria ({overview.audit.total_eventos} eventos)
          </div>
          <ul className="space-y-1 text-xs text-zinc-400">
            {overview.audit.top_acoes.map((row) => (
              <li key={row.action} className="flex justify-between">
                <span>{row.action}</span>
                <span className="font-mono text-zinc-500">{row.count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
