'use client';

import { useEffect, useState } from 'react';
import { Lightbulb, X } from 'lucide-react';
import type { ActiveTab } from '@/config/platformTabs';
import { TAB_CONTEXT_HINTS, TAB_HINT_STORAGE_PREFIX } from '@/config/tabContextHints';

type TabContextHintProps = {
  tab: ActiveTab;
  onNavigateTab?: (tab: ActiveTab) => void;
};

export default function TabContextHint({ tab, onNavigateTab }: TabContextHintProps) {
  const config = TAB_CONTEXT_HINTS[tab];
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    if (!config) return;
    try {
      setDismissed(localStorage.getItem(`${TAB_HINT_STORAGE_PREFIX}${tab}`) === 'true');
    } catch {
      setDismissed(false);
    }
  }, [tab, config]);

  if (!config || dismissed) return null;

  const dismiss = () => {
    setDismissed(true);
    try {
      localStorage.setItem(`${TAB_HINT_STORAGE_PREFIX}${tab}`, 'true');
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="mb-4 flex items-start gap-3 rounded-xl border border-cyan-500/25 bg-cyan-950/15 px-3 py-2.5">
      <Lightbulb size={16} className="mt-0.5 shrink-0 text-cyan-300" />
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-bold text-cyan-100">{config.title}</p>
        <p className="mt-0.5 text-[10px] leading-relaxed text-zinc-400">{config.body}</p>
        {config.ctaTab && config.ctaLabel && onNavigateTab && (
          <button
            type="button"
            onClick={() => onNavigateTab(config.ctaTab!)}
            className="mt-2 text-[10px] font-bold uppercase tracking-wide text-cyan-300 hover:text-cyan-100"
          >
            {config.ctaLabel} →
          </button>
        )}
      </div>
      <button
        type="button"
        onClick={dismiss}
        title="Ocultar dica desta aba"
        className="shrink-0 rounded-md p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
      >
        <X size={14} />
      </button>
    </div>
  );
}
