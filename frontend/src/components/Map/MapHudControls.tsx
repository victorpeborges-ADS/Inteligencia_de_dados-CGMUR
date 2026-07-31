'use client';

import { useMemo } from 'react';
import { Compass, Ruler } from 'lucide-react';
import type { LayerOption } from '@/config/platformTabs';

/** Entradas de legenda por camada ativa (17f.8). */
const LAYER_LEGEND: Record<string, { title: string; items: { color: string; label: string }[] }> = {
  vulnerabilidade: {
    title: 'Vulnerabilidade (IVC)',
    items: [
      { color: '#fde047', label: 'Baixa' },
      { color: '#f97316', label: 'Média' },
      { color: '#7f1d1d', label: 'Alta' },
    ],
  },
  inundacao: {
    title: 'Risco de inundação (IRI)',
    items: [
      { color: '#075985', label: 'Baixo' },
      { color: '#0284c7', label: 'Médio' },
      { color: '#7dd3fc', label: 'Alto' },
    ],
  },
  risco_consolidado: {
    title: 'Risco consolidado',
    items: [
      { color: '#22c55e', label: 'Verde' },
      { color: '#eab308', label: 'Amarelo' },
      { color: '#ea580c', label: 'Laranja' },
      { color: '#dc2626', label: 'Vermelho' },
    ],
  },
  alertas: {
    title: 'Alertas',
    items: [
      { color: '#eab308', label: 'Moderado' },
      { color: '#f97316', label: 'Alto' },
      { color: '#f43f5e', label: 'Muito alto' },
    ],
  },
  cobertura: {
    title: 'Cobertura do solo',
    items: [
      { color: '#15803d', label: 'Vegetação / parque' },
      { color: '#a1a1aa', label: 'Área construída' },
      { color: '#1e3a8a', label: "Corpo d'água / rios" },
    ],
  },
  socioeconomico: {
    title: 'Socioeconômico',
    items: [
      { color: '#14532d', label: 'Mais favorável' },
      { color: '#facc15', label: 'Intermediário' },
      { color: '#b91c1c', label: 'Mais crítico' },
    ],
  },
};

const SIM_LEGEND = {
  title: 'Simulação ativa',
  items: [
    { color: '#0284c7', label: 'Inundação / profundidade' },
    { color: '#ef4444', label: 'Deslizamento / calor severo' },
    { color: '#fbbf24', label: 'Calor leve–moderado' },
  ],
};

type MapHudControlsProps = {
  bearing: number;
  scaleLabel: string;
  activeLayers: string[];
  layerOptions?: LayerOption[];
  hasSimulation?: boolean;
  showLiveSensors?: boolean;
  showCriticalPois?: boolean;
  showUrbanContext?: boolean;
  onResetNorth?: () => void;
  className?: string;
};

