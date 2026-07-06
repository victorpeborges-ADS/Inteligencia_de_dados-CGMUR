type MunicipioRef = {
  codigo_ibge: string;
  nome: string;
  uf?: string;
  populacao?: number;
};

export type ComparePreset = {
  id: string;
  label: string;
  codigoIbge: string;
  hint: string;
};

export type CompareMetricRow = {
  key: string;
  label: string;
  higherIsWorse: boolean;
  format?: 'number' | 'percent' | 'text';
};

export const COMPARE_METRICS: CompareMetricRow[] = [
  { key: 'score_sinidu', label: 'Score', higherIsWorse: true, format: 'number' },
  { key: 'media_ivc', label: 'IVC médio', higherIsWorse: true, format: 'percent' },
  { key: 'media_iri', label: 'IRI médio', higherIsWorse: true, format: 'percent' },
  { key: 'nota_capag', label: 'CAPAG', higherIsWorse: false, format: 'text' },
  { key: 'alertas_ativos', label: 'Alertas ativos', higherIsWorse: true, format: 'number' },
  { key: 'maturity_score', label: 'Maturidade', higherIsWorse: false, format: 'number' },
  { key: 'populacao', label: 'População', higherIsWorse: false, format: 'number' },
];

export function buildComparePresets(codigoA: string, municipalities: MunicipioRef[]): ComparePreset[] {
  const municipioA = municipalities.find((m) => m.codigo_ibge === codigoA);
  if (!municipioA) return [];

  const others = municipalities.filter((m) => m.codigo_ibge !== codigoA);
  const presets: ComparePreset[] = [];
  const used = new Set<string>();

  const push = (preset: ComparePreset) => {
    if (used.has(preset.codigoIbge)) return;
    used.add(preset.codigoIbge);
    presets.push(preset);
  };

  const sameUf = others
    .filter((m) => municipioA.uf && m.uf === municipioA.uf)
    .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
  if (sameUf[0]) {
    push({
      id: 'same_uf',
      label: 'Mesma UF',
      codigoIbge: sameUf[0].codigo_ibge,
      hint: `${sameUf[0].nome} · ${sameUf[0].uf}`,
    });
  }

  if (municipioA.populacao) {
    const similar = others
      .filter((m) => m.populacao && Math.abs(m.populacao - municipioA.populacao!) / municipioA.populacao! <= 0.4)
      .sort(
        (a, b) =>
          Math.abs((a.populacao ?? 0) - municipioA.populacao!)
          - Math.abs((b.populacao ?? 0) - municipioA.populacao!),
      );
    if (similar[0]) {
      push({
        id: 'similar_size',
        label: 'Porte similar',
        codigoIbge: similar[0].codigo_ibge,
        hint: `${(similar[0].populacao ?? 0).toLocaleString('pt-BR')} hab.`,
      });
    }
  }

  const regional = others
    .filter((m) => m.uf !== municipioA.uf)
    .sort((a, b) => (b.populacao ?? 0) - (a.populacao ?? 0));
  if (regional[0]) {
    push({
      id: 'regional',
      label: 'Referência regional',
      codigoIbge: regional[0].codigo_ibge,
      hint: `${regional[0].nome} (${regional[0].uf})`,
    });
  }

  const loadedPeer = others.find((m) => m.codigo_ibge !== codigoA);
  if (loadedPeer && presets.length === 0) {
    push({
      id: 'fallback',
      label: 'Comparar',
      codigoIbge: loadedPeer.codigo_ibge,
      hint: loadedPeer.nome,
    });
  }

  return presets.slice(0, 3);
}

export function num(val: unknown): number | null {
  if (typeof val === 'number' && Number.isFinite(val)) return val;
  if (typeof val === 'string' && val.trim()) {
    const n = Number(val);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function formatCompareValue(val: unknown, format: CompareMetricRow['format'] = 'number'): string {
  if (val == null || val === '') return '—';
  if (format === 'text') return String(val);
  const n = num(val);
  if (n == null) return String(val);
  if (format === 'percent') return `${Math.round(n * 100)}`;
  if (format === 'number' && n >= 1000) return n.toLocaleString('pt-BR');
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

export type MetricDelta = {
  delta: number | null;
  winner: 'a' | 'b' | 'tie' | null;
  formattedDelta: string | null;
};

export function computeMetricDelta(
  aVal: unknown,
  bVal: unknown,
  higherIsWorse: boolean,
  format: CompareMetricRow['format'] = 'number',
): MetricDelta {
  if (format === 'text') return { delta: null, winner: null, formattedDelta: null };
  const a = num(aVal);
  const b = num(bVal);
  if (a == null || b == null) return { delta: null, winner: null, formattedDelta: null };

  const delta = a - b;
  if (Math.abs(delta) < 0.005) {
    return { delta: 0, winner: 'tie', formattedDelta: '≈' };
  }

  let winner: 'a' | 'b';
  if (higherIsWorse) {
    winner = delta > 0 ? 'b' : 'a';
  } else {
    winner = delta > 0 ? 'a' : 'b';
  }

  const display =
    format === 'percent'
      ? `${delta > 0 ? '+' : ''}${Math.round(delta * 100)}`
      : `${delta > 0 ? '+' : ''}${Math.round(delta * 10) / 10}`;

  return { delta, winner, formattedDelta: display };
}

export function buildCompareBullets(
  nomeA: string,
  nomeB: string,
  municipioA: Record<string, unknown>,
  municipioB: Record<string, unknown>,
): string[] {
  const bullets: string[] = [];

  const scoreA = num(municipioA.score_sinidu);
  const scoreB = num(municipioB.score_sinidu);
  if (scoreA != null && scoreB != null && Math.abs(scoreA - scoreB) >= 5) {
    const higher = scoreA > scoreB ? nomeA : nomeB;
    bullets.push(`${higher} apresenta score territorial mais elevado (${Math.max(scoreA, scoreB)} vs ${Math.min(scoreA, scoreB)}).`);
  }

  const ivcA = num(municipioA.media_ivc);
  const ivcB = num(municipioB.media_ivc);
  if (ivcA != null && ivcB != null && Math.abs(ivcA - ivcB) >= 0.08) {
    const higher = ivcA > ivcB ? nomeA : nomeB;
    bullets.push(`${higher} concentra maior vulnerabilidade climática média (IVC).`);
  }

  const matA = num(municipioA.maturity_score);
  const matB = num(municipioB.maturity_score);
  if (matA != null && matB != null && Math.abs(matA - matB) >= 8) {
    const higher = matA > matB ? nomeA : nomeB;
    bullets.push(`${higher} possui maturidade de dados superior para decisões baseadas em evidência.`);
  }

  const capA = municipioA.nota_capag;
  const capB = municipioB.nota_capag;
  if (capA && capB && capA !== capB) {
    bullets.push(`Saúde fiscal (CAPAG): ${nomeA} ${capA} · ${nomeB} ${capB}.`);
  }

  return bullets.slice(0, 4);
}
