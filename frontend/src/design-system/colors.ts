/** Tokens de cor Sinidu+Clima — estética sóbria 20f.4 (institucional, sem glow). */
export const colors = {
  background: '#0b0c0e',
  card: '#14161a',
  border: '#2a2e35',
  accent: {
    emerald: '#10b981',
    sky: '#0ea5e9',
    amber: '#f59e0b',
    rose: '#f43f5e',
    /** Brand institucional (substitui indigo como chrome) */
    teal: '#0d9488',
    /** Mantido para legado / rede urbana */
    indigo: '#6366f1',
  },
  text: {
    primary: 'var(--sinidu-fg)',
    secondary: '#a8adb7',
    muted: '#7a808c',
  },
  focus: {
    ring: '#0d9488',
    glow: 'rgba(13, 148, 136, 0.18)',
  },
} as const;

export type SiniduColors = typeof colors;