export default function MapHudControls({
  bearing,
  scaleLabel,
  activeLayers,
  layerOptions = [],
  hasSimulation = false,
  showLiveSensors = false,
  showCriticalPois = false,
  showUrbanContext = false,
  onResetNorth,
  className = '',
}: MapHudControlsProps) {
  const legends = useMemo(() => {
    const out: { title: string; items: { color: string; label: string }[] }[] = [];
    for (const id of activeLayers) {
      if (id === 'edificacoes') continue;
      const entry = LAYER_LEGEND[id];
      if (entry) out.push(entry);
      else {
        const opt = layerOptions.find((o) => o.id === id);
        if (opt) {
          out.push({
            title: opt.label,
            items: [{ color: '#6366f1', label: opt.source.split('·')[0]?.trim() || 'Camada ativa' }],
          });
        }
      }
    }
    if (hasSimulation) out.unshift(SIM_LEGEND);
    if (showUrbanContext) {
      out.unshift({
        title: 'Contexto urbano',
        items: [
          { color: '#38bdf8', label: 'Hidrografia' },
          { color: '#f8fafc', label: 'Vias' },
          { color: '#a8a29e', label: 'Curvas de nível' },
        ],
      });
    }
    if (showCriticalPois) {
      out.unshift({
        title: 'POIs críticos',
        items: [
          { color: '#38bdf8', label: 'Escola (INEP)' },
          { color: '#22c55e', label: 'Saúde (CNES)' },
          { color: '#fbbf24', label: 'Abrigo / apoio' },
          { color: '#a78bfa', label: 'Equipamento' },
        ],
      });
    }
    if (showLiveSensors) {
      out.unshift({
        title: 'Sensores vivos',
        items: [
          { color: '#f43f5e', label: 'CEMADEN crítico' },
          { color: '#f97316', label: 'CEMADEN alto' },
          { color: '#eab308', label: 'Atenção' },
          { color: '#06b6d4', label: 'Estação INMET' },
          { color: '#38bdf8', label: 'Previsão clima' },
        ],
      });
    }
    return out.slice(0, 4);
  }, [
    activeLayers,
    layerOptions,
    hasSimulation,
    showLiveSensors,
    showCriticalPois,
    showUrbanContext,
  ]);

  return (
    <div className={`pointer-events-auto flex flex-col items-end gap-2 ${className}`}>
      <div className="map-ui-chrome flex items-center gap-2 rounded-xl border border-zinc-700/80 bg-zinc-950/95 px-2 py-1.5 shadow-lg backdrop-blur-md">
        <button
          type="button"
          onClick={onResetNorth}
          title="Apontar ao norte"
          className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-700 bg-zinc-900 text-zinc-200 hover:border-teal-500/40 hover:text-teal-200"
          aria-label="Resetar norte"
        >
          <Compass
            size={18}
            style={{ transform: `rotate(${-bearing}deg)`, transition: 'transform 120ms linear' }}
          />
          <span className="absolute -top-0.5 left-1/2 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-rose-500" />
        </button>
        <div className="min-w-[4.5rem] pr-1">
          <p className="text-[8px] font-bold uppercase tracking-wider text-zinc-500">Norte</p>
          <p className="font-mono text-[11px] font-bold text-zinc-200">
            {Math.round(((bearing % 360) + 360) % 360)}°
          </p>
        </div>
        <div className="border-l border-zinc-800 pl-2">
          <p className="flex items-center gap-1 text-[8px] font-bold uppercase tracking-wider text-zinc-500">
            <Ruler size={10} /> Escala
          </p>
          <p className="font-mono text-[11px] font-bold text-zinc-200">{scaleLabel}</p>
        </div>
      </div>

      {legends.length > 0 && (
        <div className="map-ui-chrome max-w-[14rem] rounded-xl border border-zinc-700/80 bg-zinc-950/95 px-3 py-2 shadow-lg backdrop-blur-md">
          <p className="mb-1.5 text-[9px] font-extrabold uppercase tracking-wider text-teal-300">
            Legenda
          </p>
          <div className="max-h-40 space-y-2 overflow-y-auto pr-0.5">
            {legends.map((leg) => (
              <div key={leg.title}>
                <p className="mb-0.5 text-[9px] font-bold text-zinc-400">{leg.title}</p>
                <ul className="space-y-0.5">
                  {leg.items.map((item) => (
                    <li key={`${leg.title}-${item.label}`} className="flex items-center gap-1.5 text-[10px] text-zinc-300">
                      <span
                        className="h-2.5 w-2.5 shrink-0 rounded-sm border border-white/10"
                        style={{ backgroundColor: item.color }}
                      />
                      {item.label}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** Escala aproximada em metros a partir do zoom e latitude (Web Mercator). */
export function metersPerPixel(lat: number, zoom: number): number {
  const rad = (lat * Math.PI) / 180;
  return (156543.03392 * Math.cos(rad)) / 2 ** zoom;
}

export function formatScaleBar(meters: number): string {
  if (meters >= 1000) {
    const km = meters / 1000;
    return km >= 10 ? `${Math.round(km)} km` : `${km.toFixed(1)} km`;
  }
  if (meters >= 100) return `${Math.round(meters / 10) * 10} m`;
  if (meters >= 10) return `${Math.round(meters)} m`;
  return `${Math.max(1, Math.round(meters))} m`;
}

/** Comprimento alvo da barra (~80 px) em metros arredondados. */
export function niceScaleMeters(mPerPx: number, targetPx = 80): { meters: number; label: string } {
  const raw = mPerPx * targetPx;
  const nice = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000];
  let best = nice[0];
  for (const n of nice) {
    if (n <= raw * 1.35) best = n;
  }
  return { meters: best, label: formatScaleBar(best) };
}
