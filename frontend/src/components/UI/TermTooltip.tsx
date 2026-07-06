'use client';

import { HelpCircle } from 'lucide-react';

export const TERM_GLOSSARY: Record<string, string> = {
  IVC: 'IVC (Índice de Vulnerabilidade Climática): mede exposição e sensibilidade do município a eventos climáticos extremos. Escala 0–100.',
  IRI: 'IRI (Índice de Risco de Inundação): estima susceptibilidade a alagamentos com base em topografia, drenagem e uso do solo. Escala 0–100.',
  Score: 'Score Sinidu+Clima: índice composto que integra IVC, IRI, capacidade de adaptação e histórico de desastres. Quanto maior, maior a prioridade territorial.',
  CAPAG: 'CAPAG: nota de capacidade de pagamento do Tesouro Nacional (A–E). B = boa saúde fiscal; município pode tomar crédito com garantia da União.',
  COBRADE: 'COBRADE: Classificação Brasileira de Desastres — tipologia oficial usada pelo S2ID/CEMADEN para registrar eventos adversos.',
  DEM: 'DEM (Modelo Digital de Elevação): representação do relevo do terreno usada nas simulações hidrológicas e de inundação.',
  SRTM: 'DEM SRTM 30m: Modelo Digital de Elevação do terreno com 30 metros de resolução (NASA/USGS). Usado nas simulações de inundação.',
  S2ID: 'S2ID: Sistema Integrado de Informações sobre Desastres — base nacional de eventos, danos e medidas de resposta.',
};

export type TermKey = keyof typeof TERM_GLOSSARY;

type TermTooltipProps = {
  term: TermKey | string;
  label?: string;
  className?: string;
};

export default function TermTooltip({ term, label, className = '' }: TermTooltipProps) {
  const key = term.toUpperCase() as TermKey;
  const text = TERM_GLOSSARY[key] ?? TERM_GLOSSARY[term as TermKey] ?? `${term}: termo técnico Sinidu+Clima.`;
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
