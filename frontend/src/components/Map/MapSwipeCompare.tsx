'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Columns } from 'lucide-react';

export type SwipeCompareMode = '2d3d' | 'antes_depois';

type Props = {
  mode: SwipeCompareMode;
  left: ReactNode;
  right: ReactNode;
  leftLabel?: string;
  rightLabel?: string;
  initialPct?: number;
  className?: string;
};

/**
 * Cortina deslizante entre dois mapas/estados (17f.7).
 * Ambos os filhos ocupam o mesmo retângulo; o clip define o que aparece.
 */
export default function MapSwipeCompare({
  mode,
  left,
  right,
  leftLabel,
  rightLabel,
  initialPct = 50,
  className = '',
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [pct, setPct] = useState(initialPct);
  const dragging = useRef(false);

  const resolvedLeft = leftLabel ?? (mode === '2d3d' ? 'Mapa 2D' : 'Antes');
  const resolvedRight = rightLabel ?? (mode === '2d3d' ? 'Terreno 3D' : 'Depois');

  const setFromClientX = useCallback((clientX: number) => {
    const el = wrapRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0) return;
    const next = ((clientX - rect.left) / rect.width) * 100;
    setPct(Math.max(8, Math.min(92, next)));
  }, []);

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (!dragging.current) return;
      setFromClientX(e.clientX);
    };
    const onUp = () => {
      dragging.current = false;
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [setFromClientX]);

  return (
    <div ref={wrapRef} className={`relative h-full w-full overflow-hidden ${className}`}>
      {/* Esquerda (visível até a cortina) */}
      <div
        className="absolute inset-0 z-[1]"
        style={{ clipPath: `inset(0 ${100 - pct}% 0 0)` }}
      >
        {left}
      </div>

      {/* Direita (visível a partir da cortina) */}
      <div
        className="absolute inset-0 z-[2]"
        style={{ clipPath: `inset(0 0 0 ${pct}%)` }}
      >
        {right}
      </div>

      {/* Alça */}
      <div
        className="absolute inset-y-0 z-[30] w-0"
        style={{ left: `${pct}%` }}
      >
        <div className="absolute inset-y-0 -left-px w-0.5 bg-white/90 shadow-[0_0_12px_rgba(0,0,0,0.65)]" />
        <button
          type="button"
          aria-label="Arrastar cortina do comparador"
          onPointerDown={(e) => {
            e.preventDefault();
            dragging.current = true;
            (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
            setFromClientX(e.clientX);
          }}
          className="absolute left-1/2 top-1/2 flex h-11 w-11 -translate-x-1/2 -translate-y-1/2 cursor-col-resize items-center justify-center rounded-full border-2 border-white bg-indigo-600 text-white shadow-xl"
        >
          <Columns size={16} />
        </button>
      </div>

      <div className="pointer-events-none absolute left-3 top-3 z-[31] rounded-md border border-zinc-700/80 bg-zinc-950/85 px-2 py-1 text-[9px] font-extrabold uppercase tracking-wider text-zinc-200">
        {resolvedLeft}
      </div>
      <div className="pointer-events-none absolute right-3 top-3 z-[31] rounded-md border border-zinc-700/80 bg-zinc-950/85 px-2 py-1 text-[9px] font-extrabold uppercase tracking-wider text-zinc-200">
        {resolvedRight}
      </div>
    </div>
  );
}
