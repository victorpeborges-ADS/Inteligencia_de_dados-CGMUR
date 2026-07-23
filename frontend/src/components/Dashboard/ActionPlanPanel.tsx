'use client';

import { useMemo, useState } from 'react';
import {
  Banknote,
  Building2,
  CalendarRange,
  ChevronRight,
  Clock,
  Landmark,
  MapPin,
  RefreshCw,
} from 'lucide-react';
import {
  api,
  type ActionExecutionStatus,
  type ActionPlanItem,
  type MunicipalActionPlan,
} from '@/utils/api';

const COST_STYLE: Record<string, string> = {
  Baixo: 'bg-emerald-500/15 text-emerald-300 border-emerald-700/40',
  Médio: 'bg-amber-500/15 text-amber-300 border-amber-700/40',
  Alto: 'bg-rose-500/15 text-rose-300 border-rose-700/40',
};

const PRIORITY_STYLE: Record<string, string> = {
  Alta: 'text-rose-300 bg-rose-500/10 border-rose-700/40',
  Média: 'text-amber-300 bg-amber-500/10 border-amber-700/40',
  Baixa: 'text-emerald-300 bg-emerald-500/10 border-emerald-700/40',
};

const STATUS_STYLE: Record<ActionExecutionStatus, string> = {
  planejada: 'border-zinc-600 text-zinc-300',
  em_andamento: 'border-sky-600/50 text-sky-200 bg-sky-950/30',
  executada: 'border-emerald-600/50 text-emerald-200 bg-emerald-950/30',
  cancelada: 'border-rose-700/40 text-rose-300/80 line-through',
};

const STATUS_LABEL: Record<ActionExecutionStatus, string> = {
  planejada: 'Planejada',
  em_andamento: 'Em andamento',
  executada: 'Executada',
  cancelada: 'Cancelada',
};

const HORIZON_CONFIG = {
  curto: {
    label: 'Curto prazo',
    hint: '0–12 meses',
    icon: Clock,
    accent: 'border-emerald-500/40 bg-emerald-950/25',
    title: 'text-emerald-200',
    bar: 'bg-emerald-500',
  },
  medio: {
    label: 'Médio prazo',
    hint: '1–3 anos',
    icon: CalendarRange,
    accent: 'border-amber-500/40 bg-amber-950/25',
    title: 'text-amber-200',
    bar: 'bg-amber-500',
  },
  longo: {
    label: 'Longo prazo',
    hint: '3+ anos',
    icon: Landmark,
    accent: 'border-indigo-500/40 bg-indigo-950/25',
    title: 'text-indigo-200',
    bar: 'bg-indigo-500',
  },
} as const;

function ActionCard({
  item,
  status,
  busy,
  onStatusChange,
}: {
  item: ActionPlanItem;
  status: ActionExecutionStatus;
  busy?: boolean;
  onStatusChange?: (id: string, status: ActionExecutionStatus) => void;
}) {
  return (
    <article className="group rounded-xl border border-border bg-gradient-to-br from-card/90 to-card/40 p-3 shadow-sm transition hover:border-amber-700/30">
      <div className="mb-2 flex items-start justify-between">
        <h6 className="flex-1 pr-2 text-[11px] font-bold leading-snug text-zinc-100">{item.titulo}</h6>
        <div className="flex shrink-0 flex-col items-end space-y-1">
          <span
            className={`rounded-md border px-1.5 py-0.5 text-[8px] font-bold uppercase ${
              COST_STYLE[item.custo] || 'bg-zinc-800 text-zinc-400 border-border'
            }`}
          >
            {item.custo}
          </span>
          <span
            className={`rounded-md border px-1.5 py-0.5 text-[8px] font-semibold ${
              PRIORITY_STYLE[item.prioridade] || 'border-border text-zinc-400'
            }`}
          >
            {item.prioridade}
          </span>
        </div>
      </div>
      <p className="text-[10px] leading-relaxed text-zinc-400">{item.descricao}</p>
      {item.casos_referencia && item.casos_referencia.length > 0 && (
        <div className="mt-2 space-y-1 rounded-lg border border-indigo-800/30 bg-indigo-950/15 p-2">
          {item.casos_referencia.slice(0, 2).map((ref) => (
            <p key={ref.id} className="text-[9px] text-indigo-200/90 leading-relaxed">
              📌 Referência: {ref.referencia_texto}
            </p>
          ))}
        </div>
      )}
      {item.bairros_alvo?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {item.bairros_alvo.slice(0, 3).map((b) => (
            <span
              key={b}
              className="inline-flex items-center gap-0.5 rounded-full border border-border bg-background/80 px-1.5 py-0.5 text-[8px] text-zinc-400"
            >
              <MapPin size={8} /> {b}
            </span>
          ))}
        </div>
      )}
      {onStatusChange && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="text-[8px] uppercase tracking-wide text-zinc-500">Status</span>
          <select
            disabled={busy}
            value={status}
            onChange={(e) => onStatusChange(item.id, e.target.value as ActionExecutionStatus)}
            className={`rounded border bg-zinc-950/60 px-1.5 py-0.5 text-[9px] font-semibold ${STATUS_STYLE[status]}`}
          >
            {(Object.keys(STATUS_LABEL) as ActionExecutionStatus[]).map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </select>
        </div>
      )}
      <footer className="mt-2.5 flex flex-wrap items-center gap-2 border-t border-border/80 pt-2 text-[9px] text-zinc-400">
        <span className="inline-flex items-center gap-1">
          <Building2 size={10} className="text-zinc-600" />
          {item.orgao}
        </span>
        <ChevronRight size={10} className="text-zinc-700" />
        <span className="truncate">{item.fonte}</span>
      </footer>
    </article>
  );
}

