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
import {
  api,
  type MonitoringCompareResult,
  type MunicipalRankResponse,
} from '@/utils/api';
import { X, FileDown, ArrowLeftRight, AlertTriangle, ListOrdered } from 'lucide-react';
import TermTooltip from '@/components/UI/TermTooltip';
import RotatingLoader from '@/components/UI/RotatingLoader';
import { EmptyState } from '@/design-system';
import {
  buildCompareBullets,
  buildComparePresets,
  COMPARE_METRICS,
  computeMetricDelta,
  formatCompareValue,
  num,
} from '@/utils/compareMunicipalities';

type CompareModalProps = {
  open: boolean;
  onClose: () => void;
  codigoA: string;
  nomeA: string;
  municipalities: Array<{ codigo_ibge: string; nome: string; uf?: string; populacao?: number }>;
};

type TabId = 'par' | 'ranking';

const RANK_CRITERIOS: Array<{ id: string; label: string }> = [
  { id: 'score_sinidu', label: 'Score Sinidu' },
  { id: 'media_ivc', label: 'IVC médio' },
  { id: 'media_iri', label: 'IRI médio' },
  { id: 'media_adaptacao', label: 'Adaptação' },
  { id: 'nota_capag', label: 'CAPAG' },
  { id: 'populacao', label: 'População' },
];

function formatRankValor(valor: number | string | null | undefined, format: string): string {
  if (valor == null || valor === '') return '—';
  if (format === 'text') return String(valor);
  if (format === 'percent') {
    const n = typeof valor === 'number' ? valor : Number(valor);
    if (Number.isNaN(n)) return String(valor);
    return n <= 1 ? `${Math.round(n * 100)}%` : `${Math.round(n)}%`;
  }
  const n = typeof valor === 'number' ? valor : Number(valor);
  if (Number.isNaN(n)) return String(valor);
  return Math.round(n).toLocaleString('pt-BR');
}

