import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import Badge, { qualityToBadgeTone } from './Badge';

type KpiCardProps = {
  title: string;
  value: string;
  description?: string;
  icon: LucideIcon;
  iconClassName?: string;
  tier?: 'primary' | 'secondary';
  quality?: string;
  badge?: string;
  className?: string;
  children?: ReactNode;
};

export default function KpiCard({
  title,
  value,
  description,
  icon: Icon,
  iconClassName = 'text-indigo-400',
  tier = 'secondary',
  quality,
  badge,
  className = '',
  children,
}: KpiCardProps) {
  const isPrimary = tier === 'primary';

  return (
    <div
      className={`min-w-0 overflow-hidden rounded-xl border backdrop-blur-md transition-all duration-300 ${
        isPrimary
          ? 'border-indigo-500/35 bg-indigo-950/20 p-4 shadow-lg shadow-indigo-950/20'
          : 'border-border bg-card/60 p-3 hover:border-zinc-700'
      } ${className}`}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5 pr-1">
            <span
              className={`min-w-0 font-bold uppercase tracking-wider text-zinc-500 ${
                isPrimary ? 'text-[10px]' : 'text-[9px]'
              }`}
            >
              {title}
            </span>
            {quality && (
              <Badge tone={qualityToBadgeTone(quality)} className="shrink-0">
                {quality}
              </Badge>
            )}
            {badge && (
              <Badge tone="success" className="shrink-0">
                {badge}
              </Badge>
            )}
          </div>
          <p
            className={`mt-1 break-words font-extrabold leading-tight text-foreground tabular-nums ${
              isPrimary ? 'text-2xl' : 'text-base sm:text-lg'
            }`}
            title={value}
          >
            {value}
          </p>
          {description && (
            <p
              className={`mt-1 break-words leading-snug text-zinc-400 ${
                isPrimary ? 'text-[11px]' : 'text-[10px]'
              }`}
            >
              {description}
            </p>
          )}
        </div>
        <div
          className={`shrink-0 self-start rounded-lg border border-zinc-800 bg-zinc-950/80 ${
            isPrimary ? 'p-2.5' : 'p-1.5'
          } ${iconClassName}`}
          aria-hidden
        >
          <Icon size={isPrimary ? 20 : 16} />
        </div>
      </div>
      {children ? <div className="min-w-0">{children}</div> : null}
    </div>
  );
}