function ActionHorizonSection({
  horizon,
  items,
  statusMap,
  busyId,
  onStatusChange,
}: {
  horizon: keyof typeof HORIZON_CONFIG;
  items: ActionPlanItem[];
  statusMap: Record<string, ActionExecutionStatus>;
  busyId?: string | null;
  onStatusChange?: (id: string, status: ActionExecutionStatus) => void;
}) {
  const cfg = HORIZON_CONFIG[horizon];
  const Icon = cfg.icon;
  if (items.length === 0) return null;

  return (
    <section className={`overflow-hidden rounded-xl border ${cfg.accent}`}>
      <header className="flex items-center justify-between px-3 py-2.5">
        <div className="flex items-center space-x-2">
          <div className={`flex h-7 w-7 items-center justify-center rounded-lg border ${cfg.accent}`}>
            <Icon size={14} className={cfg.title} />
          </div>
          <div>
            <h5 className={`text-[10px] font-extrabold uppercase tracking-wide ${cfg.title}`}>
              {cfg.label}
            </h5>
            <p className="text-[9px] text-zinc-400">{cfg.hint}</p>
          </div>
        </div>
        <span className="rounded-full border border-border bg-background/60 px-2 py-0.5 text-[9px] font-bold text-zinc-100">
          {items.length} {items.length === 1 ? 'ação' : 'ações'}
        </span>
      </header>
      <div className={`h-0.5 w-full ${cfg.bar} opacity-60`} />
      <div className="flex flex-col space-y-2 p-2.5">
        {items.map((a) => (
          <ActionCard
            key={a.id}
            item={a}
            status={statusMap[a.id] || 'planejada'}
            busy={busyId === a.id}
            onStatusChange={onStatusChange}
          />
        ))}
      </div>
    </section>
  );
}

