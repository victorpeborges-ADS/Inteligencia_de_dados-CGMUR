'use client';

import { Building2, Sparkles } from 'lucide-react';
import { INSTITUTIONAL_GAPS, gapStatusFromCatalog } from '@/config/institutionalGaps';
import type { DataCatalogBase } from '@/utils/api';
import { Badge } from '@/design-system';

type Props = {
  bases: DataCatalogBase[];
  onAnalyzeGap: (fonteId: string) => void;
};

const STATUS_TONE: Record<string, 'success' | 'warning' | 'info' | 'gap' | 'neutral'> = {
  Integrado: 'success',
  Estimado: 'warning',
  'Em integracao': 'info',
  Ausente: 'gap',
};

export default function InstitutionalGapsPanel({ bases, onAnalyzeGap }: Props) {
  return (
    <div className="rounded-xl border border-violet-500/25 bg-violet-950/10 p-3">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-violet-300">
            <Building2 size={13} />
            Trâmite institucional — lacunas nacionais
          </h3>
          <p className="mt-1 text-[10px] leading-relaxed text-zinc-500">
            Fontes que exigem convênio ou credencial MCID. Impacto estimado no Score Sinidu+Clima.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-[10px]">
          <thead>
            <tr className="border-b border-violet-900/30 text-zinc-500">
              <th className="py-1 pr-2">#</th>
              <th className="py-1 pr-2">Fonte</th>
              <th className="py-1 pr-2">Catálogo</th>
              <th className="py-1 pr-2">Impacto</th>
              <th className="py-1 pr-2">Responsável</th>
              <th className="py-1 pr-2">Prazo</th>
              <th className="py-1">Ação</th>
            </tr>
          </thead>
          <tbody>
            {INSTITUTIONAL_GAPS.map((gap) => {
              const status = gapStatusFromCatalog(gap.fonteId, bases);
              return (
                <tr key={gap.fonteId} className="border-b border-zinc-900/50 text-zinc-300">
                  <td className="py-2 pr-2 font-mono text-zinc-500">{gap.rank}</td>
                  <td className="py-2 pr-2">
                    <p className="font-semibold text-zinc-100">{gap.nome}</p>
                    <p className="mt-0.5 line-clamp-2 text-[9px] text-zinc-500">{gap.acao}</p>
                  </td>
                  <td className="py-2 pr-2">
                    {status ? (
                      <Badge tone={STATUS_TONE[status] || 'neutral'}>{status}</Badge>
                    ) : (
                      <span className="text-zinc-600">—</span>
                    )}
                  </td>
                  <td className="py-2 pr-2 text-amber-300">{gap.impactoScore}</td>
                  <td className="py-2 pr-2 text-zinc-400">{gap.responsavel}</td>
                  <td className="py-2 pr-2 text-zinc-400">{gap.prazo}</td>
                  <td className="py-2">
                    <button
                      type="button"
                      onClick={() => onAnalyzeGap(gap.fonteId)}
                      className="inline-flex items-center gap-0.5 rounded border border-violet-600/40 px-1.5 py-0.5 text-[8px] font-bold uppercase text-violet-200 hover:bg-violet-950/40"
                    >
                      <Sparkles size={10} />
                      Impacto IA
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-[9px] text-zinc-600">
        Referência: PLANO_LACUNAS_INSTITUCIONAIS.md · Meta maturidade nacional 77% → 84% (GeoSGB + Brasil MAIS)
      </p>
    </div>
  );
}
