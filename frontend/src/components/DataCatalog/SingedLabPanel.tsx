'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ExternalLink, FileUp, Loader2, Waves } from 'lucide-react';
import { api, type DataCatalogBase } from '@/utils/api';
import { Badge } from '@/design-system';

const SINGEDLAB_PORTAL_URL = 'https://www.ibge.gov.br/singedlab/dados-apoio-rs.php';

type Exposure = {
  codigo_ibge: string;
  escopo: string;
  populacao_area_afetada?: number | null;
  domicilios_area_afetada?: number | null;
  estabelecimentos_area_afetada?: number | null;
  pct_populacao_municipio?: number | null;
  pct_area_municipio?: number | null;
  data_quality?: string;
  status_catalogo?: string;
  fonte_ref?: string | null;
  sincronizado_em?: string | null;
  municipio?: { codigo_ibge: string; nome: string; uf: string };
};

type Props = {
  codigoIbge: string;
  municipioNome: string;
  uf: string;
  isGestorOrAdmin: boolean;
  singedlabBase?: DataCatalogBase;
  onImported?: () => void;
};

function formatNumber(value?: number | null): string {
  if (value == null) return '—';
  return value.toLocaleString('pt-BR');
}

function statusTone(status?: string): 'success' | 'warning' | 'info' | 'gap' | 'neutral' {
  if (status === 'Integrado') return 'success';
  if (status === 'Estimado') return 'warning';
  if (status === 'Em integracao') return 'info';
  if (status === 'Ausente') return 'gap';
  return 'neutral';
}

export default function SingedLabPanel({
  codigoIbge,
  municipioNome,
  uf,
  isGestorOrAdmin,
  singedlabBase,
  onImported,
}: Props) {
  const isRs = uf === 'RS';
  const showPanel = isRs || isGestorOrAdmin;
  const [exposure, setExposure] = useState<Exposure | null>(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadExposure = useCallback(async () => {
    if (!isRs) {
      setExposure(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = (await api.getSingedlabExposure(codigoIbge)) as Exposure;
      setExposure(data);
    } catch (e) {
      setExposure(null);
      setError(e instanceof Error ? e.message : 'Falha ao carregar exposição SINGED Lab');
    } finally {
      setLoading(false);
    }
  }, [codigoIbge, isRs]);

  useEffect(() => {
    loadExposure();
  }, [loadExposure]);

  const handleImport = async (file: File) => {
    setImporting(true);
    setMessage(null);
    setError(null);
    try {
      const result = await api.importSingedlabCsv(file);
      const count = result.imported_municipios ?? 0;
      setMessage(`Importação concluída: ${count} município(s) atualizado(s) no seed curado.`);
      await loadExposure();
      onImported?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha na importação do CSV');
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  if (!showPanel) return null;

  const catalogStatus = exposure?.status_catalogo || singedlabBase?.status;
  const pendingImport = exposure?.data_quality === 'pendente_import' || catalogStatus === 'Em integracao';

  return (
    <div className="rounded-xl border border-sky-500/25 bg-sky-950/10 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-sky-300">
            <Waves size={13} />
            IBGE SINGED Lab — enchentes RS 2024
          </h3>
          <p className="mt-1 text-[10px] leading-relaxed text-zinc-400">
            Exposição oficial CNEFE/Censo 2022 nas áreas afetadas. O portal IBGE não expõe API pública —
            importe o CSV exportado manualmente para atualizar o catálogo Sinidu.
          </p>
        </div>
        {catalogStatus && (
          <Badge tone={statusTone(catalogStatus)}>{catalogStatus === 'Nao aplicavel' ? 'N/A' : catalogStatus}</Badge>
        )}
      </div>

      {isRs && (
        <div className="mt-3 rounded-lg border border-zinc-800/80 bg-zinc-950/50 p-2.5">
          {loading ? (
            <div className="flex items-center gap-2 text-[10px] text-zinc-400">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Carregando exposição municipal…
            </div>
          ) : exposure ? (
            <div className="grid grid-cols-2 gap-2 text-[10px] sm:grid-cols-4">
              <div>
                <p className="text-zinc-500">População afetada</p>
                <p className="font-semibold text-zinc-100">{formatNumber(exposure.populacao_area_afetada)}</p>
              </div>
              <div>
                <p className="text-zinc-500">Domicílios</p>
                <p className="font-semibold text-zinc-100">{formatNumber(exposure.domicilios_area_afetada)}</p>
              </div>
              <div>
                <p className="text-zinc-500">Estabelecimentos</p>
                <p className="font-semibold text-zinc-100">{formatNumber(exposure.estabelecimentos_area_afetada)}</p>
              </div>
              <div>
                <p className="text-zinc-500">% pop. municipal</p>
                <p className="font-semibold text-zinc-100">
                  {exposure.pct_populacao_municipio != null ? `${exposure.pct_populacao_municipio}%` : '—'}
                </p>
              </div>
              {exposure.fonte_ref && (
                <p className="col-span-full text-[9px] text-zinc-500">Fonte: {exposure.fonte_ref}</p>
              )}
            </div>
          ) : (
            <p className="text-[10px] text-zinc-500">
              Dados ainda não sincronizados para {municipioNome}. Use a importação CSV ou atualize a fonte no catálogo.
            </p>
          )}
          {pendingImport && (
            <p className="mt-2 text-[9px] text-sky-300/90">
              Pendente: exporte o município no portal SINGED Lab e importe o CSV abaixo (perfil gestor).
            </p>
          )}
        </div>
      )}

      {!isRs && isGestorOrAdmin && (
        <p className="mt-3 text-[10px] text-zinc-500">
          Produto pontual do RS — fora do escopo de {municipioNome}/{uf}. Gestores podem importar CSV para os 6
          municípios RS do piloto.
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <a
          href={SINGEDLAB_PORTAL_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-lg border border-sky-600/40 bg-sky-950/30 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-sky-100 transition hover:bg-sky-900/40"
        >
          <ExternalLink size={12} />
          Portal IBGE SINGED Lab
        </a>

        {isGestorOrAdmin && (
          <>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleImport(file);
              }}
            />
            <button
              type="button"
              disabled={importing}
              onClick={() => fileRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-600/40 bg-emerald-950/30 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-emerald-100 transition hover:bg-emerald-900/40 disabled:opacity-50"
            >
              {importing ? <Loader2 size={12} className="animate-spin" /> : <FileUp size={12} />}
              Importar CSV
            </button>
          </>
        )}
      </div>

      {message && <p className="mt-2 text-[10px] text-emerald-300/90">{message}</p>}
      {error && <p className="mt-2 text-[10px] text-rose-300/90">{error}</p>}
    </div>
  );
}
