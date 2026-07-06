'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';

import { ROUTE_TO_TAB, TAB_ROUTES, type ActiveTab } from '@/config/platformTabs';
import { api } from '@/utils/api';
import { useAppStore } from '@/stores/useAppStore';

export type PageContext = {
  pagina: string;
  descricao: string;
  dados_disponiveis: string[];
  perguntas_sugeridas: string[];
};

const PAGE_CONTEXTS: Record<string, PageContext> = {
  '/painel': {
    pagina: 'Painel Principal',
    descricao: 'Visão geral do município com mapa, camadas espaciais e Central da Oficina',
    dados_disponiveis: ['score_sinidu', 'diagnostico_atual', 'camadas_ativas', 'plano_acao'],
    perguntas_sugeridas: [
      'O que significa o Score Sinidu?',
      'Por que alguns bairros são prioritários?',
      'Como interpretar as camadas socioeconômicas?',
    ],
  },
  '/simulacoes': {
    pagina: 'Simulações Territoriais',
    descricao: 'Modelo pluvial v2.3 com DEM SRTM, manchas de inundação e zonas de deslizamento',
    dados_disponiveis: ['parametros_simulacao', 'resultado_manchas', 'zonas_deslizamento'],
    perguntas_sugeridas: [
      'O que são as manchas por profundidade?',
      'Como interpretar os vetores D8?',
      'Qual o risco real de 120mm neste município?',
    ],
  },
  '/monitor': {
    pagina: 'Monitoramento Operacional',
    descricao: 'Alertas CEMADEN em tempo real, precipitação e risco atual',
    dados_disponiveis: ['alertas_cemaden', 'precipitacao_24h', 'risco_atual', 'probabilidade_critico'],
    perguntas_sugeridas: [
      'O que significa risco AMARELO?',
      'Quantos alertas CEMADEN é crítico?',
      'O que fazer quando o risco for LARANJA?',
    ],
  },
  '/catalogo': {
    pagina: 'Catálogo de Dados',
    descricao: 'Maturidade informacional e status de integração das fontes de dados',
    dados_disponiveis: ['maturidade_pct', 'fontes_status', 'lacunas'],
    perguntas_sugeridas: [
      'Por que o GeoSGB está "Em Integração"?',
      'O que significa a maturidade informacional?',
      'Quais lacunas impactam mais o Score?',
    ],
  },
  '/contingencia': {
    pagina: 'Contingência COBRADE',
    descricao: 'Planos de resposta, zonas de evacuação e rotas',
    dados_disponiveis: ['planos_ativos', 'zonas_evacuacao', 'pontos_apoio'],
    perguntas_sugeridas: [
      'Como ativar um plano de contingência?',
      'O que é COBRADE?',
      'Quais bairros têm maior prioridade de evacuação?',
    ],
  },
  '/auditoria': {
    pagina: 'Trilha de Auditoria',
    descricao: 'Registro de ações: PDFs gerados, exports SEI, ativações de contingência',
    dados_disponiveis: ['logs_acoes'],
    perguntas_sugeridas: [
      'Como registrar uma ação na trilha?',
      'O que é export SEI?',
      'Quais ações aparecem no histórico?',
    ],
  },
  '/municipios': {
    pagina: 'Municípios',
    descricao: 'Onboarding, carga de dados e status de integração municipal',
    dados_disponiveis: ['status_carga', 'malha_territorial', 'integracoes'],
    perguntas_sugeridas: [
      'Como recarregar dados reais do município?',
      'O que significa confiabilidade BAIXA?',
      'Como melhorar a malha de bairros?',
    ],
  },
  '/assistente': {
    pagina: 'Assistente Municipal',
    descricao: 'Chat completo com RAG normativo e contexto municipal',
    dados_disponiveis: ['rag_normativo', 'contexto_municipal', 'casos_sucesso'],
    perguntas_sugeridas: [
      'Qual a nota CAPAG deste município?',
      'Quais bairros têm maior risco?',
      'O que diz a legislação sobre PDDU?',
    ],
  },
  '/casos': {
    pagina: 'Casos de Sucesso',
    descricao: 'Base de conhecimento com busca semântica de intervenções urbanas verificáveis',
    dados_disponiveis: ['casos_sucesso', 'busca_semantica', 'adaptacao_ia'],
    perguntas_sugeridas: [
      'Quais casos de drenagem são similares ao meu município?',
      'Como adaptar piscinões para cidade menor?',
      'Quais programas financiaram encostas no Sudeste?',
    ],
  },
};

