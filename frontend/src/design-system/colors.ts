/** Tokens de cor Sinidu+Clima — espelham tailwind.config.js */
export const colors = {
  background: '#09090b',
  card: '#18181b',
  border: '#27272a',
  accent: {
    emerald: '#10b981',
    sky: '#0ea5e9',
    amber: '#f59e0b',
    rose: '#f43f5e',
    indigo: '#6366f1',
    teal: '#14b8a6',
  },
  text: {
    primary: 'var(--sinidu-fg)',
    secondary: '#a1a1aa',
    muted: '#71717a',
  },
  focus: {
    ring: '#6366f1',
    glow: 'rgba(99, 102, 241, 0.25)',
  },
} as const;

export type SiniduColors = typeof colors;
