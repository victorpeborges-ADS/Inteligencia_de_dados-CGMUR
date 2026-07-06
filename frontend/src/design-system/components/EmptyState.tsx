import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
};

export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className = '',
  compact = false,
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-800 bg-zinc-950/40 text-center ${
        compact ? 'gap-2 px-4 py-5' : 'gap-3 px-6 py-8'
      } ${className}`}
    >
      <div className={`rounded-xl border border-zinc-800 bg-zinc-900/80 text-zinc-500 ${compact ? 'p-2' : 'p-3'}`}>
        <Icon size={compact ? 18 : 22} />
      </div>
      <div>
        <p className={`font-bold text-zinc-300 ${compact ? 'text-xs' : 'text-sm'}`}>{title}</p>
        {description && (
          <p className={`mt-1 leading-relaxed text-zinc-500 ${compact ? 'text-[10px]' : 'text-[11px]'}`}>
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}
