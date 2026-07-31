'use client';

import { useEffect, useState } from 'react';
import { api, FloodRiskPrediction } from '@/utils/api';
import { Brain, Loader2, AlertTriangle } from 'lucide-react';

interface PredictiveAnalysisProps {
  codigoIbge?: string;
  municipioNome?: string;
  municipioLoaded?: boolean;
  onPredict: (geojson: unknown) => void;
  onClear: () => void;
  /** Quando embutido na aba Chuva: sincroniza com o volume do cenário físico. */
  embedded?: boolean;
  precipEventMm?: number;
  antecedentMm?: number;
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

function deriveHorizons(eventMm: number, antecedentMm: number) {
  const p24 = Math.max(0, Math.round(eventMm));
  const p48 = Math.max(p24, Math.round(eventMm * 1.35 + antecedentMm * 0.15));
  const p72 = Math.max(p48, Math.round(eventMm * 1.55 + antecedentMm * 0.25));
  const p7d = Math.max(p72, Math.round(antecedentMm + eventMm));
  return { p24, p48, p72, p7d };
}

export default function PredictiveAnalysis({
  codigoIbge,
  municipioNome,
  municipioLoaded,
  onPredict,
  onClear,
  embedded = false,
  precipEventMm = 80,
  antecedentMm = 0,
}: PredictiveAnalysisProps) {
  const derived = deriveHorizons(precipEventMm, antecedentMm);
  const [precip24, setPrecip24] = useState(derived.p24);
  const [precip48, setPrecip48] = useState(derived.p48);
  const [precip72, setPrecip72] = useState(derived.p72);
  const [precip7d, setPrecip7d] = useState(derived.p7d);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FloodRiskPrediction | null>(null);

  const ready = Boolean(codigoIbge && municipioLoaded !== false);

  useEffect(() => {
    if (!embedded) return;
    const next = deriveHorizons(precipEventMm, antecedentMm);
    setPrecip24(next.p24);
    setPrecip48(next.p48);
    setPrecip72(next.p72);
    setPrecip7d(next.p7d);
  }, [embedded, precipEventMm, antecedentMm]);

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
    <div className={`flex flex-col gap-3 ${embedded ? '' : 'gap-4'}`}>
      <div>
        <h4 className="flex items-center gap-1.5 text-sm font-extrabold text-zinc-200">
          <Brain size={16} className="text-violet-400" />
          {embedded ? 'Score multi-horizonte (mesmo evento)' : 'Análise Preditiva de Alagamento'}
        </h4>
        <p className="mt-1 text-[11px] text-zinc-400">
          {embedded
            ? `Horizontes 24h–7d derivados do volume do cenário (${precip24} mm no evento) + solo antecedente. Complementa a mancha DEM — não a substitui.`
            : `Inferência experimental com precipitação + terreno para ${municipioNome || 'o município selecionado'}.`}
        </p>
      </div>

      {!ready && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 p-3 text-[10px] text-amber-100">
          Aguarde a integração territorial do município ou selecione uma cidade já carregada no banco.
        </div>
      )}

      {ready && (
        <p className="rounded-lg border border-amber-500/25 bg-amber-950/15 px-3 py-2 text-[10px] text-amber-100/90">
          Artefatos atuais são em geral <strong>baseline sintético</strong> — score experimental.
          O Monitor operacional só usa modelo com lastro observacional (`full`).
        </p>
      )}

      {embedded ? (
        <div className="grid grid-cols-2 gap-2 text-[10px] sm:grid-cols-4">
          {[
            { label: '24h', value: precip24 },
            { label: '48h', value: precip48 },
            { label: '72h', value: precip72 },
            { label: '7d', value: precip7d },
          ].map((h) => (
            <div key={h.label} className="rounded-lg border border-zinc-800 bg-zinc-950/50 px-2 py-1.5">
              <p className="text-[9px] uppercase tracking-wider text-zinc-500">{h.label}</p>
              <p className="font-bold text-violet-200">{h.value} mm</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {[
            { label: 'Precipitação 24h', value: precip24, set: setPrecip24, max: 350 },
            { label: 'Precipitação 48h', value: precip48, set: setPrecip48, max: 450 },
            { label: 'Precipitação 72h', value: precip72, set: setPrecip72, max: 550 },
            { label: 'Precipitação 7d (antecedente)', value: precip7d, set: setPrecip7d, max: 900 },
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
      )}

      <button
        type="button"
        onClick={handlePredict}
        disabled={loading || !ready}
        className="flex items-center justify-center gap-2 rounded-xl bg-violet-600 py-2.5 text-xs font-bold uppercase tracking-wider text-white hover:bg-violet-500 disabled:opacity-50"
      >
        {loading ? <Loader2 size={14} className="animate-spin" /> : <Brain size={14} />}
        {loading ? 'Calculando…' : embedded ? 'Calcular score do evento' : 'Executar predição ML'}
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
                  </div>
                ))}
              </div>
            </div>
          )}
          {result.impact?.disponivel && (
            <div className="mt-2 rounded-lg border border-amber-500/25 bg-amber-950/15 p-2.5">
              <p className="mb-1 text-[9px] font-bold uppercase tracking-wider text-amber-200/90">
                Impacto estimado (ML)
              </p>
              <p className="text-[11px] text-zinc-200">
                {(result.impact.populacao_exposta_estimada ?? 0).toLocaleString('pt-BR')} pessoas ·{' '}
                {result.impact.n_bairros_prioritarios ?? 0} bairros prioritários
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
