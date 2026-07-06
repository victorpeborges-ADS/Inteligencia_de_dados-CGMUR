import type {
  ExecutiveDiagnostic,
  ExecutiveIndicators,
  IndicesResponse,
  MunicipalMaturity,
} from '@/utils/api';

export type ExecutiveNarrativeInput = {
  municipioNome?: string;
  uf?: string;
  codigoIbge?: string;
  indicators?: ExecutiveIndicators | null;
  indices?: IndicesResponse | null;
  maturity?: MunicipalMaturity | null;
  diagnostic?: ExecutiveDiagnostic | null;
  avgIvc?: number | null;
  avgIri?: number | null;
};

export type ExecutiveNarrativeResult = {
  paragraphs: string[];
  bullets: string[];
  source: 'diagnostic_ia' | 'diagnostic_headline' | 'generated';
};

function topBairros(
  indices: IndicesResponse | null | undefined,
  key: 'vulnerabilidade' | 'inundacao',
  limit = 2,
): string[] {
  if (!indices) return [];
  if (key === 'vulnerabilidade') {
    return [...indices.vulnerabilidade]
      .sort((a, b) => b.indice_vulnerabilidade - a.indice_vulnerabilidade)
      .slice(0, limit)
      .map((row) => row.bairro_nome);
  }
  return [...indices.inundacao]
    .sort((a, b) => b.indice_risco_inundacao - a.indice_risco_inundacao)
    .slice(0, limit)
    .map((row) => row.bairro_nome);
}

function scorePriority(score: number): string {
  if (score >= 70) return 'prioridade muito alta';
  if (score >= 50) return 'prioridade alta';
  if (score >= 30) return 'prioridade moderada';
  return 'prioridade de acompanhamento';
}

export function buildExecutiveNarrative(input: ExecutiveNarrativeInput): ExecutiveNarrativeResult {
  const iaParagraphs = input.diagnostic?.narrativa_ia_meta?.paragrafos?.filter(Boolean);
  if (iaParagraphs?.length) {
    return {
      paragraphs: iaParagraphs,
      bullets: [],
      source: 'diagnostic_ia',
    };
  }

  if (input.diagnostic?.headline) {
    return {
      paragraphs: [input.diagnostic.headline],
      bullets: [],
      source: 'diagnostic_headline',
    };
  }

  const nome = input.indicators?.nome || input.municipioNome || 'O município';
  const uf = input.indicators?.uf || input.uf || '';
  const score = input.indicators?.score_sinidu;
  const ivc = input.avgIvc ?? input.indicators?.media_ivc ?? null;
  const iri = input.avgIri ?? input.indicators?.media_iri ?? null;
  const alertas = input.indicators?.alertas_ativos_count ?? 0;
  const maturidade = input.maturity?.classificacao || input.maturity?.score;
  const capag = input.indicators?.nota_capag;
  const desastres = input.indicators?.historico_desastres_count ?? 0;
  const topVuln = topBairros(input.indices, 'vulnerabilidade');
  const topFlood = topBairros(input.indices, 'inundacao');

  const paragraphs: string[] = [];
  const bullets: string[] = [];

  if (score != null) {
    paragraphs.push(
      `${nome}${uf ? ` (${uf})` : ''} apresenta score Sinidu+Clima de **${Math.round(score)}** (${scorePriority(score)}). `
      + `A leitura integra vulnerabilidade climática, risco de inundação, histórico de desastres e maturidade de dados territoriais.`,
    );
  } else {
    paragraphs.push(
      `${nome}${uf ? ` (${uf})` : ''} ainda não possui score composto calculado. `
      + `Conclua o onboarding municipal para liberar indicadores prioritários e narrativa completa.`,
    );
  }

  const riscoParts: string[] = [];
  if (ivc != null) riscoParts.push(`IVC médio de ${Math.round(ivc * 100)}`);
  if (iri != null) riscoParts.push(`IRI médio de ${Math.round(iri * 100)}`);
  if (alertas > 0) riscoParts.push(`${alertas} alerta(s) CEMADEN ativo(s)`);
  if (desastres > 0) riscoParts.push(`${desastres} evento(s) registrado(s) no S2ID`);

  if (riscoParts.length) {
    paragraphs.push(
      `No eixo de risco, observa-se ${riscoParts.join(', ')}. `
      + (topVuln.length
        ? `Setores com maior vulnerabilidade: ${topVuln.join(' e ')}. `
        : '')
      + (topFlood.length
        ? `Maior exposição a inundação: ${topFlood.join(' e ')}.`
        : ''),
    );
  }

  const capacidadeParts: string[] = [];
  if (maturidade) {
    capacidadeParts.push(
      typeof maturidade === 'number'
        ? `maturidade de dados em ${Math.round(maturidade)}%`
        : `classificação ${maturidade} na maturidade territorial`,
    );
  }
  if (capag) capacidadeParts.push(`CAPAG ${capag}`);
  if (input.maturity?.fontes_faltantes?.length) {
    capacidadeParts.push(`${input.maturity.fontes_faltantes.length} fonte(s) ainda pendente(s)`);
  }

  if (capacidadeParts.length) {
    paragraphs.push(
      `Quanto à capacidade institucional e fiscal, destacam-se ${capacidadeParts.join(', ')}. `
      + `Use Simulações para cenários pluviais e o Modo Focus (tecla F) em apresentações à gestão.`,
    );
  }

  if (alertas > 0) bullets.push('Monitorar alertas CEMADEN e cruzar camadas de inundação no mapa.');
  if (ivc != null && ivc >= 0.6) bullets.push('Priorizar ações de adaptação nos bairros de maior IVC.');
  if (iri != null && iri >= 0.6) bullets.push('Simular chuva extrema (≥120 mm) e inspecionar profundidade no terreno 3D.');
  if (input.maturity && input.maturity.score < 26) bullets.push('Elevar maturidade para Prata antes de relatórios PDF oficiais.');
  if (!bullets.length) bullets.push('Gerar diagnóstico executivo para narrativa institucional completa com IA.');

  return { paragraphs, bullets, source: 'generated' };
}

/** Remove markdown bold markers for plain display */
export function stripNarrativeMarkdown(text: string): string {
  return text.replace(/\*\*(.*?)\*\*/g, '$1');
}
