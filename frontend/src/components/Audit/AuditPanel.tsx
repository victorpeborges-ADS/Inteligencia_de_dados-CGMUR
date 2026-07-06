'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, type AuditLogEntry } from '@/utils/api';
import { ClipboardList, Loader2, RefreshCw, ShieldAlert } from 'lucide-react';

const ACTION_LABELS: Record<string, string> = {
  'report.generate': 'Gerar PDF municipal',
  'report.completo': 'Relatório completo (sync)',
  'report.completo_async': 'Relatório completo (async)',
  'report.download': 'Download PDF',
  'report.sei_export': 'Export SEI',
  'diagnostic.generate': 'Gerar diagnóstico PDF',
  'diagnostic.download_pdf': 'Download diagnóstico PDF',
  'presentation.view': 'Abrir apresentação',
  'action_plan.generate': 'Gerar plano de ação',
  'onboarding.ensure': 'Recarregar município',
  'onboarding.run': 'Executar onboarding',
  'compare.analytics': 'Comparar municípios (analytics)',
  'compare.monitoring': 'Comparar municípios (monitor)',
  'simulation.export_geojson': 'Export GeoJSON simulação',
  'simulation.export_pdf': 'Export PDF simulação',
  'contingency.activate': 'Ativar contingência',
  'contingency.export_pdf': 'Export PDF contingência',
  'contingency.sei_export': 'Export SEI contingência',
};

function formatAction(action: string): string {
  return ACTION_LABELS[action] || action;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pt-BR', {
      dateStyle: 'short',
      timeStyle: 'medium',
    });
  } catch {
    return iso;
  }
}

export default function AuditPanel({ codigoIbge }: { codigoIbge?: string }) {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionFilter, setActionFilter] = useState('');
  const [usernameFilter, setUsernameFilter] = useState('');
  const [ibgeFilter, setIbgeFilter] = useState(codigoIbge || '');

  useEffect(() => {
    if (codigoIbge) setIbgeFilter(codigoIbge);
  }, [codigoIbge]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await api.listAuditLog({
        limit: 100,
        action: actionFilter || undefined,
        username: usernameFilter || undefined,
        codigo_ibge: ibgeFilter || undefined,
      });
      setEntries(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao carregar auditoria');
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [actionFilter, usernameFilter, ibgeFilter]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pr-1">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-indigo-300">
            <ClipboardList className="h-4 w-4" />
            Trilha de auditoria
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            PDFs, diagnósticos, comparações, onboarding, simulações e contingência.
          </p>
        </div>
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

      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="mb-1 block text-[10px] uppercase tracking-wider text-zinc-500">Ação</label>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200"
          >
            <option value="">Todas</option>
            {Object.entries(ACTION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-[10px] uppercase tracking-wider text-zinc-500">IBGE</label>
          <input
            value={ibgeFilter}
            onChange={(e) => setIbgeFilter(e.target.value)}
            placeholder="2611606"
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200"
          />
        </div>
        <div>
          <label className="mb-1 block text-[10px] uppercase tracking-wider text-zinc-500">Usuário</label>
          <input
            value={usernameFilter}
            onChange={(e) => setUsernameFilter(e.target.value)}
            placeholder="dev, admin…"
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-xs text-zinc-200"
          />
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-rose-800 bg-rose-950/40 px-3 py-2 text-xs text-rose-200">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {loading && entries.length === 0 ? (
        <Loader2 className="mx-auto h-6 w-6 animate-spin text-zinc-400" />
      ) : entries.length === 0 ? (
        <p className="text-sm text-zinc-500">Nenhum registro encontrado. Execute uma ação (PDF, diagnóstico, comparação) e atualize.</p>
      ) : (
        <div className="space-y-2">
          {entries.map((row) => (
            <article
              key={row.id}
              className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-zinc-200">{formatAction(row.action)}</span>
                <time className="text-[10px] text-zinc-500">{formatDate(row.created_at)}</time>
              </div>
              <p className="mt-1 text-zinc-400">
                <span className="text-zinc-300">{row.username}</span>
                <span className="text-zinc-600"> · </span>
                {row.role}
                {row.codigo_ibge && (
                  <>
                    <span className="text-zinc-600"> · IBGE </span>
                    {row.codigo_ibge}
                  </>
                )}
              </p>
              {row.metadata && Object.keys(row.metadata).length > 0 && (
                <p className="mt-0.5 text-[10px] text-zinc-500">{JSON.stringify(row.metadata)}</p>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
