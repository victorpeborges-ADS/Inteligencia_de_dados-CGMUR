import type { ActiveTab } from '@/config/platformTabs';

export type TabContextHintConfig = {
  title: string;
  body: string;
  ctaTab?: ActiveTab;
  ctaLabel?: string;
};

export const TAB_CONTEXT_HINTS: Partial<Record<ActiveTab, TabContextHintConfig>> = {
  onboarding: {
    title: 'Integração municipal',
    body: 'Valide o município e execute o onboarding para liberar malha de bairros, MapBiomas e score Sinidu+Clima.',
  },
  catalog: {
    title: 'Catálogo de dados',
    body: 'Consulte maturidade por fonte (IBGE, S2ID, CEMADEN…) e identifique lacunas antes de relatórios oficiais.',
    ctaTab: 'dashboard',
    ctaLabel: 'Ver painel',
  },
  simulation: {
    title: 'Simulações territoriais',
    body: 'Chuva extrema (120 mm) ativa volume 3D no mapa. Após rodar, use o card “Próximos passos” e Modo Focus (F).',
    ctaTab: 'contingency',
    ctaLabel: 'Plano de contingência',
  },
  monitoring: {
    title: 'Monitor operacional',
    body: 'Alertas CEMADEN em tempo real. Ative contingência direto da timeline quando o nível subir para Laranja/Vermelho.',
    ctaTab: 'contingency',
    ctaLabel: 'Abrir contingência',
  },
  contingency: {
    title: 'Contingência e Defesa Civil',
    body: 'Monte rotas, abrigos e comunicação a partir de simulações ou alertas. Exporte o plano para operação.',
    ctaTab: 'simulation',
    ctaLabel: 'Simular cenário',
  },
  assistant: {
    title: 'Assistente municipal',
    body: 'Pergunte com o IBGE selecionado — respostas citam fontes oficiais (IBGE, S2ID, CAPAG). Ideal para dúvidas pontuais.',
  },
  cases: {
    title: 'Casos de referência',
    body: 'Compare experiências de outros municípios e adapte medidas ao contexto local via busca semântica.',
  },
  audit: {
    title: 'Auditoria',
    body: 'Rastreie geração de PDFs, diagnósticos e comparações — útil para homologação MCID e prestação de contas.',
  },
  system: {
    title: 'Sistema',
    body: 'Jobs de pipeline, DEM e MapBiomas. Use apenas em ambiente administrativo.',
  },
};

export const TAB_HINT_STORAGE_PREFIX = 'sinidu-tab-hint-dismissed-';
