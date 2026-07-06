type SkeletonProps = {
  className?: string;
};

export function Skeleton({ className = '' }: SkeletonProps) {
  return <div className={`animate-pulse rounded-md bg-zinc-800/80 ${className}`} aria-hidden />;
}

type SkeletonGridProps = {
  count?: number;
  className?: string;
};

export function SkeletonKpiGrid({ count = 4, className = '' }: SkeletonGridProps) {
  return (
    <div className={`grid grid-cols-2 gap-3 ${className}`}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-2">
          <Skeleton className="h-2.5 w-2/3" />
          <Skeleton className="h-7 w-1/2" />
          <Skeleton className="h-2 w-full" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonChart({ className = '' }: SkeletonProps) {
  return (
    <div className={`rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 ${className}`}>
      <Skeleton className="mb-3 h-3 w-1/3" />
      <Skeleton className="h-48 w-full rounded-lg" />
    </div>
  );
}
