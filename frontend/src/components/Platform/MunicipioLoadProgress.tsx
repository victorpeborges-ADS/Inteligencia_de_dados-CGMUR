'use client';

import RotatingLoader, { MUNICIPIO_LOAD_STEPS } from '@/components/UI/RotatingLoader';

export default function MunicipioLoadProgress({ visible, stepIndex = 0 }: { visible: boolean; stepIndex?: number }) {
  if (!visible) return null;

  const idx = Math.min(stepIndex, MUNICIPIO_LOAD_STEPS.length - 1);

  return (
    <div className="rounded-lg border border-indigo-500/30 bg-indigo-950/30 px-3 py-2">
      <RotatingLoader messages={MUNICIPIO_LOAD_STEPS} intervalMs={2500} className="text-indigo-200" />
      <ul className="mt-2 space-y-1">
        {MUNICIPIO_LOAD_STEPS.map((label, i) => (
          <li
            key={label}
            className={`text-[10px] ${i < idx ? 'text-emerald-400' : i === idx ? 'text-indigo-200' : 'text-zinc-600'}`}
          >
            {i < idx ? '✅' : i === idx ? '⏳' : '○'} {label.replace('…', '')}
          </li>
        ))}
      </ul>
    </div>
  );
}