const DEFAULT_CONTEXT: PageContext = {
  pagina: 'Sinidu+Clima',
  descricao: 'Plataforma de inteligência territorial e gestão de risco urbano',
  dados_disponiveis: ['score_sinidu', 'camadas_ativas'],
  perguntas_sugeridas: [
    'Como usar o mapa de camadas?',
    'O que é o Score Sinidu?',
    'Como gerar um diagnóstico?',
  ],
};

function resolvePath(pathname: string): string {
  const tab = ROUTE_TO_TAB[pathname];
  if (tab) return TAB_ROUTES[tab];
  if (PAGE_CONTEXTS[pathname]) return pathname;
  return '/painel';
}

export function useAgenteContexto() {
  const pathname = usePathname() || '/painel';
  const routeKey = resolvePath(pathname);
  const selectedMunicipio = useAppStore((s) => s.selectedMunicipio);
  const activeTab = useAppStore((s) => s.activeTab);
  const activeLayers = useAppStore((s) => s.activeLayers);
  const alertNivel = useAppStore((s) => s.alertNivel);
  const municipalities = useAppStore((s) => s.municipalities);

  const [dadosPagina, setDadosPagina] = useState<Record<string, unknown>>({});
  const [loadingDados, setLoadingDados] = useState(false);

  const pageContext = useMemo(
    () => PAGE_CONTEXTS[routeKey] || DEFAULT_CONTEXT,
    [routeKey],
  );

  const municipioMeta = useMemo(
    () => municipalities.find((m) => m.codigo_ibge === selectedMunicipio),
    [municipalities, selectedMunicipio],
  );

  const municipioNome = municipioMeta
    ? `${municipioMeta.nome}/${municipioMeta.uf}`
    : selectedMunicipio;

  const refreshDadosPagina = useCallback(async () => {
    if (!selectedMunicipio) return;
    setLoadingDados(true);
    const base: Record<string, unknown> = {
      aba_ativa: activeTab,
      camadas_ativas: activeLayers,
      alert_nivel: alertNivel,
    };
    try {
      if (routeKey === '/painel' || activeTab === 'dashboard') {
        const [exec, plan] = await Promise.all([
          api.getExecutiveIndicators(selectedMunicipio).catch(() => null),
          api.getActionPlan(selectedMunicipio).catch(() => null),
        ]);
        setDadosPagina({
          ...base,
          score_sinidu: exec?.score_sinidu,
          media_ivc: exec?.media_ivc,
          media_iri: exec?.media_iri,
          score_confiabilidade: exec?.score_confiabilidade,
          confiabilidade_geral: exec?.confiabilidade_geral,
          alertas_ativos: exec?.alertas_ativos_count,
          plano_acao_disponivel: Boolean(plan),
        });
      } else if (routeKey === '/monitor' || activeTab === 'monitoring') {
        const dash = await api.getMonitoringDashboard(selectedMunicipio).catch(() => null);
        setDadosPagina({
          ...base,
          nivel_risco: dash?.nivel_risco_atual,
          cemaden_ativos: dash?.cemaden_ativos,
          precip_24h_mm: dash?.precip_24h_mm,
          risk_probability: dash?.risk_probability,
        });
      } else if (routeKey === '/catalogo' || activeTab === 'catalog') {
        const cov = await api.getDataCoverage(selectedMunicipio).catch(() => null);
        setDadosPagina({
          ...base,
          maturidade_percentual: cov?.maturidade_percentual,
          classificacao: cov?.classificacao,
          lacunas: cov?.lacunas_prioritarias?.map((l: { nome?: string }) => l.nome).slice(0, 5),
        });
      } else if (routeKey === '/simulacoes' || activeTab === 'simulation') {
        setDadosPagina({
          ...base,
          modelo: 'pluvial_v2.3',
          precipitacao_padrao_mm: 120,
          glossario_camadas: {
            vetores_d8:
              'Setas de direção de escoamento (algoritmo D8): indicam para onde a água flui célula a célula no DEM. Concentram-se em vales e drenagens naturais.',
            manchas_profundidade:
              'Polígonos de alagamento por faixa de profundidade estimada (m), derivados do volume pluvial e declividade.',
            curvas_nivel: 'Isolinhas de cota altimétrica (m) do terreno.',
            zonas_deslizamento:
              'Encostas com inclinação elevada e suscetibilidade a movimentos de massa sob chuva intensa (COBRADE).',
          },
        });
      } else if (routeKey === '/casos' || activeTab === 'cases') {
        const search = await api
          .searchCasesSemantic({
            query: municipioMeta
              ? `adaptação climática ${municipioMeta.nome} ${municipioMeta.uf}`
              : 'drenagem encosta habitação',
            municipio_codigo: selectedMunicipio,
            top_k: 5,
          })
          .catch(() => null);
        setDadosPagina({
          ...base,
          casos_encontrados: search?.items?.length || 0,
          casos_top: search?.items?.slice(0, 3).map((c) => ({
            id: c.id,
            titulo: c.titulo,
            municipio: `${c.municipio_nome}/${c.municipio_uf}`,
            tipo: c.tipo_intervencao,
          })),
          search_mode: search?.search_mode,
        });
      } else {
        setDadosPagina(base);
      }
    } catch {
      setDadosPagina(base);
    } finally {
      setLoadingDados(false);
    }
  }, [activeTab, activeLayers, alertNivel, routeKey, selectedMunicipio, municipioMeta]);

  useEffect(() => {
    refreshDadosPagina();
  }, [refreshDadosPagina]);

  const perguntasContextuais = useMemo(() => {
    const sugestoes = [...pageContext.perguntas_sugeridas];
    const score = dadosPagina.score_sinidu;
    if (routeKey === '/painel' && typeof score === 'number') {
      sugestoes[0] = `O que significa Score ${score}?`;
    }
    const cemaden = dadosPagina.cemaden_ativos;
    if (routeKey === '/monitor' && typeof cemaden === 'number') {
      sugestoes[0] = `${cemaden} alertas é crítico?`;
    }
    return sugestoes.slice(0, 3);
  }, [dadosPagina, pageContext.perguntas_sugeridas, routeKey]);

  return {
    pathname,
    routeKey,
    activeTab: activeTab as ActiveTab,
    pageContext,
    municipioCodigo: selectedMunicipio,
    municipioNome,
    dadosPagina,
    loadingDados,
    refreshDadosPagina,
    perguntasContextuais,
  };
}

