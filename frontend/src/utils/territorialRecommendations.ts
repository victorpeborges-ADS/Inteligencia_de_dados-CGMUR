import type { ActiveTab } from '@/config/platformTabs';
import type {
  ExecutiveDiagnostic,
  ExecutiveIndicators,
  IndicesResponse,
  MunicipalMaturity,
} from '@/utils/api';

export type RecommendationCategory = 'risco' | 'operacao' | 'dados' | 'planejamento' | 'fiscal';
export type RecommendationPriority = 'alta' | 'media' | 'baixa';

export type TerritorialRecommendation = {
  id: string;
  priority: RecommendationPriority;
  priorityScore: number;
  category: RecommendationCategory;
  title: string;
  explanation: string;
  evidence: string[];
  ctaTab?: ActiveTab;
  ctaLabel?: string;
};

export type TerritorialRecommendationsInput = {
  indicators?: ExecutiveIndicators | null;
  indices?: IndicesResponse | null;
  maturity?: MunicipalMaturity | null;
  diagnostic?: ExecutiveDiagnostic | null;
  avgIvc?: number | null;
  avgIri?: number | null;
};

const CATEGORY_LABEL: Record<RecommendationCategory, string> = {
  risco: 'Risco climático',
  operacao: 'Operação',
  dados: 'Maturidade de dados',
  planejamento: 'Planejamento',
  fiscal: 'Capacidade fiscal',
};

export function recommendationCategoryLabel(category: RecommendationCategory): string {
  return CATEGORY_LABEL[category];
}

function priorityFromScore(score: number): RecommendationPriority {
  if (score >= 80) return 'alta';
  if (score >= 50) return 'media';
  return 'baixa';
}

function topBairro(
  indices: IndicesResponse | null | undefined,
  key: 'vulnerabilidade' | 'inundacao',
): string | null {
  if (!indices) return null;
  if (key === 'vulnerabilidade') {
    const row = [...indices.vulnerabilidade].sort(
      (a, b) => b.indice_vulnerabilidade - a.indice_vulnerabilidade,
    )[0];
    return row?.bairro_nome ?? null;
  }
  const row = [...indices.inundacao].sort(
    (a, b) => b.indice_risco_inundacao - a.indice_risco_inundacao,
  )[0];
  return row?.bairro_nome ?? null;
}

function pushRecommendation(
  list: TerritorialRecommendation[],
  rec: Omit<TerritorialRecommendation, 'priority'> & { priorityScore: number },
) {
  if (list.some((item) => item.id === rec.id)) return;
  list.push({
    ...rec,
    priority: priorityFromScore(rec.priorityScore),
  });
}

