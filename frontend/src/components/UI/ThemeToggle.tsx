'use client';

import { Moon, Sun } from 'lucide-react';
import { useAppStore } from '@/stores/useAppStore';

type Props = {
  compact?: boolean;
};

export default function ThemeToggle({ compact = false }: Props) {
  const colorMode = useAppStore((s) => s.colorMode);
  const toggleColorMode = useAppStore((s) => s.toggleColorMode);
  const isLight = colorMode === 'light';

  return (
    <button
      type="button"
      onClick={toggleColorMode}
      title={isLight ? 'Ativar modo escuro' : 'Ativar tom claro (grayscale)'}
      aria-label={isLight ? 'Ativar modo escuro' : 'Ativar tom claro'}
      className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider transition-all duration-300 ${
        isLight
          ? 'border-amber-500/40 bg-amber-50 text-amber-800'
          : 'border-zinc-700 bg-zinc-950/80 text-zinc-400 hover:border-indigo-500/40 hover:text-indigo-200'
      }`}
    >
      {isLight ? <Moon size={12} /> : <Sun size={12} />}
      {!compact && (isLight ? 'Tom claro' : 'Modo escuro')}
    </button>
  );
}
