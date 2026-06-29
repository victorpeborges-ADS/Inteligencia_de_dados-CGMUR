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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<FloodRiskPrediction | null>(null);

  const ready = Boolean(codigoIbge && municipioLoaded !== false);

  const handlePredict = async () => {
    if (!codigoIbge || !ready) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.predictFloodRisk(codigoIbge, precip24, precip48, precip72);
      setResult(data);
      if (data.flood_geojson?.features?.length) {
        onPredict(data.flood_geojson);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Erro na predição';
      if (msg.includes('não treinado') || msg.includes('503')) {
        try {
          await api.bootstrapFloodModels();
          const data = await api.predictFloodRisk(codigoIbge, precip24, precip48, precip72);
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

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h4 className="flex items-center gap-1.5 text-sm font-extrabold text-zinc-200">
          <Brain size={16} className="text-violet-400" /> Análise Preditiva de Alagamento
        </h4>
        <p className="mt-1 text-[11px] text-zinc-400">
          Random Forest com precipitação simulada + terreno municipal para {municipioNome || 'o município selecionado'}.
        </p>
      </div>

      {!ready && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 p-3 text-[10px] text-amber-100">
          Aguarde a integração territorial do município ou selecione uma cidade já carregada no banco.
        </div>
      )}

      {ready && (
        <p className="rounded-lg border border-violet-500/20 bg-violet-950/15 px-3 py-2 text-[10px] text-violet-200/90">
          Modelo gerado on-demand se necessário. Municípios prioritários (Recife, Salvador, POA, JP, Londrina) usam
          artefato dedicado; demais recebem baseline calibrado pelo terreno local.
        </p>
      )}

      <div className="grid grid-cols-1 gap-3">
        {[
          { label: 'Precipitação 24h', value: precip24, set: setPrecip24, max: 200 },
          { label: 'Precipitação 48h', value: precip48, set: setPrecip48, max: 300 },
          { label: 'Precipitação 72h', value: precip72, set: setPrecip72, max: 400 },
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
              <p className="text-[10px] uppercase tracking-wide text-zinc-400">
                {result.risk_level.replace('_', ' ')} · confiança {result.confidence}
              </p>
              {result.model_kind === 'baseline_synthetic' && (
                <span className="mt-1 inline-block rounded bg-amber-500/15 px-1.5 py-0.5 text-[8px] font-bold uppercase text-amber-300">
                  Baseline on-demand
                </span>
              )}
            </div>
          </div>
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
