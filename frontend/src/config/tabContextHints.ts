import type { ActiveTab } from '@/config/platformTabs';

export type TabContextHintConfig = {
  title: string;
  body: string;
  ctaTab?: ActiveTab;
  ctaLabel?: string;
};

export const TAB_CONTEXT_HINTS: Partial<Record<ActiveTab, TabContextHintConfig>> = {
  dashboard: {
    title: 'Painel executivo',
    body: 'Leia a narrativa, siga as recomendações territoriais (prioridade + evidências) e exporte PDF quando a maturidade for Prata ou superior.',
    ctaTab: 'simulation',
    ctaLabel: 'Simular cenário',
  },
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
    title: 'Onde alaga se chover forte?',
    body: 'Escolha um volume de chuva (ou TR) e rode. O selo de confiança e a nota metodológica explicam o que o modelo pode (e não pode) afirmar.',
    ctaTab: 'contingency',
    ctaLabel: 'Plano de contingência',
  },
  monitoring: {
    title: 'Monitor operacional',
    body: 'Alertas CEMADEN em tempo real. Em Laranja/Vermelho, abra a contingência e siga o protocolo de campo.',
    ctaTab: 'contingency',
    ctaLabel: 'Abrir contingência',
  },
  contingency: {
    title: 'Do alerta à ação de campo',
    body: 'Defina zonas, abrigos, contatos 24h e recursos. O protocolo COBRADE diz quem faz o quê em cada nível de alerta.',
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
