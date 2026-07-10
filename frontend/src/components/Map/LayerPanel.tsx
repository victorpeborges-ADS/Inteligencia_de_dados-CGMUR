'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Building2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  CloudRain,
  ExternalLink,
  Eye,
  HeartPulse,
  Layers,
  Map,
  Search,
  type LucideIcon,
} from 'lucide-react';
import type { LayerOption } from '@/config/platformTabs';
import {
  SOCIO_SUBCAMADAS,
  type SocioSubcamadaId,
} from '@/config/socioeconomicoSubcamadas';
import {
  EDUCACAO_ETAPAS,
  MAX_EDUCACAO_RAIO_M,
  MIN_EDUCACAO_RAIO_M,
  type EducacaoEtapaId,
} from '@/config/educacaoInep';
import TemporalYearPanel from './TemporalYearPanel';
import {
  getTemporalTemaForLayer,
  PIB_CONTEXT_LAYERS,
  type TemporalTemaId,
  type TemporalTemaOption,
} from '@/config/layerTemporal';
import {
  GEOREDUS_BASE_URL,
  georedusMunicipioUrl,
  matchGeoReDusIndicators,
  matchLayerOption,
} from '@/config/georedus';
import { REGIONAL_ESCOPO_LABELS, type RegionalEscopo } from '@/config/regionalContext';
import { MAP_CENTER_LEFT } from '@/config/mapOverlayLayout';
import {
  TERRITORIO_TIPOS,
  type TerritorioTipoId,
} from '@/config/territoriosEspeciais';

/** Presets documentados — ver CHECKLIST_FASE_13.md */
export const LAYER_PRESETS = {
  cruzarRiscos: {
    id: 'cruzar_riscos',
    label: 'Cruzar riscos',
    description: 'Bairros + vulnerabilidade climática + risco de inundação',
    layers: ['bairros', 'vulnerabilidade', 'inundacao'],
  },
} as const;

const GROUP_ICONS: Record<LayerOption['group'], LucideIcon> = {
  Base: Map,
  'Dados urbanos': Building2,
  'Clima e riscos': CloudRain,
  Planejamento: ClipboardList,
  'Saúde e segurança': HeartPulse,
};

const PANEL_COLLAPSED_KEY = 'sinidu-layer-panel-collapsed';
const GROUPS_COLLAPSED_KEY = 'sinidu-layer-groups-collapsed';

type LayerPanelProps = {
  activeLayers: string[];
  setActiveLayers: (layers: string[]) => void;
  toggleLayer: (layerId: string) => void;
  layerOptions: LayerOption[];
  malhaIndisponivel?: boolean;
  codigoIbge?: string;
  className?: string;
  socioSubcamada?: SocioSubcamadaId;
  setSocioSubcamada?: (id: SocioSubcamadaId) => void;
  educacaoEtapa?: EducacaoEtapaId;
  setEducacaoEtapa?: (id: EducacaoEtapaId) => void;
  educacaoRaioM?: number;
  setEducacaoRaioM?: (value: number) => void;
  showEducacaoBuffer?: boolean;
  setShowEducacaoBuffer?: (value: boolean) => void;
  temporalActiveTemas?: TemporalTemaOption[];
  layerAnoByTema?: Partial<Record<TemporalTemaId, number>>;
  setLayerAnoForTema?: (temaId: TemporalTemaId, ano: number | null) => void;
  showRegionalOverlay?: boolean;
  setShowRegionalOverlay?: (value: boolean) => void;
  regionalEscopo?: RegionalEscopo;
  setRegionalEscopo?: (escopo: RegionalEscopo) => void;
  territorioTipo?: TerritorioTipoId;
  setTerritorioTipo?: (id: TerritorioTipoId) => void;
};