export function useAgenteProativo() {
  const selectedMunicipio = useAppStore((s) => s.selectedMunicipio);
  const activeTab = useAppStore((s) => s.activeTab);
  const pushAgenteProativo = useAppStore((s) => s.pushAgenteProativo);
  const setAgenteAberto = useAppStore((s) => s.setAgenteAberto);
  const hasProactiveShown = useAppStore((s) => s.hasProactiveShown);
  const markProactiveShown = useAppStore((s) => s.markProactiveShown);
  const municipalities = useAppStore((s) => s.municipalities);

  useEffect(() => {
    if (!selectedMunicipio || selectedMunicipio === '2611606') return;
    const key = `muni-${selectedMunicipio}`;
    if (hasProactiveShown(key)) return;

    let cancelled = false;
    (async () => {
      try {
        const exec = await api.getExecutiveIndicators(selectedMunicipio);
        if (cancelled) return;
        const conf = exec.score_confiabilidade || 'ESTIMADO';
        if (conf === 'ALTA') return;
        const nome = municipalities.find((m) => m.codigo_ibge === selectedMunicipio)?.nome || selectedMunicipio;
        const pct = exec.confiabilidade_geral === 'ALTA' ? 80 : conf === 'MEDIA' ? 55 : 35;
        pushAgenteProativo(
          `⚠️ Atenção: **${nome}** tem dados parciais. O Score **${exec.score_sinidu ?? '?'}** foi calculado com ~${pct}% de dados verificáveis. Recomendo interpretar com cautela.`,
        );
        setAgenteAberto(true);
        markProactiveShown(key);
      } catch {
        /* silencioso */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedMunicipio, municipalities, pushAgenteProativo, setAgenteAberto, hasProactiveShown, markProactiveShown]);

  useEffect(() => {
    if (activeTab !== 'monitoring' || !selectedMunicipio) return;
    const key = `monitor-${selectedMunicipio}`;
    if (hasProactiveShown(key)) return;

    let cancelled = false;
    (async () => {
      try {
        const dash = await api.getMonitoringDashboard(selectedMunicipio);
        if (cancelled) return;
        if ((dash.cemaden_ativos || 0) <= 20) return;
        const nome = dash.nome_municipio || selectedMunicipio;
        const prob = dash.risk_probability != null ? Math.round(dash.risk_probability * 100) : '?';
        pushAgenteProativo(
          `🔴 **${dash.cemaden_ativos}** alertas CEMADEN ativos para **${nome}** nas últimas 24h. Probabilidade de evento crítico: **${prob}%**. Deseja que eu explique o que fazer?`,
        );
        markProactiveShown(key);
      } catch {
        /* silencioso */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeTab, selectedMunicipio, pushAgenteProativo, hasProactiveShown, markProactiveShown]);
}
