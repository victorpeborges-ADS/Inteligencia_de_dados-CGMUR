'use client';

import { useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowRight,
  Database,
  Landmark,
  MapPinned,
  ShieldAlert,
  Siren,
} from 'lucide-react';
import type {
  ExecutiveDiagnostic,
  ExecutiveIndicators,
  IndicesResponse,
  MunicipalMaturity,
} from '@/utils/api';
import { TAB_ROUTES, type ActiveTab } from '@/config/platformTabs';
import { Badge, PanelSection } from '@/design-system';
import { useAppStore } from '@/stores/useAppStore';
import {
  buildTerritorialRecommendations,
  recommendationCategoryLabel,
  type RecommendationCategory,
  type RecommendationPriority,
} from '@/utils/territorialRecommendations';

type Props = {
  indicators?: ExecutiveIndicators | null;
  indices?: IndicesResponse | null;
  maturity?: MunicipalMaturity | null;
  diagnostic?: ExecutiveDiagnostic | null;
  avgIvc?: number | null;
  avgIri?: number | null;
};

const PRIORITY_BADGE: Record<
  RecommendationPriority,
  { label: string; tone: 'danger' | 'warning' | 'neutral' }
> = {
  alta: { label: 'Alta', tone: 'danger' },
  media: { label: 'Média', tone: 'warning' },
  baixa: { label: 'Acompanhar', tone: 'neutral' },
};

const CATEGORY_ICON: Record<RecommendationCategory, typeof ShieldAlert> = {
  risco: ShieldAlert,
  operacao: Siren,
  dados: Database,
  planejamento: MapPinned,
  fiscal: Landmark,
};

export default function TerritorialRecommendations(props: Props) {
  const router = useRouter();
  const setActiveTab = useAppStore((s) => s.setActiveTab);

  const recommendations = useMemo(
    () =>
      buildTerritorialRecommendations({
        indicators: props.indicators,
        indices: props.indices,
        maturity: props.maturity,
        diagnostic: props.diagnostic,
        avgIvc: props.avgIvc,
        avgIri: props.avgIri,
      }),
    [
      props.indicators,
      props.indices,
      props.maturity,
      props.diagnostic,
      props.avgIvc,
      props.avgIri,
    ],
  );

  const navigate = (tab: ActiveTab) => {
    setActiveTab(tab);
    router.push(TAB_ROUTES[tab]);
  };

  if (!recommendations.length) return null;

  return (
    <PanelSection
      title="Recomendações territoriais"
      tier="primary"
      description="Motor Sinidu+Clima — priorização explicável com base em indicadores oficiais e derivados"
    >
      <ul className="space-y-3">
        {recommendations.map((rec, index) => {
          const Icon = CATEGORY_ICON[rec.category];
          const badge = PRIORITY_BADGE[rec.priority];
          return (
            <li
              key={rec.id}
              className="rounded-lg border border-zinc-800/80 bg-zinc-950/40 px-3 py-2.5"
            >
              <div className="flex items-start gap-2">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-zinc-900 text-[10px] font-bold text-zinc-500">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Icon size={13} className="shrink-0 text-indigo-300" />
                    <p className="text-[11px] font-bold leading-snug text-zinc-100">{rec.title}</p>
                    <Badge tone={badge.tone}>{badge.label}</Badge>
                    <span className="text-[9px] uppercase tracking-wide text-zinc-600">
                      {recommendationCategoryLabel(rec.category)}
                    </span>
                  </div>
                  <p className="mt-1 text-[10px] leading-relaxed text-zinc-400">{rec.explanation}</p>
                  {rec.evidence.length > 0 && (
                    <ul className="mt-2 space-y-0.5">
                      {rec.evidence.map((line) => (
                        <li key={line} className="flex gap-1.5 text-[9px] text-zinc-500">
                          <span className="text-indigo-500/80">•</span>
                          <span>{line}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {rec.ctaTab && rec.ctaLabel && (
                    <button
                      type="button"
                      onClick={() => navigate(rec.ctaTab!)}
                      className="mt-2 inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-indigo-300 hover:text-indigo-100"
                    >
                      {rec.ctaLabel}
                      <ArrowRight size={12} />
                    </button>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </PanelSection>
  );
}
