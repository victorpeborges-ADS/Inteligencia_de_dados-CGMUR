export type SocioSubcamadaId =
  | 'renda'
  | 'arborizacao'
  | 'calcada'
  | 'iluminacao'
  | 'agua'
  | 'esgoto'
  | 'lixo'
  | 'alfabetizacao';

export type SocioSubcamada = {
  id: SocioSubcamadaId;
  label: string;
  description: string;
  unit: string;
  legend: { color: string; label: string }[];
};

export const SOCIO_SUBCAMADAS: SocioSubcamada[] = [
  {
    id: 'renda',
    label: 'Renda relativa',
    description: 'Tercis de renda média por setor censitário (IBGE).',
    unit: 'classe',
    legend: [
      { color: '#22c55e', label: 'Renda alta (terço superior)' },
      { color: '#eab308', label: 'Renda média (terço médio)' },
      { color: '#f97316', label: 'Renda baixa (terço inferior)' },
    ],
  },
  {
    id: 'arborizacao',
    label: 'Arborização ausente',
    description: 'Domicílios em vias sem árvores no entorno (Censo 2022 / PUE).',
    unit: '%',
    legend: [
      { color: '#14532d', label: 'Baixo déficit (<15%)' },
      { color: '#84cc16', label: 'Médio (15–35%)' },
      { color: '#facc15', label: 'Alto (>35%)' },
    ],
  },
  {
    id: 'calcada',
    label: 'Calçada ausente',
    description: 'Domicílios sem calçada ou passeio no entorno (Censo 2022 / PUE).',
    unit: '%',
    legend: [
      { color: '#1e3a8a', label: 'Baixo déficit (<15%)' },
      { color: '#60a5fa', label: 'Médio (15–35%)' },
      { color: '#f97316', label: 'Alto (>35%)' },
    ],
  },
  {
    id: 'iluminacao',
    label: 'Iluminação ausente',
    description: 'Domicílios sem iluminação pública no entorno (Censo 2022 / PUE).',
    unit: '%',
    legend: [
      { color: '#312e81', label: 'Baixo déficit (<5%)' },
      { color: '#a78bfa', label: 'Médio (5–15%)' },
      { color: '#ef4444', label: 'Alto (>15%)' },
    ],
  },
  {
    id: 'agua',
    label: 'Água sem rede',
    description: 'Domicílios sem ligação à rede geral de água (Censo 2022).',
    unit: '%',
    legend: [
      { color: '#0c4a6e', label: 'Baixo déficit (<5%)' },
      { color: '#38bdf8', label: 'Médio (5–15%)' },
      { color: '#dc2626', label: 'Alto (>15%)' },
    ],
  },
  {
    id: 'esgoto',
    label: 'Esgoto inadequado',
    description: 'Domicílios com esgotamento sanitário inadequado (Censo 2022).',
    unit: '%',
    legend: [
      { color: '#134e4a', label: 'Baixo déficit (<10%)' },
      { color: '#2dd4bf', label: 'Médio (10–25%)' },
      { color: '#b91c1c', label: 'Alto (>25%)' },
    ],
  },
  {
    id: 'lixo',
    label: 'Lixo sem coleta',
    description: 'Domicílios com destino inadequado de lixo (Censo 2022).',
    unit: '%',
    legend: [
      { color: '#3f3f46', label: 'Baixo déficit (<3%)' },
      { color: '#a1a1aa', label: 'Médio (3–8%)' },
      { color: '#ea580c', label: 'Alto (>8%)' },
    ],
  },
  {
    id: 'alfabetizacao',
    label: 'Baixa alfabetização',
    description: 'Complemento da taxa de alfabetização (15+) no município, calibrado por setor.',
    unit: '%',
    legend: [
      { color: '#4c1d95', label: 'Baixo (<5%)' },
      { color: '#c084fc', label: 'Médio (5–12%)' },
      { color: '#be123c', label: 'Alto (>12%)' },
    ],
  },
];

export const DEFAULT_SOCIO_SUBCAMADA: SocioSubcamadaId = 'renda';

export function getSocioSubcamada(id: SocioSubcamadaId): SocioSubcamada {
  return SOCIO_SUBCAMADAS.find((s) => s.id === id) ?? SOCIO_SUBCAMADAS[0];
}
