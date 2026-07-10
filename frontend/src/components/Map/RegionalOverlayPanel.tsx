'use client';

import { ArrowLeftRight, X } from 'lucide-react';
import type { RegionalOverlayResponse } from '@/config/regionalContext';
import { REGIONAL_ESCOPO_LABELS, type RegionalEscopo } from '@/config/regionalContext';
import { MAP_CENTER_LEFT } from '@/config/mapOverlayLayout';

type Props = {
  data: RegionalOverlayResponse | null;
  loading?: boolean;
  escopo: RegionalEscopo;
  setEscopo: (escopo: RegionalEscopo) => void;
  onClose: () => void;
  onOpenCompare?: () => void;
};

export default function RegionalOverlayPanel({
  data,
  loading = false,
  escopo,
  setEscopo,
  onClose,
  onOpenCompare,
}: Props) {
  if (loading) {
    return (
      <div
        className="absolute bottom-4 z-[998] w-80 max-w-[calc(100%-2rem)] rounded-xl border border-teal-500/30 bg-zinc-950/92 p-3 shadow-2xl backdrop-blur-md"
        style={{ left: MAP_CENTER_LEFT }}
      >
        <p className="text-[10px] text-zinc-400">Carregando contexto regional…</p>
      </div>
    );
  }

  if (!data) return null;

  const municipio = data.indicadores?.municipio || {};
  const regional = data.indicadores?.regional || {};
  const regiaoNome =
    escopo === 'mesorregiao' ? data.mesorregiao?.nome : data.regiao_imediata?.nome;

  return (
    <div
      className="absolute bottom-4 z-[998] w-80 max-w-[calc(100%-2rem)] rounded-xl border border-teal-500/30 bg-zinc-950/92 p-3 shadow-2xl backdrop-blur-md"
      style={{ left: MAP_CENTER_LEFT }}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-teal-200">
            Contexto regional
          </p>
          <p className="mt-0.5 text-[10px] text-zinc-400">
            {data.municipio_nome} · {REGIONAL_ESCOPO_LABELS[escopo]}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
          title="Ocultar overlay regional"
        >
          <X size={14} />
        </button>
      </div>

      {regiaoNome && (
        <p className="mt-2 text-[11px] font-semibold text-zinc-100">{regiaoNome}</p>
      )}
      <p className="mt-1 text-[9px] text-zinc-500">
        {data.total_municipios_escopo} municípios no escopo · {data.municipios_carregados_mapa} no mapa
      </p>

      <div className="mt-2 flex gap-1">
        {(Object.keys(REGIONAL_ESCOPO_LABELS) as RegionalEscopo[]).map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => setEscopo(id)}
            className={`rounded-md border px-1.5 py-0.5 text-[9px] font-semibold ${
              escopo === id
                ? 'border-teal-400/50 bg-teal-500/20 text-teal-100'
                : 'border-zinc-700 text-zinc-500 hover:text-teal-100'
            }`}
          >
            {REGIONAL_ESCOPO_LABELS[id]}
          </button>
        ))}
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2 text-[10px]">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-2">
          <p className="text-[9px] uppercase text-zinc-500">Município</p>
          <p className="font-semibold text-zinc-100">
            Score {String(municipio.score_sinidu ?? '—')}
          </p>
        </div>
        <div className="rounded-lg border border-teal-900/40 bg-teal-950/20 p-2">
          <p className="text-[9px] uppercase text-teal-300/80">Média regional</p>
          <p className="font-semibold text-teal-100">
            Score {String(regional.score_sinidu_medio ?? '—')}
          </p>
        </div>
      </div>

      {data.referencia_comparacao && onOpenCompare && (
        <button
          type="button"
          onClick={onOpenCompare}
          className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-amber-500/35 bg-amber-950/20 px-2 py-1.5 text-[10px] font-bold text-amber-100 hover:bg-amber-900/30"
        >
          <ArrowLeftRight size={12} />
          Comparar com {data.referencia_comparacao.nome}
        </button>
      )}

      {data.nota && (
        <p className="mt-2 text-[8px] leading-snug text-zinc-500">{data.nota}</p>
      )}
    </div>
  );
}
