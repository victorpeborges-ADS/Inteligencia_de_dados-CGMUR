/** Tipografia 20f.4 — Source Sans 3 (institucional; evita Inter genérico). */
export const typography = {
  fontFamily: {
    sans: ['"Source Sans 3"', 'Segoe UI', 'system-ui', 'sans-serif'],
  },
  fontSize: {
    micro: '8px',
    xs: '10px',
    sm: '11px',
    base: '12px',
    md: '14px',
    lg: '16px',
    xl: '20px',
    '2xl': '24px',
  },
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
    extrabold: 800,
  },
  letterSpacing: {
    tight: '-0.015em',
    wide: '0.08em',
    wider: '0.14em',
  },
} as const;
