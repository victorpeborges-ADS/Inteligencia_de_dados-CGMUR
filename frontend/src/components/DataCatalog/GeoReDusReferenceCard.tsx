'use client';

import { ExternalLink, Globe2 } from 'lucide-react';
import { georedusMunicipioUrl } from '@/config/georedus';
import { Badge } from '@/design-system';

type Props = {
  codigoIbge: string;
  municipioNome?: string;
};

export default function GeoReDusReferenceCard({ codigoIbge, municipioNome }: Props) {
  const url = georedusMunicipioUrl(codigoIbge);

  return (
    <div className="rounded-xl border border-cyan-500/25 bg-cyan-950/10 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-cyan-300">
            <Globe2 size={13} />
            GeoReDUS — referência nacional
          </h3>
          <p className="mt-1 text-[10px] leading-relaxed text-zinc-400">
            Catálogo aberto da ReDUS com indicadores intramunicipais em 5.570 municípios (Censo, INEP,
            saúde, LST por satélite). Complementa o Sinidu onde a cobertura local ainda é parcial.
          </p>
        </div>
        <Badge tone="info">Referência externa</Badge>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-600/40 bg-cyan-950/30 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-cyan-100 transition hover:bg-cyan-900/40"
        >
          <ExternalLink size={12} />
          Abrir no GeoReDUS
          {municipioNome ? ` — ${municipioNome}` : ''}
        </a>
        <span className="font-mono text-[9px] text-zinc-600">IBGE {codigoIbge}</span>
      </div>
    </div>
  );
}
