'use client';

import {
  Banknote,
  Building2,
  CalendarRange,
  ChevronRight,
  Clock,
  Landmark,
  MapPin,
} from 'lucide-react';
import type { ActionPlanItem, MunicipalActionPlan } from '@/utils/api';

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

function ActionCard({ item }: { item: ActionPlanItem}) {
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
}: {
  horizon: keyof typeof HORIZON_CONFIG;
  items: ActionPlanItem[];
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
          <ActionCard key={a.id} item={a} />
        ))}
      </div>
    </section>
  );
}

export default function ActionPlanPanel({ plan }: { plan: MunicipalActionPlan}) {
  const severityStyle =
    plan.severidade === 'Alta'
      ? 'border-rose-500/40 bg-rose-950/30 text-rose-200'
      : plan.severidade === 'Média'
        ? 'border-amber-500/40 bg-amber-950/30 text-amber-200'
        : 'border-emerald-500/40 bg-emerald-950/30 text-emerald-200';

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-card/50 p-3">
        <p className="text-[11px] font-semibold leading-snug text-zinc-100">{ plan.headline}</p>
        <div className="mt-2.5 grid grid-cols-3 gap-2">
          <div className="rounded-lg border border-border bg-background/80 px-2 py-2 text-center">
            <p className="text-[8px] uppercase tracking-wide text-zinc-400">Score</p>
            <p className="text-lg font-black text-amber-300">{ plan.score_sinidu}</p>
          </div>
          <div className={`rounded-lg border px-2 py-2 text-center ${severityStyle}`}>
            <p className="text-[8px] uppercase tracking-wide opacity-80">Severidade</p>
            <p className="text-sm font-extrabold">{ plan.severidade}</p>
          </div>
          <div className="rounded-lg border border-border bg-background/80 px-2 py-2 text-center">
            <p className="text-[8px] uppercase tracking-wide text-zinc-400">Total</p>
            <p className="text-lg font-black text-zinc-100">{ plan.total_acoes}</p>
            <p className="text-[8px] text-zinc-400">v{ plan.versao}</p>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5 text-[9px]">
          <span className="rounded-full border border-emerald-800/50 bg-emerald-950/30 px-2 py-0.5 text-emerald-300">
            Curto: { plan.acoes_curto_prazo.length}
          </span>
          <span className="rounded-full border border-amber-800/50 bg-amber-950/30 px-2 py-0.5 text-amber-300">
            Médio: { plan.acoes_medio_prazo.length}
          </span>
          <span className="rounded-full border border-indigo-800/50 bg-indigo-950/30 px-2 py-0.5 text-indigo-300">
            Longo: { plan.acoes_longo_prazo.length}
          </span>
        </div>
      </div>

      <div className="flex flex-col space-y-3">
        <ActionHorizonSection horizon="curto" items={ plan.acoes_curto_prazo} />
        <ActionHorizonSection horizon="medio" items={ plan.acoes_medio_prazo} />
        <ActionHorizonSection horizon="longo" items={ plan.acoes_longo_prazo} />
      </div>

      { plan.programas_financiamento.length > 0 && (
        <section className="rounded-xl border border-sky-500/25 bg-sky-950/15 p-3">
          <h5 className="mb-2 flex items-center space-x-1.5 text-[10px] font-extrabold uppercase tracking-wide text-sky-200">
            <Banknote size={12} />
            <span>Financiamento federal sugerido</span>
          </h5>
          <div className="flex flex-col space-y-2">
            { plan.programas_financiamento.slice(0, 4).map((p) => (
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
