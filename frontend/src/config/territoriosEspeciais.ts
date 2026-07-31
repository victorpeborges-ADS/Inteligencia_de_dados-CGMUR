export type TerritorioTipoId = 'todas' | 'quilombo' | 'terra_indigena' | 'comunidade_urbana';

export const DEFAULT_TERRITORIO_TIPO: TerritorioTipoId = 'todas';

export const TERRITORIO_TIPOS: Array<{
  id: TerritorioTipoId;
  label: string;
  color: string;
  description: string;
}> = [
  {
    id: 'quilombo',
    label: 'Quilombos',
    color: '#a16207',
    description: 'Territórios quilombolas certificados (INCRA).',
  },
  {
    id: 'terra_indigena',
    label: 'Terras indígenas',
    color: '#15803d',
    description: 'Terras indígenas homologadas (FUNAI).',
  },
  {
    id: 'comunidade_urbana',
    label: 'Comunidades urbanas',
    color: '#c026d3',
    description: 'Aglomerados subnormais e periferias urbanas (IBGE Censo 2022).',
  },
  {
    id: 'todas',
    label: 'Todas',
    color: '#6366f1',
    description: 'Exibir todos os tipos de território especial.',
  },
];

export function getTerritorioTipo(id: TerritorioTipoId = 'todas') {
  return TERRITORIO_TIPOS.find((t) => t.id === id) || TERRITORIO_TIPOS[3];
}

export const TERRITORIO_LEGEND = TERRITORIO_TIPOS.filter((t) => t.id !== 'todas').map((t) => ({
  color: t.color,
  label: t.label,
}));
