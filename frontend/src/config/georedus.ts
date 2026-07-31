/** Referência externa GeoReDUS (ReDUS / CEM-USP / FNP) — Fase 16a */

export const GEOREDUS_BASE_URL = 'https://www.redus.org.br/georedus';

export function georedusMunicipioUrl(codigoIbge: string): string {
  const code = codigoIbge.padStart(7, '0').slice(0, 7);
  return `${GEOREDUS_BASE_URL}?v=v0&municipioId=${code}`;
}

export type GeoReDusExternalIndicator = {
  id: string;
  label: string;
  group: string;
  source: string;
  keywords: string[];
  description: string;
};

/** Indicadores disponíveis no GeoReDUS mas ainda não integrados como camada Sinidu */
export const GEOREDUS_EXTERNAL_INDICATORS: GeoReDusExternalIndicator[] = [
  {
    id: 'georedus_censo_infra',
    label: 'Déficits domiciliares (Censo 2022)',
    group: 'Dados urbanos',
    source: 'GeoReDUS / IBGE',
    keywords: ['censo', 'domicílio', 'arborização', 'calçada', 'iluminação', 'saneamento', 'água', 'esgoto'],
    description: 'Indicadores de infraestrutura domiciliar por setor censitário.',
  },
  {
    id: 'georedus_inep',
    label: 'Matrículas escolares (INEP)',
    group: 'Dados urbanos',
    source: 'GeoReDUS / INEP',
    keywords: ['inep', 'educação', 'escola', 'matrícula', 'creche', 'fundamental', 'médio'],
    description: 'Matrículas por etapa de ensino com visualização intramunicipal.',
  },
  {
    id: 'georedus_saude',
    label: 'Equipamentos de saúde',
    group: 'Saúde e segurança',
    source: 'GeoReDUS / CNES',
    keywords: ['saúde', 'ubs', 'hospital', 'ambulatório', 'cnes'],
    description: 'Hospitais, UBS e ambulatórios georreferenciados.',
  },
  {
    id: 'georedus_territorios',
    label: 'Quilombos, TIs e comunidades urbanas',
    group: 'Base',
    source: 'GeoReDUS / bases oficiais',
    keywords: ['quilombo', 'terra indígena', 'ti', 'favela', 'comunidade', 'periferia'],
    description: 'Integrado no Sinidu como camada Territórios Especiais — consulte também o GeoReDUS nacional.',
  },
];

export function matchGeoReDusIndicators(query: string): GeoReDusExternalIndicator[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return GEOREDUS_EXTERNAL_INDICATORS.filter((item) => {
    const haystack = [
      item.label,
      item.group,
      item.source,
      item.description,
      ...item.keywords,
    ]
      .join(' ')
      .toLowerCase();
    return haystack.includes(q);
  });
}

export function matchLayerOption(
  query: string,
  layer: { id: string; label: string; group: string; source: string },
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [layer.id, layer.label, layer.group, layer.source].join(' ').toLowerCase();
  return haystack.includes(q);
}