function qualityTone(quality: LayerOption['quality']) {
  if (quality === 'Oficial') return 'border-emerald-400/40 bg-emerald-500/10 text-emerald-300';
  if (quality === 'Observado') return 'border-sky-400/40 bg-sky-500/10 text-sky-300';
  if (quality === 'Referencia') return 'border-cyan-400/40 bg-cyan-500/10 text-cyan-300';
  if (quality === 'Estimado') return 'border-amber-400/40 bg-amber-500/10 text-amber-300';
  if (quality === 'Indisponível') return 'border-rose-400/40 bg-rose-500/10 text-rose-300';
  return 'border-sky-400/40 bg-sky-500/10 text-sky-300';
}

export default function LayerPanel({
  activeLayers,
  setActiveLayers,
  toggleLayer,
  layerOptions,
  malhaIndisponivel = false,
  codigoIbge,
  className = '',
  socioSubcamada = 'renda',
  setSocioSubcamada,
  educacaoEtapa = 'todas',
  setEducacaoEtapa,
  educacaoRaioM = 800,
  setEducacaoRaioM,
  showEducacaoBuffer = true,
  setShowEducacaoBuffer,
  temporalActiveTemas = [],
  layerAnoByTema = {},
  setLayerAnoForTema,
  showRegionalOverlay = false,
  setShowRegionalOverlay,
  regionalEscopo = 'regiao_imediata',
  setRegionalEscopo,
  territorioTipo = 'todas',
  setTerritorioTipo,
}: LayerPanelProps) {
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [searchQuery, setSearchQuery] = useState('');

  const filteredLayerOptions = useMemo(() => {
    if (!searchQuery.trim()) return layerOptions;
    return layerOptions.filter((opt) => matchLayerOption(searchQuery, opt));
  }, [layerOptions, searchQuery]);

  const externalMatches = useMemo(
    () => matchGeoReDusIndicators(searchQuery),
    [searchQuery],
  );

  const layerGroups = useMemo(
    () => Array.from(new Set(filteredLayerOptions.map((opt) => opt.group))),
    [filteredLayerOptions],
  );

  useEffect(() => {
    try {
      if (localStorage.getItem(PANEL_COLLAPSED_KEY) === 'true') {
        setPanelCollapsed(true);
      }
      const raw = localStorage.getItem(GROUPS_COLLAPSED_KEY);
      if (raw) setCollapsedGroups(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(PANEL_COLLAPSED_KEY, String(panelCollapsed));
    } catch {
      /* ignore */
    }
  }, [panelCollapsed]);

  useEffect(() => {
    try {
      localStorage.setItem(GROUPS_COLLAPSED_KEY, JSON.stringify(collapsedGroups));
    } catch {
      /* ignore */
    }
  }, [collapsedGroups]);

  const toggleGroup = (group: string) => {
    setCollapsedGroups((prev) => ({ ...prev, [group]: !prev[group] }));
  };

  if (panelCollapsed) {
    return (
      <div className={`absolute top-4 left-4 z-[999] ${className}`}>
        <button
          type="button"
          onClick={() => setPanelCollapsed(false)}
          title="Expandir camadas espaciais"
          className="flex items-center gap-2 rounded-xl border border-border bg-card/90 px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-indigo-300 shadow-2xl backdrop-blur-md transition hover:border-indigo-500/40"
        >
          <Layers size={14} />
          Camadas
          <span className="rounded-full bg-indigo-500/20 px-1.5 py-0.5 text-[9px] text-indigo-200">
            {activeLayers.length}
          </span>
        </button>
      </div>
    );
  }

  return (
    <div
      className={`absolute top-4 bottom-4 left-4 z-[999] flex w-72 max-h-[calc(100%-2rem)] flex-col gap-2 overflow-hidden rounded-xl border border-border bg-card/85 p-3 shadow-2xl backdrop-blur-md transition-all duration-300 ${className}`}
    >
      <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5">
        <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-400">
          <Layers size={12} className="text-indigo-400" />
          Camadas Espaciais
        </span>
        <div className="flex items-center gap-2">
          <span className="text-[9px] italic text-zinc-500">{activeLayers.length} ativa(s)</span>
          <button
            type="button"
            onClick={() => setPanelCollapsed(true)}
            title="Recolher painel"
            className="rounded-md p-0.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
          >
            <ChevronDown size={14} />
          </button>
        </div>
      </div>

      <div className="relative">
        <Search size={12} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Pesquisar indicadores…"
          className="w-full rounded-lg border border-zinc-800 bg-zinc-950/80 py-1.5 pl-8 pr-2 text-[11px] text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/40 focus:outline-none"
        />
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <button
          type="button"
          onClick={() => setActiveLayers([...LAYER_PRESETS.cruzarRiscos.layers])}
          title={LAYER_PRESETS.cruzarRiscos.description}
          className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-2 py-1 text-[10px] font-bold text-indigo-300 hover:bg-indigo-500/20"
        >
          {LAYER_PRESETS.cruzarRiscos.label}
        </button>
        <button
          type="button"
          onClick={() => setActiveLayers([])}
          className="rounded-lg border border-zinc-700 bg-zinc-950/70 px-2 py-1 text-[10px] font-bold text-zinc-400 hover:text-zinc-100"
        >
          Limpar
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
        {malhaIndisponivel && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-950/30 px-2.5 py-2 text-[10px] leading-relaxed text-amber-100">
            Malha de bairros indisponível — camadas socioeconômicas e por bairro desativadas.
          </div>
        )}

        {activeLayers.includes('socioeconomico') && setSocioSubcamada && (
          <div className="rounded-lg border border-amber-500/25 bg-amber-950/15 p-2">
            <p className="mb-1.5 text-[9px] font-bold uppercase tracking-wider text-amber-200">
              Subcamada socioeconômica
            </p>
            <div className="flex flex-wrap gap-1">
              {SOCIO_SUBCAMADAS.map((sub) => {
                const isActive = socioSubcamada === sub.id;
                return (
                  <button
                    key={sub.id}
                    type="button"
                    title={sub.description}
                    onClick={() => setSocioSubcamada(sub.id)}
                    className={`rounded-md border px-1.5 py-0.5 text-[9px] font-semibold transition ${
                      isActive
                        ? 'border-amber-400/50 bg-amber-500/20 text-amber-100'
                        : 'border-zinc-700 bg-zinc-950/60 text-zinc-400 hover:border-amber-700/40 hover:text-amber-100'
                    }`}
                  >
                    {sub.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {activeLayers.includes('territorios_especiais') && setTerritorioTipo && (
          <div className="rounded-lg border border-fuchsia-500/25 bg-fuchsia-950/15 p-2">
            <p className="mb-1.5 text-[9px] font-bold uppercase tracking-wider text-fuchsia-200">
              Territórios especiais — tipo
            </p>
            <div className="flex flex-wrap gap-1">
              {TERRITORIO_TIPOS.map((tipo) => {
                const isActive = territorioTipo === tipo.id;
                return (
                  <button
                    key={tipo.id}
                    type="button"
                    title={tipo.description}
                    onClick={() => setTerritorioTipo(tipo.id)}
                    className={`rounded-md border px-1.5 py-0.5 text-[9px] font-semibold transition ${
                      isActive
                        ? 'border-fuchsia-400/50 bg-fuchsia-500/20 text-fuchsia-100'
                        : 'border-zinc-700 bg-zinc-950/60 text-zinc-400 hover:border-fuchsia-700/40 hover:text-fuchsia-100'
                    }`}
                  >
                    {tipo.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {activeLayers.includes('educacao') && setEducacaoEtapa && (
          <div className="rounded-lg border border-sky-500/25 bg-sky-950/15 p-2">
            <p className="mb-1.5 text-[9px] font-bold uppercase tracking-wider text-sky-200">
              Educação INEP — etapa
            </p>
            <div className="flex flex-wrap gap-1">
              {EDUCACAO_ETAPAS.map((etapa) => {
                const isActive = educacaoEtapa === etapa.id;
                return (
                  <button
                    key={etapa.id}
                    type="button"
                    onClick={() => setEducacaoEtapa(etapa.id)}
                    className={`rounded-md border px-1.5 py-0.5 text-[9px] font-semibold transition ${
                      isActive
                        ? 'border-sky-400/50 bg-sky-500/20 text-sky-100'
                        : 'border-zinc-700 bg-zinc-950/60 text-zinc-400 hover:border-sky-700/40 hover:text-sky-100'
                    }`}
                  >
                    {etapa.label}
                  </button>
                );
              })}
            </div>
            {setEducacaoRaioM && (
              <label className="mt-2 flex flex-col gap-1 text-[9px] text-zinc-400">
                Buffer de influência ({educacaoRaioM} m)
                <input
                  type="range"
                  min={MIN_EDUCACAO_RAIO_M}
                  max={MAX_EDUCACAO_RAIO_M}
                  step={50}
                  value={educacaoRaioM}
                  onChange={(e) => setEducacaoRaioM(Number(e.target.value))}
                  className="w-full accent-sky-500"
                />
              </label>
            )}
            {setShowEducacaoBuffer && (
              <label className="mt-2 flex items-center gap-2 text-[9px] text-zinc-400">
                <input
                  type="checkbox"
                  checked={showEducacaoBuffer}
                  onChange={(e) => setShowEducacaoBuffer(e.target.checked)}
                  className="accent-sky-500"
                />
                Exibir buffer de influência
              </label>
            )}
          </div>
        )}

        {temporalActiveTemas.length > 0 && setLayerAnoForTema && (
          <TemporalYearPanel
            activeTemas={temporalActiveTemas}
            layerAnoByTema={layerAnoByTema}
            setLayerAnoForTema={setLayerAnoForTema}
          />
        )}

        {setShowRegionalOverlay && (
          <div className="rounded-lg border border-teal-500/25 bg-teal-950/15 p-2">
            <label className="flex items-center gap-2 text-[10px] font-bold text-teal-100">
              <input
                type="checkbox"
                checked={showRegionalOverlay}
                onChange={(e) => setShowRegionalOverlay(e.target.checked)}
                className="accent-teal-500"
              />
              <Eye size={12} className="text-teal-300" />
              Visualizar dados regionais
            </label>
            <p className="mt-1 text-[9px] leading-snug text-zinc-500">
              Overlay dos municípios do escopo IBGE carregados no Sinidu. Complementa o comparador.
            </p>
            {showRegionalOverlay && setRegionalEscopo && (
              <div className="mt-2 flex flex-wrap gap-1">
                {(Object.keys(REGIONAL_ESCOPO_LABELS) as RegionalEscopo[]).map((id) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setRegionalEscopo(id)}
                    className={`rounded-md border px-1.5 py-0.5 text-[9px] font-semibold ${
                      regionalEscopo === id
                        ? 'border-teal-400/50 bg-teal-500/20 text-teal-100'
                        : 'border-zinc-700 text-zinc-500 hover:text-teal-100'
                    }`}
                  >
                    {REGIONAL_ESCOPO_LABELS[id]}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {searchQuery.trim() && filteredLayerOptions.length === 0 && externalMatches.length === 0 && (
          <p className="px-1 text-[10px] italic text-zinc-500">Nenhuma camada local encontrada.</p>
        )}

        {layerGroups.map((group) => {
          const GroupIcon = GROUP_ICONS[group];
          const isGroupCollapsed = collapsedGroups[group];
          const groupLayers = filteredLayerOptions.filter((opt) => opt.group === group);
          const activeInGroup = groupLayers.filter((opt) => activeLayers.includes(opt.id)).length;

          return (
            <div key={group} className="rounded-lg border border-zinc-800/80 bg-zinc-950/30">
              <button
                type="button"
                onClick={() => toggleGroup(group)}
                className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-zinc-900/50"
              >
                {isGroupCollapsed ? (
                  <ChevronRight size={12} className="shrink-0 text-zinc-500" />
                ) : (
                  <ChevronDown size={12} className="shrink-0 text-zinc-500" />
                )}
                <GroupIcon size={12} className="shrink-0 text-indigo-400" />
                <span className="flex-1 text-[9px] font-extrabold uppercase tracking-wider text-zinc-400">
                  {group}
                </span>
                {activeInGroup > 0 && (
                  <span className="rounded-full bg-indigo-500/20 px-1.5 text-[8px] font-bold text-indigo-200">
                    {activeInGroup}
                  </span>
                )}
              </button>

              {!isGroupCollapsed && (
                <div className="flex flex-col gap-1 px-1 pb-1.5">
                  {groupLayers.map((opt) => {
                    const isActive = activeLayers.includes(opt.id);
                    const isDisabled = opt.disponivel === false;
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => !isDisabled && toggleLayer(opt.id)}
                        disabled={isDisabled}
                        title={
                          isActive && opt.descricao
                            ? `${opt.descricao}\n\nFonte: ${opt.source}${
                                opt.tooltipEstimado ? `\n\nNota: ${opt.tooltipEstimado}` : ''
                              }`
                            : opt.tooltipEstimado
                              || (isDisabled ? 'Camada indisponível — malha territorial ausente' : undefined)
                        }
                        className={`flex w-full items-center justify-between rounded-lg border px-2 py-1.5 text-left text-xs transition-all ${
                          isDisabled
                            ? 'cursor-not-allowed border-zinc-800 bg-zinc-950/40 text-zinc-600 opacity-60'
                            : isActive
                              ? 'border-indigo-500/40 bg-zinc-900 font-bold text-indigo-300'
                              : 'border-transparent text-zinc-400 hover:bg-zinc-900/40 hover:text-zinc-200'
                        }`}
                      >
                        <span className="flex min-w-0 flex-1 flex-col gap-1 pr-2">
                          <span className="truncate">{opt.label}</span>
                          <span className="flex flex-wrap gap-1">
                            <span
                              className={`rounded-md border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide ${
                                isActive
                                  ? 'border-indigo-400/40 bg-indigo-500/15 text-indigo-200'
                                  : 'border-zinc-700 bg-zinc-950/70 text-zinc-500'
                              }`}
                            >
                              {opt.source.split('/')[0].trim()}
                            </span>
                            <span className={`rounded-md border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide ${qualityTone(opt.quality)}`}>
                              {opt.quality === 'Oficial' && opt.id === 'bairros'
                                ? 'IBGE 2022'
                                : opt.quality}
                            </span>
                          </span>
                        </span>
                        <span
                          className={`flex h-4 w-4 items-center justify-center rounded border ${
                            isActive ? 'border-indigo-400 bg-indigo-500/20 text-indigo-200' : 'border-zinc-700'
                          }`}
                        >
                          {isActive && <Eye size={11} />}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}

        {externalMatches.length > 0 && (
          <div className="rounded-lg border border-cyan-500/25 bg-cyan-950/10 p-2">
            <p className="mb-1.5 text-[9px] font-bold uppercase tracking-wider text-cyan-300">
              GeoReDUS — referência externa
            </p>
            <div className="flex flex-col gap-1">
              {externalMatches.map((item) => (
                <a
                  key={item.id}
                  href={codigoIbge ? georedusMunicipioUrl(codigoIbge) : GEOREDUS_BASE_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={item.description}
                  className="flex items-start justify-between gap-2 rounded-lg border border-cyan-800/40 bg-zinc-950/50 px-2 py-1.5 text-left transition hover:border-cyan-600/50 hover:bg-cyan-950/30"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[11px] font-semibold text-cyan-100">{item.label}</span>
                    <span className="mt-0.5 block text-[8px] text-zinc-500">{item.source}</span>
                  </span>
                  <ExternalLink size={12} className="mt-0.5 shrink-0 text-cyan-400" />
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
