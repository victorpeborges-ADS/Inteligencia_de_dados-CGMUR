'use client';

import { useState } from 'react';
import { api, FloodRiskPrediction } from '@/utils/api';
import { Brain, Loader2, AlertTriangle } from 'lucide-react';

interface PredictiveAnalysisProps {
  codigoIbge?: string;
  municipioNome?: string;
  municipioLoaded?: boolean;
  onPredict: (geojson: unknown) => void;
  onClear: () => void;
}

function riskColor(level: string) {
  if (level === 'MUITO_ALTO') return 'text-rose-300';
  if (level === 'ALTO') return 'text-orange-300';
  if (level === 'MEDIO') return 'text-amber-300';
  return 'text-emerald-300';
}

function gaugeColor(prob: number) {
  if (prob >= 0.75) return '#f43f5e';
  if (prob >= 0.55) return '#f97316';
  if (prob >= 0.35) return '#fbbf24';
  return '#34d399';
}

export default function PredictiveAnalysis({
  codigoIbge,
  municipioNome,
  municipioLoaded,
  onPredict,
  onClear,
}: PredictiveAnalysisProps) {
  const [precip24, setPrecip24] = useState(80);
  const [precip48, setPrecip48] = useState(120);
  const [precip72, setPrecip72] = useState(150);
  const [precip7d, setPrecip7d] = useState(280);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FloodRiskPrediction | null>(null);

  const ready = Boolean(codigoIbge && municipioLoaded !== false);

  const handlePredict = async () => {
    if (!codigoIbge || !ready) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.predictFloodRisk(codigoIbge, precip24, precip48, precip72, precip7d);
      setResult(data);
      if (data.flood_geojson?.features?.length) {
        onPredict(data.flood_geojson);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Erro na predição';
      if (msg.includes('não treinado') || msg.includes('503')) {
        try {
          await api.bootstrapFloodModels();
          const data = await api.predictFloodRisk(codigoIbge, precip24, precip48, precip72, precip7d);
          setResult(data);
          if (data.flood_geojson?.features?.length) onPredict(data.flood_geojson);
          return;
        } catch (retryErr) {
          setError(retryErr instanceof Error ? retryErr.message : msg);
        }
      } else {
        setError(msg);
      }
      setResult(null);
      onClear();
    } finally {
      setLoading(false);
    }
  };

  const probPct = result ? Math.round(result.risk_probability * 100) : 0;
  const arc = result ? result.risk_probability * 283 : 0;
  const isSynthetic = result?.model_kind === 'baseline_synthetic' || result?.production_ready === false;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h4 className="flex items-center gap-1.5 text-sm font-extrabold text-zinc-200">
          <Brain size={16} className="text-violet-400" /> Análise Preditiva de Alagamento
        </h4>
        <p className="mt-1 text-[11px] text-zinc-400">
          Inferência experimental com precipitação + terreno para {municipioNome || 'o município selecionado'}.
          O Monitor operacional só usa modelo com lastro observacional (`full`).
        </p>
      </div>

      {!ready && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 p-3 text-[10px] text-amber-100">
          Aguarde a integração territorial do município ou selecione uma cidade já carregada no banco.
        </div>
      )}

      {ready && (
        <p className="rounded-lg border border-amber-500/25 bg-amber-950/15 px-3 py-2 text-[10px] text-amber-100/90">
          Artefatos atuais são em geral <strong>baseline sintético</strong> — score experimental, não probabilidade
          calibrada. O Monitor usa curva heurística de chuva até existir modelo `full` (Fase 21).
        </p>
      )}

      <div className="grid grid-cols-1 gap-3">
        {[
          { label: 'Precipitação 24h', value: precip24, set: setPrecip24, max: 200 },
          { label: 'Precipitação 48h', value: precip48, set: setPrecip48, max: 300 },
          { label: 'Precipitação 72h', value: precip72, set: setPrecip72, max: 400 },
          { label: 'Precipitação 7d (antecedente)', value: precip7d, set: setPrecip7d, max: 800 },
        ].map((slider) => (
          <div key={slider.label}>
            <div className="mb-1 flex justify-between text-xs text-zinc-300">
              <span>{slider.label}</span>
              <span className="font-bold text-violet-300">{slider.value} mm</span>
            </div>
            <input
              type="range"
              min={0}
              max={slider.max}
              step={5}
              value={slider.value}
              disabled={!ready}
              onChange={(e) => slider.set(Number(e.target.value))}
              className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-zinc-800 accent-violet-500 disabled:opacity-40"
            />
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={handlePredict}
        disabled={loading || !ready}
        className="flex items-center justify-center gap-2 rounded-xl bg-violet-600 py-3 text-xs font-bold uppercase tracking-wider text-white hover:bg-violet-500 disabled:opacity-50"
      >
        {loading ? <Loader2 size={14} className="animate-spin" /> : <Brain size={14} />}
        {loading ? 'Calculando…' : 'Executar predição ML'}
      </button>

      {error && (
        <p className="rounded-lg border border-rose-500/40 bg-rose-950/30 px-3 py-2 text-[10px] text-rose-200">
          <AlertTriangle size={12} className="mr-1 inline" />
          {error}
        </p>
      )}

      {result && (
        <div className="rounded-xl border border-violet-500/30 bg-violet-950/20 p-4">
          <div className="flex items-start gap-4">
            <svg width="80" height="48" viewBox="0 0 100 48" className="shrink-0">
              <path d="M10,40 A40,40 0 0,1 90,40" fill="none" stroke="#3f3f46" strokeWidth="8" />
              <path
                d="M10,40 A40,40 0 0,1 90,40"
                fill="none"
                stroke={gaugeColor(result.risk_probability)}
                strokeWidth="8"
                strokeDasharray={`${arc} 283`}
              />
            </svg>
            <div>
              <p className={`text-2xl font-black ${riskColor(result.risk_level)}`}>{probPct}%</p>
              {result.uncertainty && (
                <p className="text-[10px] font-mono text-zinc-500">
                  IC≈{Math.round((result.uncertainty.confidence_level ?? 0.9) * 100)}%:{' '}
                  {Math.round(result.uncertainty.ci_low * 100)}–
                  {Math.round(result.uncertainty.ci_high * 100)}%
                </p>
              )}
              <p className="text-[10px] uppercase tracking-wide text-zinc-400">
                {result.risk_level.replace('_', ' ')} ·{' '}
                {isSynthetic ? 'score experimental' : `confiança ${result.confidence}`}
              </p>
              <span className="mt-1 inline-block rounded bg-teal-500/15 px-1.5 py-0.5 text-[8px] font-bold uppercase text-teal-200">
                {isSynthetic ? 'Sintético · Estimado' : 'ML full · Derivado'}
              </span>
              {isSynthetic && (
                <span className="mt-1 ml-1 inline-block rounded bg-amber-500/15 px-1.5 py-0.5 text-[8px] font-bold uppercase text-amber-300">
                  Não é probabilidade calibrada
                </span>
              )}
              {result.model_auc_roc != null && (
                <span className="mt-1 ml-1 inline-block rounded bg-emerald-500/15 px-1.5 py-0.5 text-[8px] font-bold uppercase text-emerald-300">
                  AUC {result.model_auc_roc.toFixed(2)}
                </span>
              )}
            </div>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-[10px]">
            <div className="rounded-lg border border-zinc-700/60 bg-zinc-950/40 px-2 py-1.5">
              <p className="text-[9px] uppercase tracking-wider text-zinc-500">Limiar 24h</p>
              <p className="font-bold text-zinc-200">{result.threshold_mm_24h} mm</p>
            </div>
            <div className="rounded-lg border border-zinc-700/60 bg-zinc-950/40 px-2 py-1.5">
              <p className="text-[9px] uppercase tracking-wider text-zinc-500">vs. cenário</p>
              <p
                className={`font-bold ${
                  (result.mm_acima_limiar ?? 0) > 0 ? 'text-rose-300' : 'text-emerald-300'
                }`}
              >
                {result.mm_acima_limiar == null
                  ? '—'
                  : result.mm_acima_limiar > 0
                    ? `+${result.mm_acima_limiar} mm`
                    : `${result.mm_acima_limiar} mm`}
              </p>
            </div>
          </div>
          {result.horizons && result.horizons.length > 0 && (
            <div className="mt-2">
              <p className="mb-1 text-[9px] font-bold uppercase tracking-wider text-zinc-500">
                Horizonte D+1 · D+2 · D+3
              </p>
              <div className="grid grid-cols-3 gap-1.5">
                {result.horizons.map((h) => (
                  <div
                    key={h.horizon}
                    className="rounded-lg border border-zinc-700/50 bg-zinc-950/50 px-2 py-1.5 text-center"
                  >
                    <p className="text-[9px] font-bold uppercase text-zinc-500">{h.horizon}</p>
                    <p className="text-sm font-black text-violet-200">
                      {Math.round(h.risk_probability * 100)}%
                    </p>
                    {h.ci_low != null && h.ci_high != null && (
                      <p className="text-[8px] font-mono text-zinc-600">
                        {Math.round(h.ci_low * 100)}–{Math.round(h.ci_high * 100)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          {result.impact?.disponivel && (
            <div className="mt-2 rounded-lg border border-amber-500/25 bg-amber-950/15 p-2.5">
              <p className="mb-1 text-[9px] font-bold uppercase tracking-wider text-amber-200/90">
                Impacto estimado
              </p>
              <p className="text-[10px] leading-snug text-zinc-300">
                {result.impact.narrativa ||
                  `${result.impact.n_bairros_prioritarios ?? 0} bairros prioritários`}
              </p>
              <div className="mt-1.5 flex flex-wrap gap-2 text-[9px] text-zinc-500">
                {result.impact.populacao_exposta_estimada != null && (
                  <span>
                    Pop. exposta ~{' '}
                    <strong className="text-amber-200">
                      {result.impact.populacao_exposta_estimada.toLocaleString('pt-BR')}
                    </strong>
                    {result.impact.pct_populacao_exposta != null
                      ? ` (${result.impact.pct_populacao_exposta}%)`
                      : ''}
                  </span>
                )}
                {result.impact.capag_nota && (
                  <span>
                    CAPAG <strong className="text-zinc-300">{result.impact.capag_nota}</strong>
                  </span>
                )}
                {result.impact.porte && (
                  <span>
                    Porte <strong className="text-zinc-300">{result.impact.porte}</strong>
                  </span>
                )}
              </div>
              {result.impact.medidas_cabiveis && result.impact.medidas_cabiveis.length > 0 && (
                <ul className="mt-2 space-y-1 border-t border-zinc-800/80 pt-2">
                  {result.impact.medidas_cabiveis.slice(0, 3).map((m) => (
                    <li key={m.id || m.titulo} className="text-[10px] text-zinc-400">
                      <span className="font-semibold text-zinc-200">{m.titulo}</span>
                      {m.custo ? (
                        <span className="ml-1 text-[9px] text-zinc-500">· {m.custo}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {result.explanation?.disponivel && result.explanation.domains?.length > 0 && (
            <div className="mt-2">
              <p className="mb-1 text-[9px] font-bold uppercase tracking-wider text-zinc-500">
                Contribuição por domínio
              </p>
              {result.explanation.narrativa && (
                <p className="mb-1.5 text-[10px] leading-snug text-zinc-400">
                  {result.explanation.narrativa}
                </p>
              )}
              <ul className="space-y-1">
                {result.explanation.domains.slice(0, 5).map((d) => (
                  <li key={d.id} className="text-[10px] text-zinc-400">
                    <div className="mb-0.5 flex justify-between gap-2">
                      <span className="text-zinc-300">{d.label}</span>
                      <span className="font-mono text-violet-200">{d.contribution_pct.toFixed(0)}%</span>
                    </div>
                    <div className="h-1 overflow-hidden rounded-full bg-zinc-800">
                      <div
                        className="h-full rounded-full bg-violet-500/70"
                        style={{ width: `${Math.min(100, Math.max(2, d.contribution_pct))}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.top_features && result.top_features.length > 0 && (
            <div className="mt-2">
              <p className="mb-1 text-[9px] font-bold uppercase tracking-wider text-zinc-500">
                Variáveis mais influentes
              </p>
              <ul className="space-y-0.5">
                {result.top_features.map((f) => (
                  <li key={f.feature} className="flex justify-between text-[10px] text-zinc-400">
                    <span className="font-mono text-violet-200/90">{f.feature}</span>
                    <span>{(f.importance * 100).toFixed(0)}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="mt-2 text-[9px] leading-relaxed text-zinc-500">{result.disclaimer}</p>
          {result.critical_neighborhoods?.length > 0 && (
            <ul className="mt-3 space-y-1">
              {result.critical_neighborhoods.slice(0, 5).map((b) => (
                <li key={b.bairro_id} className="flex justify-between text-[10px] text-zinc-300">
                  <span>{b.bairro_nome}</span>
                  <span className="font-mono text-violet-300">{(b.risk_probability * 100).toFixed(0)}%</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