export default function CompareModal({ open, onClose, codigoA, nomeA, municipalities }: CompareModalProps) {
  const [tab, setTab] = useState<TabId>('par');
  const [codigoB, setCodigoB] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<MonitoringCompareResult | null>(null);

  const ufA = municipalities.find((m) => m.codigo_ibge === codigoA)?.uf ?? '';
  const [rankCriterio, setRankCriterio] = useState('score_sinidu');
  const [rankUf, setRankUf] = useState(ufA);
  const [rankLoading, setRankLoading] = useState(false);
  const [rankError, setRankError] = useState<string | null>(null);
  const [rankData, setRankData] = useState<MunicipalRankResponse | null>(null);

  const presets = useMemo(
    () => buildComparePresets(codigoA, municipalities),
    [codigoA, municipalities],
  );

  useEffect(() => {
    if (!open) return;
    const defaultPreset = presets[0];
    setCodigoB(defaultPreset?.codigoIbge ?? '');
    setData(null);
    setError(null);
    setTab('par');
    setRankUf(ufA);
    setRankData(null);
    setRankError(null);
  }, [open, codigoA, presets, ufA]);

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
    if (open && tab === 'par' && codigoB && codigoB !== codigoA) {
      runCompare().catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [codigoB, open, tab]);

  const runRank = async () => {
    setRankLoading(true);
    setRankError(null);
    try {
      const sameUf = municipalities
        .filter((m) => !rankUf || m.uf === rankUf)
        .map((m) => m.codigo_ibge)
        .slice(0, 25);
      const result = await api.rankMunicipalities({
        criterio: rankCriterio,
        uf: rankUf || undefined,
        codigos: sameUf.length >= 2 ? sameUf : undefined,
        limit: 15,
      });
      setRankData(result);
    } catch (e) {
      setRankError(e instanceof Error ? e.message : 'Falha no ranking');
      setRankData(null);
    } finally {
      setRankLoading(false);
    }
  };

  useEffect(() => {
    if (open && tab === 'ranking') {
      runRank().catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, tab, rankCriterio, rankUf]);

  const municipioB = municipalities.find((m) => m.codigo_ibge === codigoB);
  const nomeB = municipioB?.nome ?? codigoB;

  const radarData = useMemo(() => {
    if (!data) return [];
    const a = data.municipio_a as Record<string, unknown>;
    const b = data.municipio_b as Record<string, unknown>;
    return [
      { axis: 'Score', a: num(a.score_sinidu) ?? 0, b: num(b.score_sinidu) ?? 0 },
      { axis: 'IVC', a: (num(a.media_ivc) ?? 0) * 100, b: (num(b.media_ivc) ?? 0) * 100 },
      { axis: 'IRI', a: (num(a.media_iri) ?? 0) * 100, b: (num(b.media_iri) ?? 0) * 100 },
      { axis: 'Maturidade', a: num(a.maturity_score) ?? 0, b: num(b.maturity_score) ?? 0 },
      { axis: 'Alertas', a: num(a.alertas_ativos) ?? 0, b: num(b.alertas_ativos) ?? 0 },
    ];
  }, [data]);

  const bullets = useMemo(() => {
    if (!data) return [];
    return buildCompareBullets(
      nomeA,
      nomeB,
      data.municipio_a as Record<string, unknown>,
      data.municipio_b as Record<string, unknown>,
    );
  }, [data, nomeA, nomeB]);

  const maisCriticoNome =
    data?.mais_critico_ibge === codigoA ? nomeA : data?.mais_critico_ibge === codigoB ? nomeB : null;

  const ufs = useMemo(
    () =>
      Array.from(new Set(municipalities.map((m) => m.uf).filter(Boolean) as string[])).sort(),
    [municipalities],
  );

  const exportPdf = () => {
    if (!data) return;
    const a = data.municipio_a as Record<string, unknown>;
    const b = data.municipio_b as Record<string, unknown>;
    const rows = COMPARE_METRICS.map(
      (m) =>
        `<tr><td>${m.label}</td><td>${formatCompareValue(a[m.key], m.format)}</td><td>${formatCompareValue(b[m.key], m.format)}</td></tr>`,
    ).join('');
    const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"/>
      <title>Comparação ${nomeA} × ${nomeB}</title>
      <style>body{font-family:Arial,sans-serif;margin:40px;color:#111}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:8px;font-size:13px}th{background:#e0e7ff}</style>
      </head><body>
      <h1>Comparação Municipal Sinidu+Clima</h1>
      ${maisCriticoNome ? `<p><strong>Mais crítico:</strong> ${maisCriticoNome}</p>` : ''}
      <table><thead><tr><th>Indicador</th><th>${nomeA}</th><th>${nomeB}</th></tr></thead>
      <tbody>${rows}</tbody></table>
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
        <div className="sticky top-0 z-10 border-b border-zinc-800 bg-zinc-950/95">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-2">
              <ArrowLeftRight size={16} className="text-sky-300" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-sky-200">Comparador territorial</h2>
            </div>
            <button type="button" onClick={onClose} className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100">
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="flex gap-1 px-4 pb-2">
            <button
              type="button"
              onClick={() => setTab('par')}
              className={`rounded-lg px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide ${
                tab === 'par' ? 'bg-sky-500/20 text-sky-100' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              Comparar par
            </button>
            <button
              type="button"
              onClick={() => setTab('ranking')}
              className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide ${
                tab === 'ranking' ? 'bg-sky-500/20 text-sky-100' : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              <ListOrdered size={12} />
              Ranking
            </button>
          </div>
        </div>

        <div className="space-y-4 p-4">
          {tab === 'ranking' ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-[10px] uppercase text-zinc-500">Critério</label>
                  <select
                    value={rankCriterio}
                    onChange={(e) => setRankCriterio(e.target.value)}
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-2 text-sm text-zinc-100"
                  >
                    {RANK_CRITERIOS.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-[10px] uppercase text-zinc-500">UF</label>
                  <select
                    value={rankUf}
                    onChange={(e) => setRankUf(e.target.value)}
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-2 text-sm text-zinc-100"
                  >
                    <option value="">Todas (lista carregada)</option>
                    {ufs.map((uf) => (
                      <option key={uf} value={uf}>
                        {uf}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {rankLoading && (
                <RotatingLoader
                  messages={['Ordenando municípios…', 'Calculando critérios Sinidu+Clima…']}
                  className="text-sky-200"
                />
              )}
              {rankError && (
                <p className="rounded-lg border border-rose-800 bg-rose-950/40 px-3 py-2 text-xs text-rose-200">
                  {rankError}
                </p>
              )}
              {rankData && !rankLoading && (
                <>
                  <p className="text-[10px] text-zinc-500">
                    {rankData.criterio_label}
                    {rankData.uf ? ` · UF ${rankData.uf}` : ''} · {rankData.total} municípios
                    {rankData.higher_is_worse ? ' · maior = mais crítico' : ' · maior = melhor/maior porte'}
                  </p>
                  <div className="overflow-x-auto rounded-lg border border-zinc-800">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-zinc-800 text-left text-zinc-500">
                          <th className="px-3 py-2">#</th>
                          <th className="px-3 py-2">Município</th>
                          <th className="px-3 py-2">Valor</th>
                          <th className="px-3 py-2">Score</th>
                          <th className="px-3 py-2">CAPAG</th>
                        </tr>
                      </thead>
                      <tbody className="text-zinc-200">
                        {rankData.items.map((row) => {
                          const highlight = row.codigo_ibge === codigoA;
                          return (
                            <tr
                              key={row.codigo_ibge}
                              className={`border-b border-zinc-900 ${highlight ? 'bg-sky-500/10' : ''}`}
                            >
                              <td className="px-3 py-2 font-mono text-zinc-500">{row.posicao}</td>
                              <td className="px-3 py-2">
                                {row.nome}
                                <span className="ml-1 text-[9px] text-zinc-500">{row.uf}</span>
                                {highlight && (
                                  <span className="ml-1 text-[8px] font-bold uppercase text-sky-300">você</span>
                                )}
                              </td>
                              <td className="px-3 py-2 font-semibold">
                                {formatRankValor(row.valor, rankData.format)}
                              </td>
                              <td className="px-3 py-2 text-zinc-400">{row.score_sinidu ?? '—'}</td>
                              <td className="px-3 py-2 text-zinc-400">{row.nota_capag ?? '—'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  {rankData.nota && (
                    <p className="text-[9px] leading-relaxed text-zinc-500">{rankData.nota}</p>
                  )}
                </>
              )}
            </>
          ) : (
            <>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-3">
              <p className="text-[10px] uppercase text-zinc-500">Município A (base)</p>
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
                      {m.populacao ? ` · ${m.populacao.toLocaleString('pt-BR')} hab.` : ''}
                    </option>
                  ))}
              </select>
            </div>
          </div>

          {presets.length > 0 && (
            <div>
              <p className="mb-2 text-[9px] font-extrabold uppercase tracking-wider text-zinc-500">Pares sugeridos</p>
              <div className="flex flex-wrap gap-2">
                {presets.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => setCodigoB(preset.codigoIbge)}
                    className={`rounded-lg border px-3 py-1.5 text-left transition ${
                      codigoB === preset.codigoIbge
                        ? 'border-sky-500/50 bg-sky-500/15 text-sky-100'
                        : 'border-zinc-700 bg-zinc-900/60 text-zinc-300 hover:border-zinc-600'
                    }`}
                  >
                    <span className="block text-[10px] font-bold uppercase">{preset.label}</span>
                    <span className="block text-[9px] text-zinc-500">{preset.hint}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {!codigoB && (
            <EmptyState
              icon={ArrowLeftRight}
              compact
              title="Selecione um município para comparar"
              description="Use um par sugerido ou escolha manualmente no seletor."
            />
          )}

          {loading && (
            <RotatingLoader
              messages={['Comparando indicadores territoriais…', 'Gerando análise comparativa IA…', 'Montando radar sobreposto…']}
              className="text-sky-200"
            />
          )}

          {error && <p className="rounded-lg border border-rose-800 bg-rose-950/40 px-3 py-2 text-xs text-rose-200">{error}</p>}

          {data && !loading && (
            <>
              {maisCriticoNome && (
                <div className="flex items-start gap-2 rounded-lg border border-rose-500/35 bg-rose-950/25 px-3 py-2.5">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-rose-300" />
                  <div>
                    <p className="text-[10px] font-extrabold uppercase tracking-wide text-rose-200">
                      Veredicto territorial
                    </p>
                    <p className="mt-0.5 text-[11px] text-zinc-300">
                      <strong className="text-rose-100">{maisCriticoNome}</strong> concentra maior criticidade no par analisado
                      (score, IVC/IRI e alertas integrados).
                    </p>
                  </div>
                </div>
              )}

              {bullets.length > 0 && (
                <ul className="space-y-1 rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2">
                  {bullets.map((item) => (
                    <li key={item} className="flex gap-2 text-[10px] text-zinc-400">
                      <span className="text-sky-400">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              )}

              <div className="overflow-x-auto rounded-lg border border-zinc-800">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-zinc-800 text-left text-zinc-500">
                      <th className="px-3 py-2">Indicador</th>
                      <th className="px-3 py-2">{nomeA}</th>
                      <th className="px-3 py-2">{nomeB}</th>
                      <th className="px-3 py-2">Δ / melhor</th>
                    </tr>
                  </thead>
                  <tbody className="text-zinc-200">
                    {COMPARE_METRICS.map((metric) => {
                      const a = data.municipio_a as Record<string, unknown>;
                      const b = data.municipio_b as Record<string, unknown>;
                      const aVal =
                        metric.key === 'populacao'
                          ? municipalities.find((m) => m.codigo_ibge === codigoA)?.populacao ?? a.populacao
                          : a[metric.key];
                      const bVal =
                        metric.key === 'populacao'
                          ? municipioB?.populacao ?? b.populacao
                          : b[metric.key];
                      const delta = computeMetricDelta(aVal, bVal, metric.higherIsWorse, metric.format);

                      const labelNode =
                        metric.label === 'Score' ? (
                          <TermTooltip term="Score" />
                        ) : metric.label === 'IVC médio' ? (
                          <TermTooltip term="IVC" label="IVC médio" />
                        ) : metric.label === 'IRI médio' ? (
                          <TermTooltip term="IRI" label="IRI médio" />
                        ) : metric.label === 'CAPAG' ? (
                          <TermTooltip term="CAPAG" />
                        ) : (
                          metric.label
                        );

                      return (
                        <tr key={metric.key} className="border-b border-zinc-900">
                          <td className="px-3 py-2">{labelNode}</td>
                          <td className={`px-3 py-2 ${delta.winner === 'a' ? 'font-bold text-emerald-300' : ''}`}>
                            {formatCompareValue(aVal, metric.format)}
                          </td>
                          <td className={`px-3 py-2 ${delta.winner === 'b' ? 'font-bold text-indigo-300' : ''}`}>
                            {formatCompareValue(bVal, metric.format)}
                          </td>
                          <td className="px-3 py-2 text-[10px] text-zinc-500">
                            {delta.formattedDelta ?? '—'}
                            {delta.winner === 'a' && ' → A'}
                            {delta.winner === 'b' && ' → B'}
                            {delta.winner === 'tie' && ' empate'}
                          </td>
                        </tr>
                      );
                    })}
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
                <p className="mb-1 text-[9px] font-extrabold uppercase tracking-wide text-indigo-300">
                  Análise IA · {data.ai_provider || 'Sinidu+Clima'}
                </p>
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
            </>
          )}
        </div>
      </div>
    </div>
  );
}
