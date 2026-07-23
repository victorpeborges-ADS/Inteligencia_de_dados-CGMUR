'use client';

import { HelpCircle } from 'lucide-react';

export const TERM_GLOSSARY: Record<string, string> = {
  IVC: 'IVC (Índice de Vulnerabilidade Climática): mede exposição e sensibilidade do município a eventos climáticos. Escala 0–1 (painel) ou agregada no Score.',
  IRI: 'IRI (Índice de Risco de Inundação): susceptibilidade a alagamentos com topografia, drenagem e uso do solo. Escala 0–1.',
  Score: 'Score Sinidu+Clima: índice 0–100 que integra IVC, IRI e déficit de adaptação. Quanto maior, maior a prioridade territorial.',
  CAPAG: 'CAPAG: nota de capacidade de pagamento do Tesouro Nacional (A–D). A/B sem restrição de garantia da União; C/D restringem crédito federal.',
  COBRADE: 'COBRADE: Classificação Brasileira de Desastres — códigos oficiais (ex.: 1.2.1.0.0 inundação) usados no S2ID e na contingência.',
  DEM: 'DEM (Modelo Digital de Elevação): relevo do terreno usado nas simulações de inundação e encosta.',
  SRTM: 'SRTM: DEM nacional ~30 m (NASA/USGS). Bom para priorização; menos preciso que LiDAR municipal.',
  S2ID: 'S2ID: base nacional de desastres (eventos, danos e resposta). No Sinidu, valida se a mancha simulada cobre pontos históricos.',
  IDF: 'IDF: curva Intensidade–Duração–Frequência. Relaciona chuva (mm) ao tempo de retorno (TR 2, 10, 25, 100 anos).',
  TR: 'Período de retorno (TR): em média, a cada quantos anos se espera uma chuva daquela magnitude (ex.: TR 100 ≈ chuva extrema rara).',
  UHI: 'UHI (ilha de calor urbana): diferença de temperatura entre área urbana e entorno — usada nas simulações térmicas.',
  LST: 'LST: temperatura de superfície por satélite (ex.: Landsat). Serve para comparar a simulação de calor com observação.',
  TWI: 'TWI (Topographic Wetness Index): indica onde a água tende a acumular no terreno — usado no motor pluvial.',
  LOD1: 'LOD1: edifícios em 3D como blocos com altura estimada (sem forma de telhado). Suficiente para exposição climática.',
  Observado: 'Selo Observado: dado medido (ex.: LiDAR). Maior confiança operacional.',
  Estimado: 'Selo Estimado: dado de modelo nacional (ex.: SRTM/OSM). Adequado a priorização territorial.',
  Derivado: 'Selo Derivado: indicador calculado ou heurística. Use para sensibilização, não como laudo.',
  CEMADEN: 'CEMADEN: Centro Nacional de Monitoramento e Alertas — fonte dos alertas hidrológicos/geológicos ao vivo.',
  NDSM: 'nDSM: altura dos objetos acima do terreno (DSM − DTM), usada para refinar altura de edifícios com LiDAR.',
};

export type TermKey = keyof typeof TERM_GLOSSARY;

type TermTooltipProps = {
  term: TermKey | string;
  label?: string;
  className?: string;
};

function resolveGlossary(term: string): string {
  if (TERM_GLOSSARY[term]) return TERM_GLOSSARY[term];
  const upper = term.toUpperCase();
  if (TERM_GLOSSARY[upper]) return TERM_GLOSSARY[upper];
  const hit = Object.entries(TERM_GLOSSARY).find(([k]) => k.toUpperCase() === upper);
  return hit?.[1] ?? `${term}: termo técnico Sinidu+Clima.`;
}

export default function TermTooltip({ term, label, className = '' }: TermTooltipProps) {
  const text = resolveGlossary(term);
  const display = label ?? term;

  return (
    <span className={`inline-flex items-center gap-0.5 ${className}`}>
      <span>{display}</span>
      <span
        title={text}
        className="inline-flex cursor-help text-zinc-500 hover:text-indigo-300"
        aria-label={text}
      >
        <HelpCircle className="h-3 w-3" />
      </span>
    </span>
  );
}