export default function ActionPlanPanel({
  plan,
  onPlanChange,
}: {
  plan: MunicipalActionPlan;
  onPlanChange?: (plan: MunicipalActionPlan) => void;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reavaliando, setReavaliando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const statusMap = useMemo(() => {
    const map: Record<string, ActionExecutionStatus> = {};
    const acoes = plan.acompanhamento?.acoes || {};
    for (const [id, row] of Object.entries(acoes)) {
      if (row?.status) map[id] = row.status;
    }
    return map;
  }, [plan.acompanhamento]);

  const counts = useMemo(() => {
    const all = [
      ...plan.acoes_curto_prazo,
      ...plan.acoes_medio_prazo,
      ...plan.acoes_longo_prazo,
    ];
    const c = { planejada: 0, em_andamento: 0, executada: 0, cancelada: 0 };
    for (const a of all) {
      const st = statusMap[a.id] || 'planejada';
      c[st] += 1;
    }
    return c;
  }, [plan, statusMap]);

  const lastReav = plan.acompanhamento?.reavaliacoes?.slice(-1)[0];

  const severityStyle =
    plan.severidade === 'Alta' || plan.severidade === 'Crítica'
      ? 'border-rose-500/40 bg-rose-950/30 text-rose-200'
      : plan.severidade === 'Média' || plan.severidade === 'Moderada'
        ? 'border-amber-500/40 bg-amber-950/30 text-amber-200'
        : 'border-emerald-500/40 bg-emerald-950/30 text-emerald-200';

  const handleStatus = async (actionId: string, status: ActionExecutionStatus) => {
    if (!plan.codigo_ibge || !onPlanChange) return;
    setBusyId(actionId);
    setError(null);
    try {
      const next = await api.patchActionStatus(plan.codigo_ibge, actionId, { status });
      onPlanChange(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao atualizar ação');
    } finally {
      setBusyId(null);
    }
  };

  const handleReavaliar = async () => {
    if (!plan.codigo_ibge || !onPlanChange) return;
    setReavaliando(true);
    setError(null);
    try {
      const out = await api.reavaliarActionPlan(plan.codigo_ibge);
      onPlanChange(out.plano);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao reavaliar');
    } finally {
      setReavaliando(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-card/50 p-3">
        <p className="text-[11px] font-semibold leading-snug text-zinc-100">{plan.headline}</p>
        <div className="mt-2.5 grid grid-cols-3 gap-2">
          <div className="rounded-lg border border-border bg-background/80 px-2 py-2 text-center">
            <p className="text-[8px] uppercase tracking-wide text-zinc-400">Score</p>
            <p className="text-lg font-black text-amber-300">{plan.score_sinidu}</p>
          </div>
          <div className={`rounded-lg border px-2 py-2 text-center ${severityStyle}`}>
            <p className="text-[8px] uppercase tracking-wide opacity-80">Severidade</p>
            <p className="text-sm font-extrabold">{plan.severidade}</p>
          </div>
          <div className="rounded-lg border border-border bg-background/80 px-2 py-2 text-center">
            <p className="text-[8px] uppercase tracking-wide text-zinc-400">Total</p>
            <p className="text-lg font-black text-zinc-100">{plan.total_acoes}</p>
            <p className="text-[8px] text-zinc-400">v{plan.versao}</p>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5 text-[9px]">
          <span className="rounded-full border border-emerald-800/50 bg-emerald-950/30 px-2 py-0.5 text-emerald-300">
            Executadas: {counts.executada}
          </span>
          <span className="rounded-full border border-sky-800/50 bg-sky-950/30 px-2 py-0.5 text-sky-300">
            Em andamento: {counts.em_andamento}
          </span>
          <span className="rounded-full border border-zinc-700 bg-zinc-900/50 px-2 py-0.5 text-zinc-400">
            Planejadas: {counts.planejada}
          </span>
        </div>

        {onPlanChange && (
          <div className="mt-3 rounded-lg border border-teal-500/25 bg-teal-950/15 p-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[10px] font-bold text-teal-100">Ciclo de acompanhamento</p>
                <p className="text-[9px] text-zinc-400">
                  Marque o que foi feito e reavalie o risco para fechar o ciclo.
                </p>
              </div>
              <button
                type="button"
                onClick={handleReavaliar}
                disabled={reavaliando}
                className="inline-flex items-center gap-1.5 rounded-lg border border-teal-500/40 bg-teal-500/10 px-2.5 py-1.5 text-[10px] font-bold text-teal-100 hover:bg-teal-500/20 disabled:opacity-50"
              >
                <RefreshCw size={12} className={reavaliando ? 'animate-spin' : ''} />
                {reavaliando ? 'Reavaliando…' : 'Reavaliar risco'}
              </button>
            </div>
            {lastReav && (
              <p className="mt-2 text-[9px] text-zinc-400">
                Última reavaliação: score {lastReav.score_antes ?? '—'} → {lastReav.score_depois ?? '—'}
                {lastReav.delta_score != null && (
                  <span className={lastReav.delta_score <= 0 ? ' text-emerald-300' : ' text-rose-300'}>
                    {' '}
                    ({lastReav.delta_score > 0 ? '+' : ''}
                    {lastReav.delta_score})
                  </span>
                )}
                {lastReav.nivel && <> · semáforo {lastReav.nivel}</>}
              </p>
            )}
          </div>
        )}
        {error && <p className="mt-2 text-[10px] text-rose-300">{error}</p>}
      </div>

      <div className="flex flex-col space-y-3">
        <ActionHorizonSection
          horizon="curto"
          items={plan.acoes_curto_prazo}
          statusMap={statusMap}
          busyId={busyId}
          onStatusChange={onPlanChange ? handleStatus : undefined}
        />
        <ActionHorizonSection
          horizon="medio"
          items={plan.acoes_medio_prazo}
          statusMap={statusMap}
          busyId={busyId}
          onStatusChange={onPlanChange ? handleStatus : undefined}
        />
        <ActionHorizonSection
          horizon="longo"
          items={plan.acoes_longo_prazo}
          statusMap={statusMap}
          busyId={busyId}
          onStatusChange={onPlanChange ? handleStatus : undefined}
        />
      </div>

      {plan.programas_financiamento.length > 0 && (
        <section className="rounded-xl border border-sky-500/25 bg-sky-950/15 p-3">
          <h5 className="mb-2 flex items-center space-x-1.5 text-[10px] font-extrabold uppercase tracking-wide text-sky-200">
            <Banknote size={12} />
            <span>Financiamento federal sugerido</span>
          </h5>
          <div className="flex flex-col space-y-2">
            {plan.programas_financiamento.slice(0, 4).map((p) => (
              <div key={p.nome} className="rounded-lg border border-border bg-background/60 p-2.5">
                <p className="text-[10px] font-bold text-zinc-100">{p.nome}</p>
                <p className="mt-0.5 text-[9px] font-medium text-sky-300/90">{p.orgao}</p>
                <p className="mt-1 text-[9px] leading-relaxed text-zinc-400">{p.motivo}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
