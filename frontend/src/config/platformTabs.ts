import type { MunicipalityOption } from '@/utils/api';
import { BOOT_PRIORITY_IBGE_CODES } from '@/data/municipalities_seed';

export type ActiveTab =
  | 'dashboard'
  | 'simulation'
  | 'assistant'
  | 'cases'
  | 'contingency'
  | 'monitoring'
  | 'onboarding'
  | 'catalog'
  | 'audit'
  | 'system';

export type LayerQuality = 'Oficial' | 'Referencia' | 'Estimado' | 'Derivado Sinidu+Clima' | 'Observado' | 'Indisponível';

export type LayerOption = {
  id: string;
  label: string;
  group: 'Base' | 'Dados urbanos' | 'Clima e riscos' | 'Planejamento' | 'Saúde e segurança';
  source: string;
  quality: LayerQuality;
  disponivel?: boolean;
  tooltipEstimado?: string;
  descricao?: string;
  count?: number;
  fontesCatalogo?: { id: string; nome: string; descricao_curta?: string }[];
};

export const TAB_ROUTES: Record<ActiveTab, string> = {
  dashboard: '/painel',
  onboarding: '/municipios',
  catalog: '/catalogo',
  simulation: '/simulacoes',
  monitoring: '/monitor',
  contingency: '/contingencia',
  assistant: '/assistente',
  cases: '/casos',
  audit: '/auditoria',
  system: '/sistema',
};

export const ROUTE_TO_TAB: Record<string, ActiveTab> = Object.fromEntries(
  Object.entries(TAB_ROUTES).map(([tab, path]) => [path, tab as ActiveTab]),
) as Record<string, ActiveTab>;

export const DEFAULT_LAYER_OPTIONS: LayerOption[] = [
  { id: 'municipio', label: 'Limite Municipal', group: 'Base', source: 'IBGE / Geocidades', quality: 'Oficial' },
  { id: 'bairros', label: 'Malha de Bairros', group: 'Base', source: 'IBGE Censo 2022 / CTM municipal', quality: 'Oficial' },
  { id: 'territorios_especiais', label: 'Territórios Especiais', group: 'Base', source: 'INCRA / FUNAI / IBGE aglomerados', quality: 'Oficial' },
  { id: 'infraestrutura', label: 'Equipamentos e Redes', group: 'Dados urbanos', source: 'OSM + Pref. Recife / Censo Escolar', quality: 'Referencia' },
  { id: 'educacao', label: 'Educação (INEP)', group: 'Dados urbanos', source: 'INEP Censo Escolar', quality: 'Oficial' },
  { id: 'socioeconomico', label: 'Socioeconômico (IBGE/CTM)', group: 'Dados urbanos', source: 'CTM Recife · clip UCN Pref. + OSM', quality: 'Referencia' },
  { id: 'cobertura', label: 'Uso do Solo', group: 'Clima e riscos', source: 'OSM água/parques/mata · ha MapBiomas', quality: 'Referencia' },
  { id: 'lst_observada', label: 'Temperatura de superfície (LST)', group: 'Clima e riscos', source: 'GeoReDUS / Landsat 8-9', quality: 'Observado' },
  { id: 'vulnerabilidade', label: 'Vulnerabilidade Climática', group: 'Clima e riscos', source: 'Sinidu+Clima · clip UCN Pref. + OSM', quality: 'Derivado Sinidu+Clima' },
  { id: 'inundacao', label: 'Risco de Inundação', group: 'Clima e riscos', source: 'Sinidu+Clima: S2ID + hidrografia', quality: 'Derivado Sinidu+Clima' },
  { id: 'manchas_oficiais', label: 'Manchas Oficiais (validação)', group: 'Clima e riscos', source: 'Defesa Civil / CPRM / plano diretor de drenagem (quando depositado)', quality: 'Oficial' },
  { id: 'risco_consolidado', label: 'Risco consolidado (agora)', group: 'Clima e riscos', source: 'Score Sinidu × alerta · clip UCN Pref.', quality: 'Derivado Sinidu+Clima' },
  { id: 'alertas', label: 'Alertas Ativos (CEMADEN)', group: 'Clima e riscos', source: 'CEMADEN / GeoRiscos', quality: 'Oficial' },
  { id: 'desastres', label: 'Histórico de Desastres (S2ID)', group: 'Clima e riscos', source: 'S2ID / SEDEC', quality: 'Oficial' },
  { id: 'saneamento_drenagem', label: 'Saneamento e Drenagem', group: 'Planejamento', source: 'SNIS oficial + IRI · alinhado ao Plano Diretor', quality: 'Derivado Sinidu+Clima' },
  { id: 'adaptacao_climatica', label: 'Capacidade de Adaptação', group: 'Planejamento', source: 'Adapta Brasil + MapBiomas · Plano Diretor', quality: 'Derivado Sinidu+Clima' },
  { id: 'prioridade_planejamento', label: 'Prioridade de Planejamento', group: 'Planejamento', source: 'Plano Diretor municipal + Score Sinidu+Clima', quality: 'Derivado Sinidu+Clima' },
  { id: 'lacunas_dados', label: 'Lacunas de Dados', group: 'Planejamento', source: 'Radar de Integração Sinidu+Clima', quality: 'Derivado Sinidu+Clima' },
  { id: 'saude_risco', label: 'Saúde × Risco', group: 'Saúde e segurança', source: 'CNES/DataSUS × risco climático', quality: 'Derivado Sinidu+Clima' },
  { id: 'seguranca_publica', label: 'Segurança Pública', group: 'Saúde e segurança', source: 'SINESP / dados.gov.br', quality: 'Estimado' },
  { id: 'vulnerabilidade_multidimensional', label: 'Vulnerabilidade Multidimensional (VM)', group: 'Saúde e segurança', source: 'VM Sinidu+Clima', quality: 'Derivado Sinidu+Clima' },
];

export function mergeMunicipalities(
  seeds: MunicipalityOption[],
  loaded: MunicipalityOption[] | null,
): MunicipalityOption[] {
  const byCode = new Map<string, MunicipalityOption>(
    seeds.map((item) => [item.codigo_ibge, { ...item, loaded: false }]),
  );
  loaded?.forEach((item) => {
    const existing = byCode.get(item.codigo_ibge);
    byCode.set(item.codigo_ibge, {
      ...existing,
      ...item,
      loaded: true,
    });
  });
  const priorityRank = new Map<string, number>(
    BOOT_PRIORITY_IBGE_CODES.map((code, index) => [code, index]),
  );
  return Array.from(byCode.values()).sort((a, b) => {
    const pa = priorityRank.has(a.codigo_ibge) ? priorityRank.get(a.codigo_ibge)! : 999;
    const pb = priorityRank.has(b.codigo_ibge) ? priorityRank.get(b.codigo_ibge)! : 999;
    if (pa !== pb) return pa - pb;
    return a.nome.localeCompare(b.nome, 'pt-BR');
  });
}
