'use client';

import Link from 'next/link';
import { Award, Layers, Waves } from 'lucide-react';
import {
  Badge,
  EmptyState,
  KpiCard,
  PanelSection,
  Skeleton,
  SkeletonChart,
  SkeletonKpiGrid,
  colors,
  spacing,
  typography,
} from '@/design-system';

export default function DesignSystemPage() {
  return (
    <main
      className="min-h-screen p-8 text-zinc-100"
      style={{ backgroundColor: colors.background }}
    >
      <div className="mx-auto max-w-3xl space-y-8">
        <header>
          <p className="text-[10px] font-bold uppercase tracking-widest text-indigo-400">
            Sinidu+Clima · Fase 13
          </p>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight">Design System</h1>
          <p className="mt-2 text-sm text-zinc-400">
            Tokens e componentes base usados no painel executivo, catálogo e simulações.
          </p>
          <Link href="/painel" className="mt-3 inline-block text-xs text-indigo-300 hover:text-indigo-100">
            ← Voltar ao painel
          </Link>
        </header>

        <PanelSection title="Tokens de cor" tier="primary">
          <div className="flex flex-wrap gap-2">
            {Object.entries(colors.accent).map(([name, hex]) => (
              <div key={name} className="flex items-center gap-2 rounded-lg border border-zinc-800 px-2 py-1">
                <span className="h-4 w-4 rounded" style={{ backgroundColor: hex }} />
                <span className="text-[10px] text-zinc-400">{name}</span>
              </div>
            ))}
          </div>
        </PanelSection>

        <PanelSection title="Badges de qualidade" tier="secondary">
          <div className="flex flex-wrap gap-2">
            <Badge tone="official">Oficial</Badge>
            <Badge tone="derived">Derivado</Badge>
            <Badge tone="estimated">Estimado</Badge>
            <Badge tone="gap">Lacuna</Badge>
            <Badge tone="danger">Alta</Badge>
            <Badge tone="warning">Média</Badge>
          </div>
        </PanelSection>

        <PanelSection title="KPI Cards" tier="primary">
          <div className="grid grid-cols-2 gap-3">
            <KpiCard
              tier="primary"
              title="Score Sinidu+Clima"
              value="72"
              description="Prioridade territorial composta"
              icon={Award}
              iconClassName="text-indigo-300"
              quality="DERIVADO"
            />
            <KpiCard
              tier="primary"
              title="IRI médio"
              value="68"
              description="Risco de inundação agregado"
              icon={Waves}
              iconClassName="text-sky-300"
              quality="DERIVADO"
            />
          </div>
        </PanelSection>

        <PanelSection title="Estados vazios e loading" tier="secondary">
          <div className="space-y-4">
            <EmptyState
              icon={Layers}
              title="Nenhuma simulação ainda"
              description="Execute um cenário pluvial para ver manchas no mapa e volume 3D."
            />
            <SkeletonKpiGrid count={2} />
            <SkeletonChart />
            <Skeleton className="h-8 w-48" />
          </div>
        </PanelSection>

        <PanelSection title="Espaçamento" tier="secondary" description="Escala Tailwind (px)">
          <div className="flex items-end gap-2">
            {([1, 2, 3, 4, 6, 8] as const).map((n) => (
              <div key={n} className="text-center">
                <div
                  className="rounded bg-indigo-500/30"
                  style={{ width: spacing[n], height: spacing[n] }}
                />
                <span className="mt-1 block text-[9px] text-zinc-600">{spacing[n]}px</span>
              </div>
            ))}
          </div>
        </PanelSection>

        <PanelSection title="Tipografia" tier="secondary">
          <p style={{ fontSize: typography.fontSize.xl, fontWeight: typography.fontWeight.extrabold }}>
            Título executivo — {typography.fontSize.xl}
          </p>
          <p className="mt-2 text-zinc-400" style={{ fontSize: typography.fontSize.sm }}>
            Corpo secundário — {typography.fontSize.sm}
          </p>
          <p
            className="mt-2 uppercase tracking-widest text-zinc-500"
            style={{ fontSize: typography.fontSize.xs, fontWeight: typography.fontWeight.bold }}
          >
            Label uppercase — {typography.fontSize.xs}
          </p>
        </PanelSection>
      </div>
    </main>
  );
}
