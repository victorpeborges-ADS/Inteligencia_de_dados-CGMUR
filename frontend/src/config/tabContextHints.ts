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
    body: 'Consulte maturidade por fonte (IBGE, S2ID, CEMADEN…) e identifique lacunas antes de exportar relatórios para decisão municipal.',
    ctaTab: 'dashboard',
    ctaLabel: 'Ver painel',
  },
  simulation: {
    title: 'Onde alaga se chover forte?',
    body: 'Escolha um volume de chuva (ou TR) e rode. Resultado = estimativa territorial (selo Derivado/Estimado) — não é metodologia oficial ANA/CEMADEN/CPRM nem laudo. Leia o painel de limites e a nota metodológica.',
    ctaTab: 'contingency',
    ctaLabel: 'Plano de contingência',
  },
  monitoring: {
    title: 'Monitor operacional',
    body: 'Alertas CEMADEN em tempo real. Em Laranja/Vermelho, abra a contingência. O score Sinidu é triagem — não substitui o alerta oficial.',
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
    title: 'Agente Sinidu · Modo Normativo',
    body: 'Legislação e RAG (Lei 12.608, COBRADE, manuais). Dados operacionais do município ficam no FAB Agente Sinidu · Operacional (canto inferior direito).',
  },
  cases: {
    title: 'Casos de referência',
    body: 'Compare experiências de outros municípios e adapte medidas ao contexto local via busca semântica.',
  },
  audit: {
    title: 'Auditoria',
    body: 'Rastreie geração de PDFs, diagnósticos e comparações — útil para prestação de contas e revisão interna (não confunde com homologação de metodologia de engenharia).',
  },
  system: {
    title: 'Sistema',
    body: 'Jobs de pipeline, DEM e MapBiomas. Use apenas em ambiente administrativo.',
  },
};

export const TAB_HINT_STORAGE_PREFIX = 'sinidu-tab-hint-dismissed-';
