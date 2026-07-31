'use client';

import { useEffect, useState } from 'react';
import { api, type OnboardingStatus } from '@/utils/api';
import { Loader2, Zap } from 'lucide-react';

const STEP_LABELS: Record<string, string> = {
  geometria: 'Malha IBGE',
  mapbiomas: 'Dados MapBiomas',
  score: 'Score inicial',
};

function stepIcon(status: string): string {
  if (status === 'ok') return '✅';
  if (status === 'falha' || status === 'lacuna') return '❌';
  if (status === 'parcial') return '⏳';
  return '⏳';
}

function stepProgress(status: OnboardingStatus, key: string): string | null {
  if (key === 'mapbiomas' && status.completeness_score != null) {
    return `${Math.round(status.completeness_score)}%`;
  }
  const step = status.integration_steps?.[key];
  if (!step) return null;
  if (step.status === 'ok') return 'concluído';
  if (step.status === 'parcial') return 'parcial';
  if (step.status === 'falha') return 'falha';
  return 'em andamento';
}

export default function OnboardingBanner({ codigoIbge, municipioNome }: { codigoIbge: string; municipioNome?: string }) {
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [activating, setActivating] = useState(false);
  const [activateMsg, setActivateMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const load = async () => {
      try {
        const data = await api.getOnboardingStatus(codigoIbge);
        if (!cancelled) setStatus(data);
      } catch {
        if (!cancelled) setStatus(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    timer = setInterval(load, 15000);

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [codigoIbge]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-950/20 px-4 py-3 text-xs text-amber-100">
        <Loader2 className="h-4 w-4 animate-spin" />
        Verificando status de onboarding…
      </div>
    );
  }

  if (!status || status.onboarding_status === 'concluido') return null;

  const handleActivate = async () => {
    setActivating(true);
    setActivateMsg(null);
    try {
      await api.ensureMunicipality(codigoIbge);
      const data = await api.getOnboardingStatus(codigoIbge);
      setStatus(data);
      setActivateMsg('Integração básica reforçada.');
    } catch (e: unknown) {
      setActivateMsg(e instanceof Error ? e.message : 'Falha ao ativar');
    } finally {
      setActivating(false);
    }
  };

  const nome = municipioNome || status.nome;
  const steps = ['geometria', 'mapbiomas', 'score'] as const;

  const scoreStatus =
    status.score_sinidu != null
      ? { status: 'ok', detail: `Score ${Math.round(status.score_sinidu)}` }
      : { status: 'pendente', detail: 'aguardando' };

  const displaySteps = steps.map((key) => {
    if (key === 'score') {
      return { key, label: STEP_LABELS.score, raw: scoreStatus.status, progress: scoreStatus.detail };
    }
    const step = status.integration_steps?.[key];
    const raw = step?.status ?? 'pendente';
    return { key, label: STEP_LABELS[key], raw, progress: stepProgress(status, key) };
  });

  return (
    <div className="rounded-xl border border-amber-500/35 bg-gradient-to-br from-amber-950/40 to-zinc-950/80 px-4 py-3 shadow-lg">
      <div className="flex items-start gap-2">
        <Zap className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-amber-100">{nome} em configuração inicial</p>
          <p className="mt-1 text-xs text-zinc-400">
            Estamos carregando os dados. Isso leva ~2 minutos. Você pode explorar o sistema enquanto carrega.
          </p>
          <ul className="mt-3 space-y-1.5">
            {displaySteps.map((item) => (
              <li key={item.key} className="flex items-center justify-between text-xs text-zinc-300">
                <span>
                  {stepIcon(item.raw)} {item.label}
                </span>
                <span className="text-[10px] text-zinc-500">{item.progress ?? 'aguardando'}</span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => void handleActivate()}
            disabled={activating}
            className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-amber-500/40 bg-amber-500/15 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-amber-100 hover:bg-amber-500/25 disabled:opacity-50"
          >
            {activating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
            Concluir integração básica
          </button>
          {activateMsg && <p className="mt-1.5 text-[10px] text-amber-100/80">{activateMsg}</p>}
        </div>
      </div>
    </div>
  );
}