export function buildTerritorialRecommendations(
  input: TerritorialRecommendationsInput,
): TerritorialRecommendation[] {
  const { indicators, indices, maturity, diagnostic } = input;
  const avgIvc = input.avgIvc ?? indicators?.media_ivc ?? null;
  const avgIri = input.avgIri ?? indicators?.media_iri ?? null;
  const alertas = indicators?.alertas_ativos_count ?? 0;
  const desastres = indicators?.historico_desastres_count ?? 0;
  const score = indicators?.score_sinidu;
  const cobertura = indicators?.cobertura_vegetal_percent;
  const capag = indicators?.nota_capag?.toUpperCase();
  const conf = (indicators?.score_confiabilidade || indicators?.confiabilidade_geral || '').toUpperCase();
  const topVuln = topBairro(indices, 'vulnerabilidade');
  const topFlood = topBairro(indices, 'inundacao');

  const out: TerritorialRecommendation[] = [];

  if (alertas >= 20) {
    pushRecommendation(out, {
      id: 'cemaden-critico',
      priorityScore: 120,
      category: 'operacao',
      title: 'Ativar sala de situação — alertas CEMADEN elevados',
      explanation:
        'Volume de alertas oficiais indica pressão operacional imediata. Cruze camadas de inundação e monte contingência.',
      evidence: [`${alertas} alertas CEMADEN ativos`, 'Fonte: monitoramento oficial GeoRiscos'],
      ctaTab: 'contingency',
      ctaLabel: 'Abrir contingência',
    });
  } else if (alertas >= 1) {
    pushRecommendation(out, {
      id: 'cemaden-ativo',
      priorityScore: alertas >= 5 ? 100 : 85,
      category: 'operacao',
      title: 'Acompanhar alertas CEMADEN no monitor',
      explanation:
        'Há alertas ativos no município. Valide áreas afetadas no mapa antes de acionar Defesa Civil.',
      evidence: [`${alertas} alerta(s) ativo(s)`, topFlood ? `Maior IRI: ${topFlood}` : 'Cruzar camada de inundação'],
      ctaTab: 'monitoring',
      ctaLabel: 'Ver monitor',
    });
  }

  if (avgIri != null && avgIri >= 0.5) {
    pushRecommendation(out, {
      id: 'simular-inundacao',
      priorityScore: avgIri >= 0.65 ? 95 : 55,
      category: 'risco',
      title: 'Simular chuva extrema e inspecionar profundidade 3D',
      explanation:
        'IRI municipal elevado indica exposição a alagamentos. Cenário de 120 mm libera volume no terreno 3D.',
      evidence: [
        `IRI médio ${Math.round(avgIri * 100)} (escala 0–100)`,
        topFlood ? `Bairro mais exposto: ${topFlood}` : 'Malha de bairros disponível',
      ],
      ctaTab: 'simulation',
      ctaLabel: 'Ir para simulações',
    });
  }

  if (avgIvc != null && avgIvc >= 0.5) {
    pushRecommendation(out, {
      id: 'adaptacao-vulnerabilidade',
      priorityScore: avgIvc >= 0.65 ? 90 : 50,
      category: 'risco',
      title: 'Priorizar adaptação nos bairros de maior vulnerabilidade',
      explanation:
        'IVC alto combina exposição climática, renda e capacidade adaptativa reduzida — foco para investimento.',
      evidence: [
        `IVC médio ${Math.round(avgIvc * 100)}`,
        topVuln ? `Prioridade: ${topVuln}` : 'Consultar ranking no mapa',
      ],
      ctaTab: 'simulation',
      ctaLabel: 'Simular intervenções',
    });
  }

  if (score != null && score >= 50) {
    pushRecommendation(out, {
      id: 'score-elevado',
      priorityScore: score >= 70 ? 88 : 62,
      category: 'planejamento',
      title: 'Consolidar plano de ação territorial',
      explanation:
        'Score Sinidu+Clima composto indica prioridade elevada. Gere diagnóstico executivo e plano de mitigação.',
      evidence: [`Score ${Math.round(score)} (0–100)`, 'Integra IVC, IRI, desastres e maturidade'],
      ctaTab: 'assistant',
      ctaLabel: 'Consultar assistente',
    });
  }

  if (!diagnostic?.headline && !diagnostic?.narrativa_md) {
    pushRecommendation(out, {
      id: 'gerar-diagnostico',
      priorityScore: 75,
      category: 'planejamento',
      title: 'Gerar diagnóstico executivo com narrativa IA',
      explanation:
        'Sem diagnóstico salvo, a narrativa institucional fica limitada. Use a Central da Oficina no mapa.',
      evidence: ['Nenhum diagnóstico executivo registrado hoje', 'Inclui headline, ranking e camadas sugeridas'],
    });
  }

  if (maturity && (maturity.classificacao === 'Bronze' || maturity.score < 26)) {
    const lacuna = maturity.fontes_faltantes[0];
    pushRecommendation(out, {
      id: 'elevar-maturidade',
      priorityScore: 70,
      category: 'dados',
      title: 'Elevar maturidade antes de relatórios oficiais',
      explanation:
        'Classificação Bronze restringe PDF completo e reduz confiabilidade do score. Integre fontes prioritárias.',
      evidence: [
        `Maturidade ${Math.round(maturity.score)}% · ${maturity.classificacao}`,
        lacuna ? `Lacuna: ${lacuna.nome}` : `${maturity.fontes_faltantes.length} fonte(s) pendente(s)`,
      ],
      ctaTab: 'catalog',
      ctaLabel: 'Ver catálogo',
    });
  } else if (maturity?.fontes_faltantes?.length) {
    const lacuna = maturity.fontes_faltantes[0];
    pushRecommendation(out, {
      id: 'integrar-fonte',
      priorityScore: 38,
      category: 'dados',
      title: `Integrar fonte prioritária: ${lacuna.nome}`,
      explanation: lacuna.recomendacao || 'Fonte ausente impacta confiabilidade territorial.',
      evidence: [`${maturity.fontes_faltantes.length} lacuna(s) catalogada(s)`, `Impacto estimado no score`],
      ctaTab: 'catalog',
      ctaLabel: 'Radar de integração',
    });
  }

  if (capag === 'C' || capag === 'D') {
    pushRecommendation(out, {
      id: 'capag-restricao',
      priorityScore: 65,
      category: 'fiscal',
      title: 'Validar restrições CAPAG em projetos com contrapartida',
      explanation:
        'Nota C ou D sinaliza alerta fiscal — relevante para operações com garantia da União (FGTS / Pro-Cidades).',
      evidence: [`CAPAG ${capag}`, indicators?.capag_fonte ? `Fonte: ${indicators.capag_fonte}` : 'Tesouro Transparente'],
    });
  }

  if (desastres >= 3) {
    pushRecommendation(out, {
      id: 'historico-desastres',
      priorityScore: desastres >= 8 ? 68 : 58,
      category: 'operacao',
      title: 'Revisar histórico S2ID e casos de referência',
      explanation:
        'Eventos registrados reforçam necessidade de contingência estruturada e lições de outros municípios.',
      evidence: [`${desastres} evento(s) no S2ID`, 'Cruzar camada de desastres no mapa'],
      ctaTab: 'cases',
      ctaLabel: 'Ver casos',
    });
  }

  if (cobertura != null && cobertura < 25) {
    pushRecommendation(out, {
      id: 'cobertura-vegetal',
      priorityScore: 45,
      category: 'risco',
      title: 'Avaliar perda de cobertura vegetal e ilhas de calor',
      explanation:
        'Baixa cobertura vegetal aumenta sensibilidade a ondas de calor urbano — simule cenário térmico.',
      evidence: [`Cobertura vegetal ~${Math.round(cobertura)}%`, 'Fonte: MapBiomas / partição espacial'],
      ctaTab: 'simulation',
      ctaLabel: 'Simular calor',
    });
  }

  if (conf && conf !== 'ALTA' && conf !== 'MEDIA') {
    pushRecommendation(out, {
      id: 'confiabilidade-baixa',
      priorityScore: 40,
      category: 'dados',
      title: 'Interpretar score com cautela — dados parciais',
      explanation:
        'Confiabilidade abaixo do ideal. Priorize integração de fontes oficiais antes de decisões de investimento.',
      evidence: [`Confiabilidade: ${conf}`, 'Consulte selos por indicador no painel'],
      ctaTab: 'catalog',
      ctaLabel: 'Ver lacunas',
    });
  }

  if (!out.length) {
    pushRecommendation(out, {
      id: 'explorar-territorio',
      priorityScore: 30,
      category: 'planejamento',
      title: 'Explorar camadas e gerar baseline territorial',
      explanation:
        'Indicadores dentro de faixa moderada. Ative camadas de risco e compare com municípios similares.',
      evidence: ['Nenhum gatilho crítico detectado', 'Use Modo Focus (F) em apresentações'],
      ctaTab: 'simulation',
      ctaLabel: 'Explorar simulações',
    });
  }

  return out
    .sort((a, b) => b.priorityScore - a.priorityScore)
    .slice(0, 5);
}
