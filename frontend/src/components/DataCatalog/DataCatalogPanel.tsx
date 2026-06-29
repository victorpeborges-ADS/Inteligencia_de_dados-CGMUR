'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, type DataCoverage, type DataCatalogNational } from '@/utils/api';
import { Database, Loader2, RefreshCw } from 'lucide-react';

const STATUS_STYLE: Record<string, string> = {
  Integrado: 'bg-emerald-500/15 text-emerald-300 border-emerald-700/40',
  Estimado: 'bg-amber-500/15 text-amber-300 border-amber-700/40',
  'Em integracao': 'bg-sky-500/15 text-sky-300 border-sky-700/40',
  Ausente: 'bg-rose-500/15 text-rose-300 border-rose-700/40',
};

function StatusPill({ status }: { status: string }) {
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[8px] font-bold uppercase ${STATUS_STYLE[status] || 'bg-zinc-800 text-zinc-400'}`}>
      {status}
    </span>
  );
}

type DataCatalogPanelProps = {
  codigoIbge: string;
  isGestorOrAdmin: boolean;
};

export default function DataCatalogPanel({ codigoIbge, isGestorOrAdmin }: DataCatalogPanelProps) {
  const [coverage, setCoverage] = useState<DataCoverage | null>(null);
  const [national, setNational] = useState<DataCatalogNational | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const municipal = await api.getDataCoverage(codigoIbge);
      setCoverage(municipal);
      if (isGestorOrAdmin) {
        try {
          const pan = await api.getNationalDataCatalog();
          setNational(pan);
        } catch {
          setNational(null);
        }
      } else {
        setNational(null);
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

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pr-1">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-indigo-300">
            <Database className="h-4 w-4" />
            Catálogo de Dados
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            Maturidade informacional e lacunas de integração — {coverage.municipio.nome}/{coverage.municipio.uf}.
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

      <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[10px] font-bold uppercase text-zinc-500">Municipal</span>
          <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-bold text-indigo-200">
            {coverage.classificacao} · {coverage.maturidade_percentual}%
          </span>
        </div>
        <p className="mb-3 text-xs text-zinc-400">{coverage.resumo}</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {coverage.bases.map((base) => (
            <div key={base.id} className="rounded-lg border border-zinc-800 bg-zinc-950/80 p-2">
              <div className="flex items-center justify-between gap-2">
                <strong className="truncate text-[10px] text-zinc-200">{base.nome}</strong>
                <StatusPill status={base.status} />
              </div>
              <p className="mt-1 text-[9px] leading-snug text-zinc-500">{base.recomendacao}</p>
              {base.camada && (
                <p className="mt-1 font-mono text-[8px] text-zinc-600">camada: {base.camada}</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {coverage.lacunas_prioritarias.length > 0 && (
        <div className="rounded-xl border border-amber-900/40 bg-amber-950/20 p-3">
          <div className="mb-2 text-[10px] font-bold uppercase text-amber-600/80">Lacunas prioritárias</div>
          <ul className="space-y-2">
            {coverage.lacunas_prioritarias.map((item) => (
              <li key={item.id} className="flex items-start justify-between gap-2 text-xs text-zinc-300">
                <span>{item.nome}</span>
                <StatusPill status={item.status} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {national && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase text-zinc-500">
              Panorama nacional ({national.total_municipios} prioritários)
            </span>
            <span className="text-[10px] text-zinc-400">
              Média {national.media_maturidade_percentual}% · {national.classificacao}
            </span>
          </div>
          <p className="mb-3 text-xs text-zinc-500">{national.resumo}</p>

          <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {national.bases.slice(0, 6).map((base) => (
              <div key={base.id} className="rounded-lg border border-zinc-800 p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-[10px] text-zinc-200">{base.nome}</span>
                  <span className="text-[10px] font-mono text-emerald-300">{base.integrado_pct}% OK</span>
                </div>
              </div>
            ))}
          </div>

          {national.lacunas_frequentes.length > 0 && (
            <>
              <div className="mb-1 text-[10px] font-bold uppercase text-zinc-500">Lacunas mais frequentes</div>
              <ul className="space-y-1 text-xs text-zinc-400">
                {national.lacunas_frequentes.map((gap) => (
                  <li key={gap.id} className="flex justify-between gap-2">
                    <span>{gap.nome}</span>
                    <span className="font-mono text-zinc-500">{gap.municipios} municípios</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          <div className="mt-3 max-h-40 overflow-y-auto">
            <div className="mb-1 text-[10px] font-bold uppercase text-zinc-500">Ranking municipal</div>
            <table className="w-full text-left text-[10px]">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500">
                  <th className="py-1 pr-2">Município</th>
                  <th className="py-1 pr-2">UF</th>
                  <th className="py-1">Maturidade</th>
                </tr>
              </thead>
              <tbody>
                {national.municipios.slice(0, 12).map((row) => (
                  <tr key={row.codigo_ibge} className="border-b border-zinc-900/80 text-zinc-300">
                    <td className="py-1 pr-2 truncate max-w-[140px]">{row.nome}</td>
                    <td className="py-1 pr-2">{row.uf}</td>
                    <td className="py-1 font-mono">{row.maturidade_percentual}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
