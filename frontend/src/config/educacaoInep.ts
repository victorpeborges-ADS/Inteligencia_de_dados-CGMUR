export type EducacaoEtapaId = 'todas' | 'infantil' | 'fundamental' | 'medio';

export type EducacaoEtapa = {
  id: EducacaoEtapaId;
  label: string;
  color: string;
};

export const EDUCACAO_ETAPAS: EducacaoEtapa[] = [
  { id: 'todas', label: 'Todas as etapas', color: '#6366f1' },
  { id: 'infantil', label: 'Educação infantil', color: '#f472b6' },
  { id: 'fundamental', label: 'Ensino fundamental', color: '#38bdf8' },
  { id: 'medio', label: 'Ensino médio', color: '#a78bfa' },
];

export const DEFAULT_EDUCACAO_ETAPA: EducacaoEtapaId = 'todas';
export const DEFAULT_EDUCACAO_RAIO_M = 800;
export const MIN_EDUCACAO_RAIO_M = 300;
export const MAX_EDUCACAO_RAIO_M = 2000;

export const DEPENDENCIA_LABELS: Record<string, string> = {
  federal: 'Federal',
  estadual: 'Estadual',
  municipal: 'Municipal',
  privada: 'Privada',
};

export function getEducacaoEtapa(id: EducacaoEtapaId): EducacaoEtapa {
  return EDUCACAO_ETAPAS.find((e) => e.id === id) ?? EDUCACAO_ETAPAS[0];
}

export function markerRadiusFromMatriculas(matriculas: number): number {
  const value = Math.max(0, matriculas);
  return Math.min(18, Math.max(5, Math.round(Math.sqrt(value) * 0.65)));
}
