import type { ActiveTab } from '@/config/platformTabs';

/** Perfis de tela (ortogonais ao Role JWT). 17h.1d */
export type UxProfile = 'defesa_civil' | 'planejamento' | 'prefeito';

export const UX_PROFILE_STORAGE_KEY = 'sinidu-ux-profile';

export const UX_PROFILE_LABELS: Record<UxProfile, string> = {
  defesa_civil: 'Defesa Civil',
  planejamento: 'Planejamento',
  prefeito: 'Prefeito',
};

export const UX_PROFILE_HINTS: Record<UxProfile, string> = {
  defesa_civil: 'Prioriza monitor e contingência; todas as abas continuam disponíveis.',
  planejamento: 'Prioriza painel, catálogo e casos; todas as abas continuam disponíveis.',
  prefeito: 'Prioriza painel executivo e assistente; todas as abas continuam disponíveis.',
};

/**
 * Abas principais — sempre visíveis em qualquer perfil.
 * O perfil só muda a ordem (destaque) e a aba padrão, não esconde módulos.
 */
export const UX_CORE_TABS: ActiveTab[] = [
  'dashboard',
  'onboarding',
  'catalog',
  'simulation',
  'monitoring',
  'contingency',
  'assistant',
  'cases',
];

/** Ordem preferida por perfil (as demais core tabs vêm em seguida). */
export const UX_PROFILE_TAB_ORDER: Record<UxProfile, ActiveTab[]> = {
  defesa_civil: ['monitoring', 'contingency', 'simulation', 'dashboard', 'assistant', 'catalog', 'cases', 'onboarding'],
  planejamento: ['dashboard', 'catalog', 'simulation', 'cases', 'onboarding', 'assistant', 'monitoring', 'contingency'],
  prefeito: ['dashboard', 'assistant', 'cases', 'monitoring', 'contingency', 'simulation', 'catalog', 'onboarding'],
};

/** @deprecated use UX_CORE_TABS + UX_PROFILE_TAB_ORDER — mantido para compat */
export const UX_PROFILE_TABS: Record<UxProfile, ActiveTab[]> = {
  defesa_civil: UX_CORE_TABS,
  planejamento: UX_CORE_TABS,
  prefeito: UX_CORE_TABS,
};

export const UX_PROFILE_DEFAULT_TAB: Record<UxProfile, ActiveTab> = {
  defesa_civil: 'monitoring',
  planejamento: 'dashboard',
  prefeito: 'dashboard',
};

/** Secções do painel executivo a esconder por perfil. */
export type DashboardSection =
  | 'recommendations'
  | 'kpis'
  | 'action_plan'
  | 'complementary'
  | 'charts';

export const UX_PROFILE_DASHBOARD_HIDDEN: Record<UxProfile, DashboardSection[]> = {
  defesa_civil: ['complementary', 'charts'],
  planejamento: [],
  prefeito: ['complementary', 'charts', 'kpis'],
};

export function orderedTabsForProfile(profile: UxProfile): ActiveTab[] {
  const preferred = UX_PROFILE_TAB_ORDER[profile] || [];
  const seen = new Set<ActiveTab>();
  const out: ActiveTab[] = [];
  for (const t of preferred) {
    if (UX_CORE_TABS.includes(t) && !seen.has(t)) {
      seen.add(t);
      out.push(t);
    }
  }
  for (const t of UX_CORE_TABS) {
    if (!seen.has(t)) out.push(t);
  }
  return out;
}

export function isUxProfile(value: string | null | undefined): value is UxProfile {
  return value === 'defesa_civil' || value === 'planejamento' || value === 'prefeito';
}

export function readUxProfile(): UxProfile {
  if (typeof window === 'undefined') return 'planejamento';
  try {
    const raw = localStorage.getItem(UX_PROFILE_STORAGE_KEY);
    if (isUxProfile(raw)) return raw;
  } catch {
    /* ignore */
  }
  return 'planejamento';
}

export function writeUxProfile(profile: UxProfile) {
  try {
    localStorage.setItem(UX_PROFILE_STORAGE_KEY, profile);
  } catch {
    /* ignore */
  }
}
