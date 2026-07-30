import type { ReactNode } from 'react';

type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'official' | 'derived' | 'estimated' | 'gap';

const TONE_CLASS: Record<BadgeTone, string> = {
  neutral: 'border-zinc-700 bg-zinc-950/70 text-zinc-400',
  success: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
  warning: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  danger: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
  info: 'border-sky-500/40 bg-sky-500/10 text-sky-300',
  official: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
  derived: 'border-sky-500/35 bg-sky-500/10 text-sky-200',
  estimated: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  gap: 'border-rose-500/40 bg-rose-500/10 text-rose-300',
};

type BadgeProps = {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
};

export default function Badge({ children, tone = 'neutral', className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex rounded-md border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide ${TONE_CLASS[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function qualityToBadgeTone(quality?: string | null): BadgeTone {
  const v = (quality || '').toUpperCase();
  if (v === 'OFICIAL') return 'official';
  if (v === 'OBSERVADO' || v === 'OBSERVADO SATÉLITE' || v.startsWith('OBSERVADO')) return 'info';
  if (v === 'DERIVADO') return 'derived';
  if (v === 'ESTIMADO') return 'estimated';
  if (v === 'LACUNA') return 'gap';
  return 'neutral';
}
