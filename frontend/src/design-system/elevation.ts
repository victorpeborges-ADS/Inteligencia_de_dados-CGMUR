/** Elevação sóbria — sem glow colorido (20f.4). */
export const elevation = {
  none: 'none',
  sm: '0 1px 2px rgba(0, 0, 0, 0.35)',
  md: '0 2px 8px rgba(0, 0, 0, 0.4)',
  lg: '0 4px 16px rgba(0, 0, 0, 0.45)',
  xl: '0 8px 28px rgba(0, 0, 0, 0.5)',
  /** @deprecated 20f.4 — preferir `md`; mantido para compat */
  glowIndigo: '0 2px 8px rgba(0, 0, 0, 0.4)',
} as const;
