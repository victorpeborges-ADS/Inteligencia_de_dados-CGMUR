export type EducacaoEtapaId = 'todas' | 'infantil' | 'fundamental' | 'medio';

export type EducacaoEtapa = {
  id: EducacaoEtapaId;
  label: string;
  color: string;
};

export const EDUCACAO_ETAPAS: EducacaoEtapa[] = [
  { id: 'todas', label: 'Todas as etapas', color: '#0d9488' },
  { id: 'infantil', label: 'Educação infantil', color: '#f472b6' },
  { id: 'fundamental', label: 'Ensino fundamental', color: '#38bdf8' },
  { id: 'medio', label: 'Ensino médio', color: '#a78bfa' },
];

export const DEFAULT_EDUCACAO_ETAPA: EducacaoEtapaId = 'todas';
export const DEFAULT_EDUCACAO_RAIO_M = 800;
export const MIN_EDUCACAO_RAIO_M = 300;
export const MAX_EDUCACAO_RAIO_M = 2000;

export type DependenciaId = 'federal' | 'estadual' | 'municipal' | 'privada';

export const DEPENDENCIA_LABELS: Record<string, string> = {
  federal: 'Federal',
  estadual: 'Estadual',
  municipal: 'Municipal',
  privada: 'Privada',
};

/** Cores sóbrias por esfera — usadas em educação e equipamentos */
export const DEPENDENCIA_COLORS: Record<string, string> = {
  federal: '#1d4ed8',
  estadual: '#b45309',
  municipal: '#0f766e',
  privada: '#7c3aed',
};

export const TIPO_EQUIPAMENTO_LABELS: Record<string, string> = {
  escola: 'Escola',
  creche: 'Creche / EMEI',
  faculdade: 'Faculdade / Universidade',
  hospital: 'Hospital',
  upa: 'UPA',
  ubs: 'UBS / USF',
  caps: 'CAPS',
  samu: 'SAMU',
  via: 'Via',
};

export type EquipamentoTipoId =
  | 'escola'
  | 'creche'
  | 'faculdade'
  | 'hospital'
  | 'upa'
  | 'ubs'
  | 'caps'
  | 'samu'
  | 'via';

export type EquipamentoTipoOption = {
  id: EquipamentoTipoId;
  label: string;
  short: string;
  color: string;
};

/** Tipos filtráveis no mapa — cor = identidade visual do equipamento */
export const EQUIPAMENTO_TIPOS: EquipamentoTipoOption[] = [
  { id: 'escola', label: 'Escola', short: 'E', color: '#0284c7' },
  { id: 'creche', label: 'Creche / EMEI', short: 'Cr', color: '#db2777' },
  { id: 'faculdade', label: 'Faculdade / Univ.', short: 'F', color: '#7c3aed' },
  { id: 'hospital', label: 'Hospital', short: 'H', color: '#dc2626' },
  { id: 'upa', label: 'UPA', short: 'U', color: '#ea580c' },
  { id: 'ubs', label: 'UBS / USF', short: 'Ub', color: '#16a34a' },
  { id: 'caps', label: 'CAPS', short: 'C', color: '#0891b2' },
  { id: 'samu', label: 'SAMU', short: 'S', color: '#b91c1c' },
  { id: 'via', label: 'Vias', short: 'V', color: '#94a3b8' },
];

export const EQUIPAMENTO_TIPOS_DEFAULT: EquipamentoTipoId[] = EQUIPAMENTO_TIPOS.filter(
  (t) => t.id !== 'via',
).map((t) => t.id);

export const EQUIPAMENTO_DEPS_DEFAULT: DependenciaId[] = [
  'federal',
  'estadual',
  'municipal',
  'privada',
];

export function getEquipamentoTipo(id?: string | null): EquipamentoTipoOption {
  const key = (id || '').toLowerCase() as EquipamentoTipoId;
  return EQUIPAMENTO_TIPOS.find((t) => t.id === key) ?? EQUIPAMENTO_TIPOS[0];
}

export function getEquipamentoTipoColor(tipo?: string | null): string {
  return getEquipamentoTipo(tipo).color;
}

export function getEducacaoEtapa(id: EducacaoEtapaId): EducacaoEtapa {
  return EDUCACAO_ETAPAS.find((e) => e.id === id) ?? EDUCACAO_ETAPAS[0];
}

export function getDependenciaColor(dependencia?: string | null): string {
  if (!dependencia) return '#64748b';
  return DEPENDENCIA_COLORS[dependencia] || '#64748b';
}

/** Feature passa nos filtros de tipo + dependência (vias ignoram dependência). */
export function matchEquipamentoFiltro(
  props: { tipo?: string | null; dependencia?: string | null },
  tiposAtivos: readonly string[],
  depsAtivas: readonly string[],
): boolean {
  const tipo = String(props.tipo || '').toLowerCase();
  if (!tipo || !tiposAtivos.includes(tipo)) return false;
  if (tipo === 'via') return true;
  const dep = String(props.dependencia || '').toLowerCase();
  if (!dep) return depsAtivas.length > 0; // sem esfera: mostra se há alguma dep ativa
  return depsAtivas.includes(dep);
}

export function markerRadiusFromMatriculas(matriculas: number): number {
  const value = Math.max(0, matriculas);
  return Math.min(18, Math.max(5, Math.round(Math.sqrt(value) * 0.65)));
}

export function markerRadiusFromTipo(tipo?: string | null): number {
  switch ((tipo || '').toLowerCase()) {
    case 'hospital':
      return 9;
    case 'upa':
    case 'faculdade':
      return 8;
    case 'escola':
      return 7;
    case 'creche':
    case 'ubs':
    case 'caps':
    case 'samu':
      return 6;
    default:
      return 5;
  }
}
