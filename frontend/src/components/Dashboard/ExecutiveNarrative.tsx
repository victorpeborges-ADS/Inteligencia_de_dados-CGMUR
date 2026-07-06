'use client';

import { useMemo } from 'react';
import { BookOpen, Sparkles } from 'lucide-react';
import type {
  ExecutiveDiagnostic,
  ExecutiveIndicators,
  IndicesResponse,
  MunicipalMaturity,
} from '@/utils/api';
import { PanelSection } from '@/design-system';
import { buildExecutiveNarrative, stripNarrativeMarkdown } from '@/utils/executiveNarrative';

type ExecutiveNarrativeProps = {
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

const SOURCE_LABEL = {
  diagnostic_ia: 'Narrativa IA (diagnóstico salvo)',
  diagnostic_headline: 'Resumo do diagnóstico',
  generated: 'Síntese automática Sinidu+Clima',
} as const;

export default function ExecutiveNarrative(props: ExecutiveNarrativeProps) {
  const narrative = useMemo(
    () =>
      buildExecutiveNarrative({
        municipioNome: props.municipioNome,
        uf: props.uf,
        codigoIbge: props.codigoIbge,
        indicators: props.indicators,
        indices: props.indices,
        maturity: props.maturity,
        diagnostic: props.diagnostic,
        avgIvc: props.avgIvc,
        avgIri: props.avgIri,
      }),
    [
      props.municipioNome,
      props.uf,
      props.codigoIbge,
      props.indicators,
      props.indices,
      props.maturity,
      props.diagnostic,
      props.avgIvc,
      props.avgIri,
    ],
  );

  if (!narrative.paragraphs.length) return null;

  return (
    <PanelSection
      title="Leitura executiva"
      tier="primary"
      description={SOURCE_LABEL[narrative.source]}
    >
      <div className="space-y-3">
        {narrative.paragraphs.map((paragraph, index) => (
          <p
            key={index}
            className="text-[11px] leading-relaxed text-zinc-300"
          >
            {stripNarrativeMarkdown(paragraph)}
          </p>
        ))}

        {narrative.bullets.length > 0 && (
          <div className="rounded-lg border border-indigo-500/20 bg-indigo-950/20 px-3 py-2.5">
            <p className="mb-2 flex items-center gap-1.5 text-[9px] font-extrabold uppercase tracking-wider text-indigo-300">
              {narrative.source === 'generated' ? (
                <Sparkles size={11} />
              ) : (
                <BookOpen size={11} />
              )}
              Próximas ações sugeridas
            </p>
            <ul className="space-y-1">
              {narrative.bullets.map((item) => (
                <li key={item} className="flex gap-2 text-[10px] text-zinc-400">
                  <span className="text-indigo-400">→</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </PanelSection>
  );
}
