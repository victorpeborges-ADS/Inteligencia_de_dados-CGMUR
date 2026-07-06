'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { api, type MonitoringCompareResult } from '@/utils/api';
import { Loader2, X, FileDown } from 'lucide-react';
import TermTooltip from '@/components/UI/TermTooltip';
import RotatingLoader from '@/components/UI/RotatingLoader';

type CompareModalProps = {
  open: boolean;
  onClose: () => void;
  codigoA: string;
  nomeA: string;
  municipalities: Array<{ codigo_ibge: string; nome: string; uf?: string }>;
};

function num(val: unknown): number | null {
  if (typeof val === 'number' && Number.isFinite(val)) return val;
  if (typeof val === 'string' && val.trim()) {
    const n = Number(val);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function str(val: unknown): string {
  return val != null ? String(val) : '—';
}

export default function CompareModal({ open, onClose, codigoA, nomeA, municipalities }: CompareModalProps) {
  const [codigoB, setCodigoB] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<MonitoringCompareResult | null>(null);

  useEffect(() => {
    if (!open) return;
    const municipioA = municipalities.find((m) => m.codigo_ibge === codigoA);
    const sameUf = municipalities.find(
      (m) => m.codigo_ibge !== codigoA && municipioA?.uf && m.uf === municipioA.uf,
    );
    const fallback = sameUf ?? municipalities.find((m) => m.codigo_ibge !== codigoA);
    setCodigoB(fallback?.codigo_ibge ?? '');
    setData(null);
    setError(null);
  }, [open, codigoA, municipalities]);

  const runCompare = async () => {
    if (!codigoB || codigoB === codigoA) {
      setError('Selecione um segundo município diferente.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api.compareMonitoringMunicipalities(codigoA, codigoB);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha na comparação');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && codigoB && codigoB !== codigoA) {
      runCompare().catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [codigoB, open]);

  const nomeB = municipalities.find((m) => m.codigo_ibge === codigoB)?.nome ?? codigoB;

  const radarData = useMemo(() => {
    if (!data) return [];
    const a = data.municipio_a as Record<string, unknown>;
    const b = data.municipio_b as Record<string, unknown>;
    const axes = [
      { axis: 'Score', a: num(a.score_sinidu) ?? 0, b: num(b.score_sinidu) ?? 0 },
      { axis: 'IVC', a: (num(a.media_ivc) ?? 0) * 100, b: (num(b.media_ivc) ?? 0) * 100 },
      { axis: 'IRI', a: (num(a.media_iri) ?? 0) * 100, b: (num(b.media_iri) ?? 0) * 100 },
      { axis: 'Maturidade', a: num(a.maturity_score) ?? 0, b: num(b.maturity_score) ?? 0 },
      { axis: 'Alertas', a: num(a.alertas_ativos) ?? 0, b: num(b.alertas_ativos) ?? 0 },
    ];
    return axes;
  }, [data]);

  const exportPdf = () => {
    if (!data) return;
    const a = data.municipio_a as Record<string, unknown>;
    const b = data.municipio_b as Record<string, unknown>;
    const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"/>
      <title>Comparação ${nomeA} × ${nomeB}</title>
      <style>body{font-family:Arial,sans-serif;margin:40px;color:#111}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:8px;font-size:13px}th{background:#e0e7ff}</style>
      </head><body>
      <h1>Comparação Municipal Sinidu+Clima</h1>
      <table><thead><tr><th>Indicador</th><th>${nomeA}</th><th>${nomeB}</th></tr></thead>
      <tbody>
      <tr><td>Score</td><td>${str(a.score_sinidu)}</td><td>${str(b.score_sinidu)}</td></tr>
      <tr><td>IVC médio</td><td>${str(a.media_ivc)}</td><td>${str(b.media_ivc)}</td></tr>
      <tr><td>IRI médio</td><td>${str(a.media_iri)}</td><td>${str(b.media_iri)}</td></tr>
      <tr><td>CAPAG</td><td>${str(a.nota_capag)}</td><td>${str(b.nota_capag)}</td></tr>
      <tr><td>Maturidade</td><td>${str(a.maturity_score)}</td><td>${str(b.maturity_score)}</td></tr>
      </tbody></table>
      <h2>Análise IA</h2><p>${data.comparacao_ia}</p>
      <script>window.print();</script></body></html>`;
    const win = window.open('', '_blank');
    win?.document.write(html);
    win?.document.close();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-sky-500/30 bg-zinc-950 shadow-2xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-zinc-800 bg-zinc-950/95 px-4 py-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-sky-200">Comparar municípios</h2>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 p-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-zinc-700 bg-zinc-900/60 p-3">
              <p className="text-[10px] uppercase text-zinc-500">Município A</p>
              <p className="text-sm font-semibold text-zinc-100">{nomeA}</p>
            </div>
            <div>
              <label className="mb-1 block text-[10px] uppercase text-zinc-500">Município B</label>
              <select
                value={codigoB}
                onChange={(e) => setCodigoB(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-2 text-sm text-zinc-100"
              >
                {municipalities
                  .filter((m) => m.codigo_ibge !== codigoA)
                  .map((m) => (
                    <option key={m.codigo_ibge} value={m.codigo_ibge}>
                      {m.nome} {m.uf ? `(${m.uf})` : ''}
                    </option>
                  ))}
              </select>
            </div>
          </div>

          {loading && (
            <RotatingLoader
              messages={['Comparando indicadores territoriais…', 'Gerando análise comparativa IA…', 'Montando radar sobreposto…']}
              className="text-sky-200"
            />
          )}

          {error && <p className="rounded-lg border border-rose-800 bg-rose-950/40 px-3 py-2 text-xs text-rose-200">{error}</p>}

          {data && !loading && (
            <>
              <div className="overflow-x-auto rounded-lg border border-zinc-800">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-zinc-800 text-left text-zinc-500">
                      <th className="px-3 py-2">Indicador</th>
                      <th className="px-3 py-2">{nomeA}</th>
                      <th className="px-3 py-2">{nomeB}</th>
                    </tr>
                  </thead>
                  <tbody className="text-zinc-200">
                    {[
                      ['Score', 'score_sinidu'],
                      ['IVC médio', 'media_ivc'],
                      ['IRI médio', 'media_iri'],
                      ['CAPAG', 'nota_capag'],
                      ['Alertas ativos', 'alertas_ativos'],
                      ['Maturidade', 'maturity_score'],
                    ].map(([label, key]) => (
                      <tr key={key} className="border-b border-zinc-900">
                        <td className="px-3 py-2">
                          {label === 'Score' ? <TermTooltip term="Score" /> : label === 'IVC médio' ? <TermTooltip term="IVC" label="IVC médio" /> : label === 'IRI médio' ? <TermTooltip term="IRI" label="IRI médio" /> : label === 'CAPAG' ? <TermTooltip term="CAPAG" /> : label}
                        </td>
                        <td className="px-3 py-2">{str((data.municipio_a as Record<string, unknown>)[key])}</td>
                        <td className="px-3 py-2">{str((data.municipio_b as Record<string, unknown>)[key])}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="h-64 rounded-lg border border-zinc-800 bg-zinc-900/40 p-2">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#334155" />
                    <PolarAngleAxis dataKey="axis" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                    <PolarRadiusAxis tick={{ fill: '#64748b', fontSize: 9 }} />
                    <Radar name={nomeA} dataKey="a" stroke="#059669" fill="#059669" fillOpacity={0.25} />
                    <Radar name={nomeB} dataKey="b" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} />
                    <Legend />
                  </RadarChart>
                </ResponsiveContainer>
              </div>

              <div className="rounded-lg border border-indigo-500/25 bg-indigo-950/30 px-3 py-2 text-xs leading-relaxed text-indigo-100">
                {data.comparacao_ia}
              </div>

              <button
                type="button"
                onClick={exportPdf}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-600 bg-zinc-900 px-3 py-2 text-xs font-semibold text-zinc-200 hover:bg-zinc-800"
              >
                <FileDown className="h-4 w-4" />
                Exportar comparação como PDF
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
