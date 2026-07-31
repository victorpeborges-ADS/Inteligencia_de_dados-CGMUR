import type { ReactNode } from 'react';

type PanelSectionProps = {
  title: string;
  description?: string;
  tier?: 'primary' | 'secondary' | 'action';
  action?: ReactNode;
  children: ReactNode;
  className?: string;
};

const TIER_BORDER: Record<NonNullable<PanelSectionProps['tier']>, string> = {
  primary: 'border-teal-500/25 bg-teal-950/10',
  secondary: 'border-border bg-card/50',
  action: 'border-border bg-zinc-950/40',
};

const TIER_TITLE: Record<NonNullable<PanelSectionProps['tier']>, string> = {
  primary: 'text-teal-300',
  secondary: 'text-zinc-300',
  action: 'text-zinc-400',
};

export default function PanelSection({
  title,
  description,
  tier = 'secondary',
  action,
  children,
  className = '',
}: PanelSectionProps) {
  return (
    <section className={`rounded-lg border p-3.5 ${TIER_BORDER[tier]} ${className}`}>
      <div className="mb-2.5 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className={`text-xs font-bold uppercase tracking-wide ${TIER_TITLE[tier]}`}>{title}</h4>
          {description && (
            <p className="mt-1 text-[10px] leading-snug text-zinc-500">{description}</p>
          )}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
