'use client';

import {
  Play,
  Pause,
  RotateCcw,
  AlertTriangle,
  Thermometer,
  FileText,
  Sparkles,
  Copy,
  ClipboardCheck,
  Building2,
  Users,
  School,
  Stethoscope,
} from 'lucide-react';
import {
  api,
  HeatLstComparison,
  MitigationPlan,
  RainfallComparison,
  SimulationInterpret,
  SimulationOutput,
  SlopeInterpretation,
} from '@/utils/api';
import RotatingLoader, { INTERPRETATION_MESSAGES } from '@/components/UI/RotatingLoader';
import TermTooltip from '@/components/UI/TermTooltip';
import SimulationNextSteps from './SimulationNextSteps';
import { formatDuration, isVolumeSimulation } from './simulationFormat';
import type { SimOverlayOptions, SimulationTab } from './SimulationPanel';

/**
 * 20f.2 — Seção de resultados pós-simulação, extraída de `SimulationPanel.tsx` (que tinha ~3270
 * linhas). Recebe todo o estado/handlers relevantes via props; nenhuma lógica foi reescrita, apenas
 * movida (JSX idêntico ao bloco original "Simulator Results").
 */
export interface SimulationResultsProps {
  result: SimulationOutput | null;
  mitigationPlan: MitigationPlan | null;
  simInterpret: SimulationInterpret | null;
  slopeInterpret: SlopeInterpretation | null;
  analysisLoading: boolean;
  interpretError: string | null;
  copyOk: boolean;
  exportLoading: 'geojson' | 'pdf' | 'kmz' | 'csv' | null;
  rainfallComparison: RainfallComparison | null;
  heatLstComparison: HeatLstComparison | null;
  lstCompareLoading: boolean;
  activeTab: SimulationTab;
  rainfallMm: number;
  compareRainfall: boolean;
  baselineRainfallMm: number;
  floodTIndex: number;
  floodPlaying: boolean;
  floodLoop: boolean;
  floodSpeedMs: number;
  calibBusy: boolean;
  calibMsg: string | null;
  codigoIbge?: string;
  overlayOptions: SimOverlayOptions;
  onOverlayChange: (options: SimOverlayOptions) => void;
  mapMode3dActive: boolean;
  onView3D?: () => void;
  onFocusWorkshop?: () => void;
  onCrossRiskLayers?: () => void;
  setFloodPlaying: (updater: boolean | ((prev: boolean) => boolean)) => void;
  setFloodTIndex: (value: number) => void;
  setFloodSpeedMs: (value: number) => void;
  setFloodLoop: (value: boolean) => void;
  setCalibBusy: (value: boolean) => void;
  setCalibMsg: (value: string | null) => void;
  applyFloodTimelineFrame: (data: SimulationOutput, tIndex: number, playing?: boolean) => void;
  runInterpret: (
    data: SimulationOutput,
    comparison: RainfallComparison | null,
    lstComparison?: HeatLstComparison | null,
  ) => Promise<void> | void;
  handleExportGeojson: () => void | Promise<void>;
  handleExportKmz: () => void | Promise<void>;
  handleExportPdf: () => void | Promise<void>;
  handleExportImpactsCsv: () => void | Promise<void>;
  handleIncludeInReport: () => void;
  handleCopyInterpret: () => void | Promise<void>;
  simulationTipo: () => 'chuva' | 'asfalto' | 'vegetacao' | 'drenagem' | 'calor';
}

export default function SimulationResults({
  result,
  mitigationPlan,
  simInterpret,
  slopeInterpret,
  analysisLoading,
  interpretError,
  copyOk,
  exportLoading,
  rainfallComparison,
  heatLstComparison,
  lstCompareLoading,
  activeTab,
  rainfallMm,
  compareRainfall,
  baselineRainfallMm,
  floodTIndex,
  floodPlaying,
  floodLoop,
  floodSpeedMs,
  calibBusy,
  calibMsg,
  codigoIbge,
  overlayOptions,
  onOverlayChange,
  mapMode3dActive,
  onView3D,
  onFocusWorkshop,
  onCrossRiskLayers,
  setFloodPlaying,
  setFloodTIndex,
  setFloodSpeedMs,
  setFloodLoop,
  setCalibBusy,
  setCalibMsg,
  applyFloodTimelineFrame,
  runInterpret,
  handleExportGeojson,
  handleExportKmz,
  handleExportPdf,
  handleExportImpactsCsv,
  handleIncludeInReport,
  handleCopyInterpret,
  simulationTipo,
}: SimulationResultsProps) {
  return (
    <>
      {/* Simulator Results */}
      {result && onView3D && onFocusWorkshop && onCrossRiskLayers && (
        <SimulationNextSteps
          scenarioLabel={
            activeTab === 'rainfall'
              ? `${rainfallMm} mm${compareRainfall ? ` vs ${baselineRainfallMm} mm` : ''}`
              : result.scenario_type || 'Simulação'
          }
          isVolumeSim={isVolumeSimulation(result.geometry)}
          auto3dApplied={mapMode3dActive && isVolumeSimulation(result.geometry)}
          fromCache={result.from_cache}
          onView3D={onView3D}
          onFocusWorkshop={onFocusWorkshop}
          onCrossRiskLayers={onCrossRiskLayers}
          onExportPdf={handleExportPdf}
          exportPdfLoading={exportLoading === 'pdf'}
        />
      )}

      {result && (
        <div className="bg-card/40 border border-border p-4 rounded-xl flex flex-col gap-4 animate-fadeIn">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h4 className="font-extrabold text-zinc-200 text-xs uppercase tracking-wide">Resultados da Simulação</h4>
              {result.simulation_meta?.dem_available && (
                <p className="mt-0.5 text-[9px] text-lime-400/80 font-mono">
                  DEM: {result.simulation_meta.dem_source} · Δh max {result.simulation_meta.max_depth_m} m
                  {result.simulation_meta.flood_patches != null && (
                    <> · {result.simulation_meta.flood_patches} manchas</>
                  )}
                  {result.simulation_meta.dem_hydro_conditioned && (
                    <span className="ml-1 text-teal-300">· hidro-corrigido</span>
                  )}
                  {result.from_cache && (
                    <span className="ml-1 text-sky-300">· cache</span>
                  )}
                </p>
              )}
            </div>
            {result.simulation_meta?.method && (
              <span className="rounded border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[8px] font-bold uppercase text-indigo-200">
                {result.simulation_meta.method}
                {result.simulation_meta.model_version && (
                  <> · v{result.simulation_meta.model_version}</>
                )}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleExportGeojson}
              disabled={exportLoading !== null}
              className="rounded-lg border border-lime-500/30 bg-lime-950/20 px-3 py-1.5 text-[10px] font-bold uppercase text-lime-200 hover:bg-lime-950/40 disabled:opacity-50"
            >
              {exportLoading === 'geojson' ? 'Exportando…' : 'Exportar GeoJSON'}
            </button>
            <button
              type="button"
              onClick={handleExportKmz}
              disabled={exportLoading !== null || !result.geometry}
              title="Abre no Google Earth, QGIS ou ArcGIS"
              className="rounded-lg border border-amber-500/30 bg-amber-950/20 px-3 py-1.5 text-[10px] font-bold uppercase text-amber-200 hover:bg-amber-950/40 disabled:opacity-50"
            >
              {exportLoading === 'kmz' ? 'Gerando KMZ…' : 'Exportar KMZ'}
            </button>
            <button
              type="button"
              onClick={handleExportPdf}
              disabled={exportLoading !== null}
              className="rounded-lg border border-sky-500/30 bg-sky-950/20 px-3 py-1.5 text-[10px] font-bold uppercase text-sky-200 hover:bg-sky-950/40 disabled:opacity-50"
            >
              {exportLoading === 'pdf' ? 'Gerando PDF…' : 'PDF para oficina'}
            </button>
            <button
              type="button"
              onClick={handleExportImpactsCsv}
              disabled={exportLoading !== null}
              title="Lista vias intransitáveis e escolas/UBS atingidos"
              className="rounded-lg border border-rose-500/30 bg-rose-950/20 px-3 py-1.5 text-[10px] font-bold uppercase text-rose-200 hover:bg-rose-950/40 disabled:opacity-50"
            >
              {exportLoading === 'csv' ? 'Gerando CSV…' : 'CSV impactos'}
            </button>
          </div>

          {result.simulation_meta?.glofas_compare?.ok && (
            <div className="rounded-lg border border-indigo-500/25 bg-indigo-950/20 px-3 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-indigo-200">
                Confrontação GloFAS RP100
              </p>
              <p className="mt-1 text-[11px] text-indigo-100/90">
                Overlap com hazard de referência:{' '}
                <span className="font-semibold text-indigo-50">
                  {result.simulation_meta.glofas_compare.overlap_pct}%
                </span>
                {result.simulation_meta.glofas_compare.intersection_km2 != null && (
                  <> · {result.simulation_meta.glofas_compare.intersection_km2} km²</>
                )}
              </p>
              {result.simulation_meta.glofas_compare.nota && (
                <p className="mt-1 text-[10px] leading-snug text-indigo-200/70">
                  {result.simulation_meta.glofas_compare.nota}
                </p>
              )}
            </div>
          )}

          {result.scenario_type === 'ExtremeRainfall' && (
            <div className="rounded-lg border border-sky-500/25 bg-sky-950/20 px-3 py-2.5">
              <div className="flex flex-wrap items-center justify-between gap-1.5">
                <p className="text-[11px] font-semibold text-sky-100">Impacto do evento simulado</p>
                {result.simulation_meta?.impacto_operacional?.regime_chuva && (
                  <span
                    title={result.simulation_meta.impacto_operacional.regime_chuva.nota}
                    className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[9px] font-bold uppercase text-violet-200"
                  >
                    {result.simulation_meta.impacto_operacional.regime_chuva.label} ·{' '}
                    {result.simulation_meta.impacto_operacional.regime_chuva.intensidade_mm_h} mm/h
                  </span>
                )}
              </div>
              <div className="mt-2 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
                <div className="rounded border border-zinc-800 bg-zinc-950/50 px-2 py-1.5">
                  <p className="text-[9px] uppercase text-zinc-500">Área alagada</p>
                  <p className="text-[13px] font-extrabold text-zinc-100">{result.affected_area_km2} km²</p>
                </div>
                <div className="rounded border border-zinc-800 bg-zinc-950/50 px-2 py-1.5">
                  <p className="text-[9px] uppercase text-zinc-500">População</p>
                  <p className="text-[13px] font-extrabold text-zinc-100">
                    {result.affected_population.toLocaleString('pt-BR')}
                  </p>
                </div>
                <div className="rounded border border-zinc-800 bg-zinc-950/50 px-2 py-1.5">
                  <p className="text-[9px] uppercase text-zinc-500">Prof. máx.</p>
                  <p className="text-[13px] font-extrabold text-zinc-100">
                    {result.simulation_meta?.max_depth_m ?? '—'} m
                  </p>
                </div>
                <div className="rounded border border-zinc-800 bg-zinc-950/50 px-2 py-1.5">
                  <p className="text-[9px] uppercase text-zinc-500">Deslizamento</p>
                  <p className="text-[13px] font-extrabold text-amber-200">
                    {result.simulation_meta?.impacto_operacional?.deslizamento?.nivel
                      ?? `${result.simulation_meta?.landslide_zones ?? 0} zonas`}
                  </p>
                </div>
              </div>
              {result.simulation_meta?.impacto_operacional && (
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  <div className="rounded border border-teal-500/20 bg-teal-950/15 px-2.5 py-2">
                    <p className="text-[9px] font-extrabold uppercase tracking-wider text-teal-300">
                      Tempo de escoamento
                    </p>
                    <p className="mt-1 text-[11px] text-zinc-200">
                      Sem intervenção:{' '}
                      <strong>
                        {result.simulation_meta.impacto_operacional.escoamento?.tempo_sem_intervencao_h ?? '—'} h
                      </strong>
                    </p>
                    <p className="text-[11px] text-zinc-200">
                      Com intervenções sugeridas:{' '}
                      <strong className="text-teal-200">
                        {result.simulation_meta.impacto_operacional.escoamento?.tempo_com_intervencoes_h ?? '—'} h
                      </strong>
                      {result.simulation_meta.impacto_operacional.escoamento?.reducao_pct != null && (
                        <span className="text-zinc-500">
                          {' '}(−{result.simulation_meta.impacto_operacional.escoamento.reducao_pct}%)
                        </span>
                      )}
                    </p>
                    <p className="mt-1 text-[9px] leading-snug text-zinc-500">
                      {result.simulation_meta.impacto_operacional.escoamento?.nota}
                    </p>
                  </div>
                  <div className="rounded border border-amber-500/20 bg-amber-950/15 px-2.5 py-2">
                    <p className="text-[9px] font-extrabold uppercase tracking-wider text-amber-300">
                      Direito de ir e vir
                    </p>
                    <p className="mt-1 text-[11px] text-zinc-200">
                      Nível:{' '}
                      <strong>
                        {result.simulation_meta.impacto_operacional.mobilidade?.nivel ?? '—'}
                      </strong>
                    </p>
                    <p className="text-[11px] text-zinc-200">
                      {(
                        result.simulation_meta.impacto_operacional.mobilidade
                          ?.populacao_com_ir_e_vir_impedido ?? 0
                      ).toLocaleString('pt-BR')}{' '}
                      pessoas com mobilidade comprometida · ~
                      {result.simulation_meta.impacto_operacional.mobilidade?.vias_comprometidas_km_proxy ?? 0}{' '}
                      km de vias (proxy)
                    </p>
                    <p className="mt-1 text-[9px] leading-snug text-zinc-500">
                      {result.simulation_meta.impacto_operacional.mobilidade?.nota}
                    </p>
                  </div>
                </div>
              )}
              {result.simulation_meta?.ancora_historica && (
                <div className="mt-2 rounded border border-amber-500/25 bg-amber-950/10 px-2.5 py-2">
                  <p className="text-[9px] font-extrabold uppercase tracking-wider text-amber-200">
                    Âncora histórica próxima (±{result.simulation_meta.ancora_historica.delta_mm} mm
                    {result.simulation_meta.ancora_historica.delta_duracao_h != null && (
                      <> · ±{result.simulation_meta.ancora_historica.delta_duracao_h}h duração</>
                    )}
                    )
                  </p>
                  {result.simulation_meta.ancora_historica.duracao_h != null && (
                    <p className="mt-0.5 text-[10px] text-zinc-400">
                      Evento observado: {Math.round(result.simulation_meta.ancora_historica.precipitacao_mm ?? 0)} mm
                      {' '}em {formatDuration(result.simulation_meta.ancora_historica.duracao_h * 60)}
                    </p>
                  )}
                  <p className="mt-0.5 text-[11px] font-semibold text-zinc-100">
                    {result.simulation_meta.ancora_historica.url ? (
                      <a
                        href={result.simulation_meta.ancora_historica.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline decoration-amber-500/40 underline-offset-2 hover:text-amber-100"
                      >
                        {result.simulation_meta.ancora_historica.label}
                      </a>
                    ) : (
                      result.simulation_meta.ancora_historica.label
                    )}
                    {result.simulation_meta.ancora_historica.data
                      ? ` · ${result.simulation_meta.ancora_historica.data}`
                      : ''}
                  </p>
                  {result.simulation_meta.ancora_historica.bairros && (
                    <p className="mt-0.5 text-[10px] text-zinc-400">
                      Bairros observados: {result.simulation_meta.ancora_historica.bairros.slice(0, 6).join(', ')}
                    </p>
                  )}
                  <p className="mt-1 text-[9px] leading-snug text-zinc-500">
                    {result.simulation_meta.ancora_historica.nota}
                  </p>
                </div>
              )}
              {result.affected_bairros?.length > 0 && (
                <p className="mt-2 text-[10px] text-zinc-400">
                  Bairros na mancha:{' '}
                  <span className="text-zinc-200">
                    {result.affected_bairros.slice(0, 10).join(', ')}
                    {result.affected_bairros.length > 10 ? '…' : ''}
                  </span>
                </p>
              )}
            </div>
          )}

          {result.scenario_type === 'ExtremeRainfall' && result.simulation_meta?.uncertainty_bands && (
            <div className="rounded-lg border border-amber-500/25 bg-amber-950/20 px-3 py-2.5">
              <p className="text-[11px] font-semibold text-amber-100">
                Faixa de incerteza do modelo
              </p>
              <p className="mt-0.5 text-[10px] leading-snug text-zinc-400">
                Se a chuva for um pouco menor ou maior (±{result.simulation_meta.uncertainty_bands.precip_delta_pct ?? 15}%), a profundidade e a área mudam assim:
              </p>
              <div className="mt-2 grid grid-cols-3 gap-1.5 text-center">
                {(
                  [
                    ['optimistic', 'Chuva menor', 'text-emerald-300'],
                    ['expected', 'Cenário atual', 'text-sky-300'],
                    ['pessimistic', 'Chuva maior', 'text-rose-300'],
                  ] as const
                ).map(([key, label, tone]) => {
                  const band = result.simulation_meta?.uncertainty_bands?.[key];
                  if (!band) return null;
                  return (
                    <div key={key} className="rounded border border-zinc-800 bg-zinc-950/50 px-1.5 py-1.5">
                      <p className={`text-[9px] font-bold ${tone}`}>{label}</p>
                      <p className="text-[11px] font-extrabold text-zinc-100">
                        até {band.max_depth_m?.toFixed?.(1) ?? band.max_depth_m} m
                      </p>
                      <p className="text-[9px] text-zinc-500">
                        {(band.affected_population ?? 0).toLocaleString?.('pt-BR') ?? band.affected_population} pessoas
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {result.scenario_type === 'ExtremeRainfall' && result.simulation_meta?.flood_timeline && (
            <div className="sticky bottom-0 z-10 rounded-lg border border-sky-500/25 bg-sky-950/90 px-3 py-2.5 shadow-lg backdrop-blur-md">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-[11px] font-semibold text-sky-100">Evolução no tempo</p>
                  <p className="text-[10px] text-zinc-400">
                    Como a mancha sobe e baixa ao longo de {result.simulation_meta.flood_timeline.duration_h} h
                    · {result.simulation_meta.flood_timeline.n_steps} frames (aproximação — não é hidrodinâmica 2D).
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => {
                      const peak = result.simulation_meta?.flood_timeline?.peak_index ?? 0;
                      setFloodPlaying(false);
                      setFloodTIndex(peak);
                      applyFloodTimelineFrame(result, peak, false);
                    }}
                    className="inline-flex items-center gap-1 rounded border border-zinc-600 bg-zinc-900/80 px-2 py-1 text-[10px] font-bold text-zinc-200 hover:bg-zinc-800"
                    title="Ir ao pico"
                  >
                    <RotateCcw size={12} />
                    Pico
                  </button>
                  <button
                    type="button"
                    disabled={!result.simulation_meta?.flood_timeline_features?.length}
                    onClick={() => setFloodPlaying((p) => !p)}
                    className="inline-flex items-center gap-1 rounded border border-sky-500/40 bg-sky-500/10 px-2 py-1 text-[10px] font-bold text-sky-100 hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {floodPlaying ? <Pause size={12} /> : <Play size={12} />}
                    {floodPlaying ? 'Pausar' : 'Animar'}
                  </button>
                </div>
              </div>
              {!result.simulation_meta?.flood_timeline_features?.length && (
                <p className="mt-2 flex items-start gap-1.5 rounded border border-amber-500/30 bg-amber-950/30 px-2 py-1.5 text-[10px] text-amber-100">
                  <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                  Frames da mancha não vieram nesta resposta — rode a simulação de novo para animar o mapa.
                </p>
              )}
              {(() => {
                const tl = result.simulation_meta!.flood_timeline!;
                const step = tl.steps[floodTIndex] || tl.steps[tl.peak_index];
                return (
                  <div className="mt-2 space-y-1.5">
                    <input
                      type="range"
                      min={0}
                      max={tl.n_steps - 1}
                      step={1}
                      value={floodTIndex}
                      onChange={(e) => {
                        const idx = Number(e.target.value);
                        setFloodPlaying(false);
                        setFloodTIndex(idx);
                        applyFloodTimelineFrame(result, idx, false);
                      }}
                      className="w-full accent-sky-400"
                    />
                    <div className="flex flex-wrap items-center justify-between gap-2 text-[10px]">
                      <span className="font-semibold text-sky-200 capitalize">
                        {step?.fase || '—'} · t = {step?.t_h ?? 0} h
                      </span>
                      <span className="font-mono text-zinc-400">
                        até {step?.max_depth_m ?? '—'} m · {step?.flood_patches ?? 0} manchas
                      </span>
                    </div>
                    <p className="text-[10px] leading-snug text-zinc-300">
                      {step?.narrativa
                        || 'Olhe o mapa à direita — a mancha acompanha este instante.'}
                    </p>
                    <div className="flex flex-wrap items-center gap-3 pt-0.5">
                      <label className="flex items-center gap-1.5 text-[9px] text-zinc-400">
                        Ritmo
                        <select
                          value={floodSpeedMs}
                          onChange={(e) => setFloodSpeedMs(Number(e.target.value))}
                          className="rounded border border-zinc-700 bg-zinc-950 px-1.5 py-0.5 text-[10px] text-zinc-200"
                        >
                          <option value={800}>Lento</option>
                          <option value={500}>Normal</option>
                          <option value={280}>Rápido</option>
                        </select>
                      </label>
                      <label className="flex items-center gap-1.5 text-[9px] text-zinc-400">
                        <input
                          type="checkbox"
                          checked={floodLoop}
                          onChange={(e) => setFloodLoop(e.target.checked)}
                          className="accent-sky-400"
                        />
                        Loop
                      </label>
                      <span className="text-[8px] text-zinc-600">Selo Derivado · triagem ≠ laudo</span>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          <div className="h-px bg-zinc-800 w-full" />

          {(analysisLoading || simInterpret || interpretError) && (
            <div
              id="interpretacao-ia"
              className="animate-fadeIn rounded-xl border border-zinc-800 border-l-4 border-l-[#1D9E75] bg-card/40 p-4 flex flex-col gap-3"
            >
              <div className="flex items-center justify-between gap-2">
                <h4 className="font-extrabold text-zinc-200 text-xs uppercase tracking-wide flex items-center gap-1.5">
                  <Sparkles size={14} className="text-[#1D9E75]" />
                  Interpretação Sinidu·IA
                </h4>
                {simInterpret && (
                  <div className="flex flex-wrap items-center gap-1.5">
                    {simInterpret.from_cache && (
                      <span className="rounded border border-sky-500/30 bg-sky-950/30 px-2 py-0.5 text-[8px] font-bold uppercase text-sky-200">
                        cache
                      </span>
                    )}
                    <span className="rounded border border-teal-500/30 bg-teal-950/30 px-2 py-0.5 text-[8px] font-bold uppercase text-teal-200">
                      Modelo: {simInterpret.ai_provider === 'deterministic' ? 'Regras' : simInterpret.ai_provider || 'Mistral'}
                    </span>
                  </div>
                )}
              </div>

              {analysisLoading && (
                <div className="space-y-2">
                  <RotatingLoader messages={INTERPRETATION_MESSAGES} className="text-teal-200" />
                  <div className="h-3 w-full animate-pulse rounded bg-zinc-800/80" />
                  <div className="h-3 w-5/6 animate-pulse rounded bg-zinc-800/60" />
                </div>
              )}

              {interpretError && !analysisLoading && (
                <div className="rounded border border-rose-500/30 bg-rose-950/20 p-2">
                  <p className="text-[10px] text-rose-200">{interpretError}</p>
                  <button
                    type="button"
                    onClick={() => void runInterpret(result, rainfallComparison, heatLstComparison)}
                    className="mt-2 text-[9px] font-bold uppercase text-rose-300 underline"
                  >
                    Tentar novamente
                  </button>
                </div>
              )}

              {simInterpret && !analysisLoading && (
                <>
                  <div>
                    <span className="text-[9px] font-bold uppercase tracking-wider text-teal-400">Resumo</span>
                    <p className="mt-1 text-[11px] leading-relaxed text-zinc-200">{simInterpret.resumo_executivo}</p>
                  </div>

                  {simInterpret.areas_criticas.length > 0 && (
                    <div>
                      <span className="text-[9px] font-bold uppercase tracking-wider text-teal-400">Áreas críticas</span>
                      <ul className="mt-1 space-y-0.5">
                        {simInterpret.areas_criticas.map((a) => (
                          <li key={a} className="text-[10px] text-zinc-300">• {a}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {simInterpret.equipamentos_em_risco.length > 0 && (
                    <div>
                      <span className="text-[9px] font-bold uppercase tracking-wider text-teal-400">Equipamentos em risco</span>
                      <ul className="mt-1 space-y-0.5">
                        {simInterpret.equipamentos_em_risco.slice(0, 4).map((e) => (
                          <li key={e} className="text-[10px] text-amber-200/90">• {e}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {simInterpret.comparacao_historica && (
                    <p className="text-[10px] text-zinc-400">
                      <span className="text-zinc-500">≈ Histórico:</span> {simInterpret.comparacao_historica}
                    </p>
                  )}

                  {simInterpret.interpretacao_diferencial && (
                    <div className="rounded border border-indigo-500/25 bg-indigo-950/20 p-2">
                      <span className="text-[9px] font-bold uppercase text-indigo-300">Comparação vs referência</span>
                      <p className="mt-1 text-[10px] leading-relaxed text-indigo-100/90">
                        {simInterpret.interpretacao_diferencial}
                      </p>
                    </div>
                  )}

                  {simInterpret.recomendacoes_imediatas.length > 0 && (
                    <div>
                      <span className="text-[9px] font-bold uppercase tracking-wider text-emerald-400">Recomendações</span>
                      <ul className="mt-1 space-y-0.5">
                        {simInterpret.recomendacoes_imediatas.map((r) => (
                          <li key={r} className="text-[10px] text-emerald-200/90">→ {r}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {slopeInterpret && (
                    <div className="rounded border border-rose-500/25 bg-rose-950/15 p-2">
                      <span className="text-[9px] font-bold uppercase text-rose-300">
                        Encostas · {slopeInterpret.nivel_suscetibilidade} · COBRADE {slopeInterpret.referencia_cobrade}
                      </span>
                      <p className="mt-1 text-[10px] leading-relaxed text-rose-100/80">{slopeInterpret.interpretacao_ia}</p>
                    </div>
                  )}

                  <p className="text-[8px] italic text-zinc-600">{simInterpret.disclaimer}</p>

                  <div className="flex flex-wrap gap-2 pt-1">
                    <button
                      type="button"
                      onClick={handleIncludeInReport}
                      disabled={exportLoading === 'pdf'}
                      className="flex items-center gap-1 rounded-lg border border-teal-600/40 bg-teal-950/30 px-2.5 py-1.5 text-[9px] font-bold uppercase text-teal-200 hover:bg-teal-900/40 disabled:opacity-50"
                    >
                      <FileText size={11} />
                      {exportLoading === 'pdf' ? 'Gerando…' : 'Incluir no Relatório PDF'}
                    </button>
                    <button
                      type="button"
                      onClick={handleCopyInterpret}
                      className="flex items-center gap-1 rounded-lg border border-zinc-700 px-2.5 py-1.5 text-[9px] font-bold uppercase text-zinc-300 hover:bg-zinc-900"
                    >
                      {copyOk ? <ClipboardCheck size={11} className="text-teal-400" /> : <Copy size={11} />}
                      {copyOk ? 'Copiado' : 'Copiar'}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {rainfallComparison && activeTab === 'rainfall' && (
            <div className="rounded-lg border border-amber-500/25 bg-amber-950/15 p-3">
              <span className="text-[9px] font-extrabold uppercase tracking-wider text-amber-200 block mb-2">
                Delta vs referência ({rainfallComparison.delta.baseline_mm} mm → {rainfallComparison.delta.scenario_mm} mm)
              </span>
              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div className="rounded border border-zinc-800 bg-zinc-950/60 p-2">
                  <span className="text-zinc-500 block">Área adicional</span>
                  <strong className="text-amber-200">+{rainfallComparison.delta.affected_area_km2} km²</strong>
                </div>
                <div className="rounded border border-zinc-800 bg-zinc-950/60 p-2">
                  <span className="text-zinc-500 block">População adicional</span>
                  <strong className="text-amber-200">+{rainfallComparison.delta.affected_population.toLocaleString()} hab</strong>
                </div>
                <div className="rounded border border-zinc-800 bg-zinc-950/60 p-2">
                  <span className="text-zinc-500 block">Δ profundidade máx.</span>
                  <strong className="text-amber-200">+{rainfallComparison.delta.max_depth_m} m</strong>
                </div>
                <div className="rounded border border-zinc-800 bg-zinc-950/60 p-2">
                  <span className="text-zinc-500 block">Novos bairros</span>
                  <strong className="text-amber-200">{rainfallComparison.delta.bairros_novos.length}</strong>
                </div>
              </div>
              {rainfallComparison.delta.bairros_novos.length > 0 && (
                <p className="mt-2 text-[9px] text-zinc-400">
                  Novos bairros expostos: {rainfallComparison.delta.bairros_novos.slice(0, 8).join(', ')}
                  {rainfallComparison.delta.bairros_novos.length > 8 ? '…' : ''}
                </p>
              )}
            </div>
          )}

          {(lstCompareLoading || heatLstComparison) && activeTab === 'heat_island' && (
            <div className="rounded-lg border border-emerald-500/25 bg-emerald-950/15 p-3">
              <span className="text-[9px] font-extrabold uppercase tracking-wider text-emerald-200 block mb-2">
                Observado × Derivado — LST GeoReDUS vs cenário Sinidu
              </span>
              {lstCompareLoading && (
                <p className="text-[10px] text-zinc-400 italic">Consultando LST observada nos bairros críticos…</p>
              )}
              {heatLstComparison && !lstCompareLoading && (
                <>
                  <div className="grid grid-cols-2 gap-2 text-[10px]">
                    <div className="rounded border border-sky-500/25 bg-zinc-950/60 p-2">
                      <span className="text-zinc-500 block">LST GeoReDUS · Observado</span>
                      <strong className="text-sky-200">
                        {heatLstComparison.lst_mediana_c != null ? `${heatLstComparison.lst_mediana_c}°C` : '—'}
                      </strong>
                    </div>
                    <div className="rounded border border-indigo-500/25 bg-zinc-950/60 p-2">
                      <span className="text-zinc-500 block">Sinidu · Derivado</span>
                      <strong className="text-rose-200">
                        {heatLstComparison.sim_temp_mediana_c != null ? `${heatLstComparison.sim_temp_mediana_c}°C` : '—'}
                      </strong>
                    </div>
                    <div className="rounded border border-zinc-800 bg-zinc-950/60 p-2">
                      <span className="text-zinc-500 block">Δ mediano</span>
                      <strong className="text-emerald-200">
                        {heatLstComparison.divergencia_mediana_c != null
                          ? `${heatLstComparison.divergencia_mediana_c > 0 ? '+' : ''}${heatLstComparison.divergencia_mediana_c}°C`
                          : '—'}
                      </strong>
                    </div>
                    <div className="rounded border border-zinc-800 bg-zinc-950/60 p-2">
                      <span className="text-zinc-500 block">Amostras LST</span>
                      <strong className="text-emerald-200">
                        {heatLstComparison.amostras_validas}/{heatLstComparison.amostras_total}
                      </strong>
                    </div>
                  </div>
                  <p className="mt-2 text-[10px] leading-relaxed text-zinc-300">{heatLstComparison.narrativa}</p>
                  {heatLstComparison.bairros.length > 0 && heatLstComparison.disponivel && (
                    <div className="mt-2 max-h-28 overflow-y-auto rounded border border-zinc-800/80 bg-zinc-950/50">
                      <table className="w-full text-[9px]">
                        <thead>
                          <tr className="text-left text-zinc-500 border-b border-zinc-800">
                            <th className="px-2 py-1 font-bold">Bairro</th>
                            <th className="px-2 py-1 font-bold">LST · Obs.</th>
                            <th className="px-2 py-1 font-bold">Sinidu · Deriv.</th>
                            <th className="px-2 py-1 font-bold">Δ</th>
                          </tr>
                        </thead>
                        <tbody>
                          {heatLstComparison.bairros
                            .filter((row) => row.lst_observada_c != null)
                            .slice(0, 8)
                            .map((row) => (
                              <tr key={row.bairro} className="border-b border-zinc-900/80 text-zinc-300">
                                <td className="px-2 py-1 truncate max-w-[90px]">{row.bairro}</td>
                                <td className="px-2 py-1 text-sky-300">{row.lst_observada_c}°</td>
                                <td className="px-2 py-1 text-rose-300">{row.temp_simulada_c}°</td>
                                <td className="px-2 py-1 text-emerald-300">
                                  {row.delta_c != null ? `${row.delta_c > 0 ? '+' : ''}${row.delta_c}°` : '—'}
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {heatLstComparison.limites_metodologicos.length > 0 && (
                    <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[9px] italic text-zinc-500">
                      {heatLstComparison.limites_metodologicos.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-zinc-950/60 p-2.5 rounded-lg border border-zinc-800">
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block">
                {result.scenario_type === 'potencial_solar_telhado' ? 'Área de telhado' : 'Área Afetada'}
              </span>
              <span className="text-sm font-extrabold text-zinc-200">{result.affected_area_km2} km²</span>
            </div>
            <div className="bg-zinc-950/60 p-2.5 rounded-lg border border-zinc-800">
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block">Impacto Estimado</span>
              <span className="text-sm font-extrabold text-accent-rose">
                {result.scenario_type === 'VegetationLoss' || result.scenario_type === 'HeatIsland'
                  ? `+${result.impact_value}°C`
                  : result.scenario_type === 'potencial_solar_telhado'
                    ? `${Number(result.impact_value).toLocaleString()} kWp`
                    : result.scenario_type === 'telhado_verde_permeabilidade'
                      ? `${Number(result.impact_value).toLocaleString()} km² evitados`
                      : `${result.impact_value.toLocaleString()} hab`}
              </span>
            </div>
          </div>

          {result.scenario_type === 'potencial_solar_telhado' && (
            <div className="rounded-lg border border-amber-500/25 bg-amber-950/20 px-3 py-2.5 text-[11px] text-zinc-300">
              <p className="text-[9px] font-extrabold uppercase tracking-wider text-amber-300">Potencial solar</p>
              <p className="mt-1">
                {(result as { potencia_total_mwp?: number }).potencia_total_mwp ?? '—'} MWp ·{' '}
                {(result as { geracao_total_mwh_ano?: number }).geracao_total_mwh_ano ?? '—'} MWh/ano ·{' '}
                {(result as { edificios_avaliados?: number }).edificios_avaliados ?? 0} edifícios
              </p>
            </div>
          )}

          {result.scenario_type === 'telhado_verde_permeabilidade' && (result as { delta?: { area_evitada_km2?: number; populacao_evitada?: number } }).delta && (
            <div className="rounded-lg border border-lime-500/25 bg-lime-950/20 px-3 py-2.5 text-[11px] text-zinc-300">
              <p className="text-[9px] font-extrabold uppercase tracking-wider text-lime-300">Mitigação telhado verde</p>
              <p className="mt-1">
                Área evitada: {(result as { delta: { area_evitada_km2?: number } }).delta.area_evitada_km2 ?? 0} km² ·
                Pop. evitada: {((result as { delta: { populacao_evitada?: number } }).delta.populacao_evitada ?? 0).toLocaleString()}
              </p>
            </div>
          )}

          {result.scenario_type === 'infraestrutura_verde_calor' && (
            <div className="rounded-lg border border-lime-500/25 bg-lime-950/20 px-3 py-2.5 text-[11px] text-zinc-300">
              <p className="text-[9px] font-extrabold uppercase tracking-wider text-lime-300">Infraverde × calor</p>
              <p className="mt-1">
                Resfriamento até {(result as { delta?: { resfriamento_max_c?: number } }).delta?.resfriamento_max_c ?? result.impact_value} °C ·
                {((result as { delta?: { populacao_menos_exposta?: number } }).delta?.populacao_menos_exposta ?? 0).toLocaleString()} hab. menos expostos
              </p>
            </div>
          )}

          {result.scenario_type === 'comparador_intervencoes' && (
            <div className="rounded-lg border border-indigo-500/25 bg-indigo-950/20 px-3 py-2.5 text-[11px] text-zinc-300">
              <p className="text-[9px] font-extrabold uppercase tracking-wider text-indigo-300">Antes → Depois</p>
              <p className="mt-1 text-[10px] text-zinc-400">
                {(result as { label_antes?: string }).label_antes} → {(result as { label_depois?: string }).label_depois}
              </p>
              <p className="mt-1">
                {(result as { delta?: { resumo?: string } }).delta?.resumo || result.metric_impact}
              </p>
            </div>
          )}

          {result.scenario_type === 'sombra_insolacao' && (
            <div className="rounded-lg border border-amber-500/25 bg-amber-950/20 px-3 py-2.5 text-[11px] text-zinc-300">
              <p className="text-[9px] font-extrabold uppercase tracking-wider text-amber-300">Sombra / insolação</p>
              <p className="mt-1">
                Índice médio {result.impact_value} · sol elev. {(result as { sol?: { elevacao_graus?: number } }).sol?.elevacao_graus ?? '—'}° ·
                sombra {(result as { resumo?: { sombra_media?: number } }).resumo?.sombra_media ?? '—'}
              </p>
            </div>
          )}

          {result.scenario_type === 'ExtremeRainfall' && result.simulation_meta?.exposicao_cenario && (
            <div className="rounded-lg border border-cyan-500/25 bg-cyan-950/20 px-3 py-2.5">
              <p className="text-[9px] font-extrabold uppercase tracking-wider text-cyan-300">
                Exposição do cenário · edifícios × inundação
              </p>
              {result.simulation_meta.exposicao_cenario.disponivel ? (
                <>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-zinc-300 sm:grid-cols-4">
                    <span className="flex items-center gap-1.5">
                      <Building2 size={13} className="text-cyan-400" />
                      <strong>{result.simulation_meta.exposicao_cenario.edificios_expostos}</strong>
                      <span className="text-[10px] text-zinc-500">
                        / {result.simulation_meta.exposicao_cenario.edificios_total} edif.
                      </span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Users size={13} className="text-sky-400" />
                      <strong>
                        {(
                          result.simulation_meta.exposicao_cenario.populacao_edificios_estimada
                          ?? result.simulation_meta.exposicao_cenario.populacao_exposta
                          ?? 0
                        ).toLocaleString('pt-BR')}
                      </strong>
                      <span className="text-[10px] text-zinc-500">hab/edif.</span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <School size={13} className="text-indigo-400" />
                      <strong>{result.simulation_meta.exposicao_cenario.escolas_expostas?.n ?? 0}</strong>
                      <span className="text-[10px] text-zinc-500">escolas</span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Stethoscope size={13} className="text-rose-400" />
                      <strong>{result.simulation_meta.exposicao_cenario.saude_exposta?.n ?? 0}</strong>
                      <span className="text-[10px] text-zinc-500">saúde</span>
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[9px]">
                    <span className="rounded border border-sky-500/30 bg-sky-500/10 px-1.5 py-0.5 text-sky-200">
                      superficial {result.simulation_meta.exposicao_cenario.por_faixa.superficial ?? 0}
                    </span>
                    <span className="rounded border border-blue-500/30 bg-blue-500/10 px-1.5 py-0.5 text-blue-200">
                      moderada {result.simulation_meta.exposicao_cenario.por_faixa.moderada ?? 0}
                    </span>
                    <span className="rounded border border-indigo-500/40 bg-indigo-500/15 px-1.5 py-0.5 text-indigo-100">
                      crítica {result.simulation_meta.exposicao_cenario.por_faixa.critica ?? 0}
                    </span>
                  </div>
                  {(result.simulation_meta.exposicao_cenario.amostra?.length ?? 0) > 0 && (
                    <ul className="mt-2 max-h-24 space-y-0.5 overflow-y-auto text-[9px] text-zinc-400">
                      {result.simulation_meta.exposicao_cenario.amostra!.slice(0, 6).map((b) => (
                        <li key={b.id}>
                          {b.nome || `Edifício #${b.id}`} · {b.depth_band} (~{b.depth_m} m) · {b.altura_m} m
                          {b.populacao_estimada != null && b.populacao_estimada > 0
                            ? ` · ~${b.populacao_estimada.toLocaleString('pt-BR')} hab`
                            : ''}
                        </li>
                      ))}
                    </ul>
                  )}
                  {result.simulation_meta.exposicao_cenario.edificios_total === 0 && (
                    <p className="mt-1.5 text-[9px] text-amber-200/80">
                      Sem footprints carregados — ative a camada Edificações 3D ou sync OSM para contar prédios.
                    </p>
                  )}
                </>
              ) : (
                <p className="mt-1 text-[10px] text-zinc-400">
                  {result.simulation_meta.exposicao_cenario.motivo || 'Exposição por edifício indisponível neste cenário.'}
                </p>
              )}
            </div>
          )}

          {result.scenario_type === 'ExtremeRainfall' && result.simulation_meta?.exposicao_deslizamento && (
            <div className="rounded-lg border border-red-500/25 bg-red-950/15 px-3 py-2.5">
              <p className="text-[9px] font-extrabold uppercase tracking-wider text-red-300">
                Exposição · edifícios × deslizamento
                {result.simulation_meta.exposicao_deslizamento.slope_threshold_deg != null
                  ? ` (≥ ${result.simulation_meta.exposicao_deslizamento.slope_threshold_deg}°)`
                  : ''}
              </p>
              {result.simulation_meta.exposicao_deslizamento.disponivel ? (
                <>
                  <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-zinc-300">
                    <span>
                      <strong>{result.simulation_meta.exposicao_deslizamento.edificios_expostos}</strong>
                      <span className="text-[10px] text-zinc-500">
                        {' '}/ {result.simulation_meta.exposicao_deslizamento.edificios_total} edif.
                      </span>
                    </span>
                    <span>
                      <strong>
                        {(result.simulation_meta.exposicao_deslizamento.populacao_edificios_estimada || 0).toLocaleString('pt-BR')}
                      </strong>
                      <span className="text-[10px] text-zinc-500"> hab/edif.</span>
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[9px]">
                    <span className="rounded border border-orange-500/30 bg-orange-500/10 px-1.5 py-0.5 text-orange-200">
                      moderada {result.simulation_meta.exposicao_deslizamento.por_faixa.moderada ?? 0}
                    </span>
                    <span className="rounded border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 text-red-200">
                      alta {result.simulation_meta.exposicao_deslizamento.por_faixa.alta ?? 0}
                    </span>
                    <span className="rounded border border-rose-500/40 bg-rose-500/15 px-1.5 py-0.5 text-rose-100">
                      crítica {result.simulation_meta.exposicao_deslizamento.por_faixa.critica ?? 0}
                    </span>
                  </div>
                  {(result.simulation_meta.exposicao_deslizamento.amostra?.length ?? 0) > 0 && (
                    <ul className="mt-2 max-h-20 space-y-0.5 overflow-y-auto text-[9px] text-zinc-400">
                      {result.simulation_meta.exposicao_deslizamento.amostra!.slice(0, 5).map((b) => (
                        <li key={b.id}>
                          {b.nome || `Edifício #${b.id}`} · {b.slope_band} (~{b.mean_slope_deg}°)
                          {b.populacao_estimada ? ` · ~${b.populacao_estimada.toLocaleString('pt-BR')} hab` : ''}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <p className="mt-1 text-[10px] text-zinc-400">
                  {result.simulation_meta.exposicao_deslizamento.motivo || 'Sem edifícios em encostas críticas neste cenário.'}
                </p>
              )}
            </div>
          )}

          {result.scenario_type === 'HeatIsland' && result.simulation_meta && (
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Pico previsto</span>
                <span className="text-xs font-bold text-rose-300">
                  {result.simulation_meta.temperatura_pico_c ?? result.input_value}°C
                </span>
              </div>
              <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Temp local máx</span>
                <span className="text-xs font-bold text-rose-300">
                  {result.simulation_meta.temp_pico_local_c ?? '—'}°C
                </span>
              </div>
              <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Ilha de calor máx</span>
                <span className="text-xs font-bold text-rose-300">
                  +{result.simulation_meta.max_delta_t_c ?? result.impact_value}°C
                </span>
              </div>
            </div>
          )}

          {result.scenario_type === 'HeatIsland' && result.simulation_meta?.exposicao_cenario && (
            <div className="rounded-lg border border-orange-500/25 bg-orange-950/15 px-3 py-2.5">
              <p className="text-[9px] font-extrabold uppercase tracking-wider text-orange-300">
                Exposição · edifícios × calor
              </p>
              {result.simulation_meta.exposicao_cenario.disponivel ? (
                <>
                  <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-zinc-300">
                    <span>
                      <strong>{result.simulation_meta.exposicao_cenario.edificios_expostos}</strong>
                      <span className="text-[10px] text-zinc-500">
                        {' '}/ {result.simulation_meta.exposicao_cenario.edificios_total} edif.
                      </span>
                    </span>
                    <span>
                      <strong>
                        {(
                          result.simulation_meta.exposicao_cenario.populacao_edificios_estimada
                          ?? result.simulation_meta.exposicao_cenario.populacao_exposta
                          ?? 0
                        ).toLocaleString('pt-BR')}
                      </strong>
                      <span className="text-[10px] text-zinc-500"> hab/edif.</span>
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[9px]">
                    <span className="rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-amber-200">
                      leve {result.simulation_meta.exposicao_cenario.por_faixa.leve
                        ?? result.simulation_meta.exposicao_cenario.por_faixa.superficial ?? 0}
                    </span>
                    <span className="rounded border border-orange-500/30 bg-orange-500/10 px-1.5 py-0.5 text-orange-200">
                      moderada {result.simulation_meta.exposicao_cenario.por_faixa.moderada ?? 0}
                    </span>
                    <span className="rounded border border-rose-500/40 bg-rose-500/15 px-1.5 py-0.5 text-rose-100">
                      severa {result.simulation_meta.exposicao_cenario.por_faixa.severa
                        ?? result.simulation_meta.exposicao_cenario.por_faixa.critica ?? 0}
                    </span>
                  </div>
                  {(result.simulation_meta.exposicao_cenario.amostra?.length ?? 0) > 0 && (
                    <ul className="mt-2 max-h-20 space-y-0.5 overflow-y-auto text-[9px] text-zinc-400">
                      {result.simulation_meta.exposicao_cenario.amostra!.slice(0, 5).map((b) => (
                        <li key={b.id}>
                          {b.nome || `Edifício #${b.id}`} · {b.heat_band || b.depth_band}
                          {b.delta_t_c != null ? ` (+${b.delta_t_c}°C)` : ''}
                          {b.temp_local_c != null ? ` · ${b.temp_local_c}°C` : ''}
                          {b.populacao_estimada ? ` · ~${b.populacao_estimada.toLocaleString('pt-BR')} hab` : ''}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <p className="mt-1 text-[10px] text-zinc-400">
                  {result.simulation_meta.exposicao_cenario.motivo || 'Exposição térmica por edifício indisponível.'}
                </p>
              )}
            </div>
          )}

          {result.scenario_type === 'HeatIsland'
            && (result.simulation_meta?.ganho_vegetal_pct ?? 0) > 0
            && (result.simulation_meta?.resfriamento_max_c ?? 0) > 0 && (
            <div className="rounded-lg border border-lime-500/30 bg-lime-950/15 p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <Thermometer size={13} className="text-lime-300" />
                <span className="text-[10px] font-extrabold uppercase tracking-wide text-lime-200">
                  Benefício da arborização (+{result.simulation_meta?.ganho_vegetal_pct}% de cobertura)
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded border border-lime-500/20 bg-zinc-950/50 p-2 text-center">
                  <span className="block text-[8px] uppercase text-zinc-500">Resfriamento máx</span>
                  <span className="text-sm font-extrabold text-lime-300">
                    −{result.simulation_meta?.resfriamento_max_c}°C
                  </span>
                </div>
                <div className="rounded border border-lime-500/20 bg-zinc-950/50 p-2 text-center">
                  <span className="block text-[8px] uppercase text-zinc-500">Resfriamento médio</span>
                  <span className="text-sm font-extrabold text-lime-300">
                    −{result.simulation_meta?.resfriamento_medio_c}°C
                  </span>
                </div>
              </div>
              <p className="mt-2 text-[9px] leading-relaxed text-lime-200/70">
                Redução da ilha de calor comparada ao mesmo cenário sem arborização — priorize
                os bairros de maior ΔT e vulnerabilidade (IVC).
              </p>
            </div>
          )}

          {result.simulation_meta?.dem_available && (
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg border border-lime-500/20 bg-lime-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Resolução DEM</span>
                <span className="text-xs font-bold text-lime-300">
                  ~{result.simulation_meta.dem_resolution_m ?? 30} m
                </span>
              </div>
              <div className="rounded-lg border border-lime-500/20 bg-lime-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Isolinhas</span>
                <span className="text-xs font-bold text-lime-300">
                  {result.simulation_meta.contour_interval_m} m
                  {result.simulation_meta.contour_count != null && (
                    <span className="block text-[8px] font-normal text-zinc-500">
                      {result.simulation_meta.contour_count} curvas
                    </span>
                  )}
                </span>
              </div>
              <div className="rounded-lg border border-lime-500/20 bg-lime-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Incerteza vertical</span>
                <span className="text-xs font-bold text-lime-300">
                  ±{result.simulation_meta.vertical_accuracy_m ?? 16} m
                </span>
              </div>
            </div>
          )}

          {result.scenario_type === 'ExtremeRainfall' && result.simulation_meta?.calibration && (
            <div className="rounded-lg border border-violet-500/25 bg-violet-950/15 px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-[9px] font-extrabold uppercase tracking-wider text-violet-300">
                    Calibração local
                  </p>
                  <p className="mt-0.5 text-[10px] text-zinc-400">
                    {result.simulation_meta.calibration.nota
                      || `Fonte ${result.simulation_meta.calibration.source}`}
                    {result.simulation_meta.calibration.hit_rate != null && (
                      <> · hit S2ID {(result.simulation_meta.calibration.hit_rate * 100).toFixed(0)}%</>
                    )}
                  </p>
                  <p className="mt-0.5 font-mono text-[9px] text-zinc-500">
                    rise×{result.simulation_meta.calibration.rise_scale} · runoff×
                    {result.simulation_meta.calibration.runoff_scale} · v
                    {result.simulation_meta.calibration.version}
                  </p>
                </div>
                {codigoIbge && (
                  <button
                    type="button"
                    disabled={calibBusy}
                    onClick={async () => {
                      setCalibBusy(true);
                      setCalibMsg(null);
                      try {
                        const out = await api.recalibrateHydro(codigoIbge, { auto: true });
                        setCalibMsg(out.nota || 'Calibração atualizada. Rode a simulação de novo.');
                      } catch (e) {
                        setCalibMsg(e instanceof Error ? e.message : 'Falha na calibração');
                      } finally {
                        setCalibBusy(false);
                      }
                    }}
                    className="rounded border border-violet-500/40 bg-violet-500/10 px-2 py-1 text-[9px] font-bold text-violet-100 hover:bg-violet-500/20 disabled:opacity-50"
                  >
                    {calibBusy ? 'Calibrando…' : 'Recalibrar S2ID'}
                  </button>
                )}
              </div>
              {calibMsg && <p className="mt-1.5 text-[9px] text-violet-200/90">{calibMsg}</p>}
            </div>
          )}

          {result.simulation_meta?.shade_factor_medio != null && (
            <div className="rounded-lg border border-sky-500/30 bg-sky-950/20 px-3 py-2">
              <p className="text-[9px] font-extrabold uppercase tracking-wider text-sky-200">
                Sombra e vento (17g.1f)
              </p>
              <p className="mt-1 text-[10px] text-zinc-300">
                Fator sombra médio {result.simulation_meta.shade_factor_medio}
                {result.simulation_meta.ventilacao_factor_medio != null
                  ? ` · ventilação ${result.simulation_meta.ventilacao_factor_medio}`
                  : ''}
                {result.simulation_meta.sombreamento_pct
                  ? ` · intervenção sombra ${result.simulation_meta.sombreamento_pct}%`
                  : ''}
                {result.simulation_meta.corredores_vento_pct
                  ? ` · vento ${result.simulation_meta.corredores_vento_pct}%`
                  : ''}
              </p>
            </div>
          )}

          {result.simulation_meta?.modulo && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[9px] font-extrabold uppercase tracking-wider text-amber-200">
                  {result.simulation_meta.modulo === 'seca' ? 'Estresse hídrico' : 'Proxy arbovírus'}
                </p>
                {result.simulation_meta.nivel_label && (
                  <span className="rounded border border-amber-500/40 bg-amber-500/15 px-1.5 py-0.5 text-[8px] font-bold uppercase text-amber-100">
                    {result.simulation_meta.nivel_label}
                  </span>
                )}
              </div>
              <p className="mt-1 text-[10px] text-zinc-300">
                Índice municipal {result.simulation_meta.indice_municipal ?? result.impact_value}
                {result.simulation_meta.temperatura_media_c != null
                  ? ` · ${result.simulation_meta.temperatura_media_c} °C`
                  : ''}
                {result.simulation_meta.precip_72h_mm != null
                  ? ` · precip 72h ${result.simulation_meta.precip_72h_mm} mm`
                  : ''}
              </p>
              {result.simulation_meta.nota && (
                <p className="mt-1 text-[9px] leading-relaxed text-zinc-500">{result.simulation_meta.nota}</p>
              )}
            </div>
          )}

          {result.simulation_meta?.drenagem_urbana?.aplicado && (
            <div
              className={`rounded-lg border px-3 py-2 ${
                result.simulation_meta.drenagem_urbana.saturada
                  ? 'border-amber-500/35 bg-amber-950/25'
                  : 'border-cyan-500/30 bg-cyan-950/20'
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[9px] font-extrabold uppercase tracking-wider text-cyan-200">
                  Rede de drenagem (proxy)
                </p>
                {result.simulation_meta.drenagem_urbana.saturada && (
                  <span className="rounded border border-amber-500/40 bg-amber-500/15 px-1.5 py-0.5 text-[8px] font-bold uppercase text-amber-100">
                    saturada
                  </span>
                )}
              </div>
              <p className="mt-1 text-[10px] text-zinc-300">
                Capacidade {result.simulation_meta.drenagem_urbana.capacidade_mm_h} mm/h · removidos{' '}
                {result.simulation_meta.drenagem_urbana.removido_mm} mm
                {result.simulation_meta.drenagem_urbana.fonte
                  ? ` · ${result.simulation_meta.drenagem_urbana.fonte}`
                  : ''}
              </p>
              {result.simulation_meta.drenagem_urbana.nota && (
                <p className="mt-1 text-[9px] leading-relaxed text-zinc-500">
                  {result.simulation_meta.drenagem_urbana.nota}
                </p>
              )}
            </div>
          )}

          {result.simulation_meta?.selo_confianca && (
            <div className="rounded-lg border border-sky-500/25 bg-sky-950/20 px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[9px] font-extrabold uppercase tracking-wider text-sky-300">
                  Selo de confiança
                </p>
                <div className="flex gap-1">
                  <span className="rounded border border-sky-500/40 bg-sky-500/10 px-1.5 py-0.5 text-[8px] font-bold uppercase text-sky-100">
                    <TermTooltip term={result.simulation_meta.selo_confianca.selo_qualidade} />
                  </span>
                  <span className="rounded border border-zinc-600 px-1.5 py-0.5 text-[8px] font-bold uppercase text-zinc-300">
                    {result.simulation_meta.selo_confianca.nivel_confianca}
                  </span>
                </div>
              </div>
              <p className="mt-1 text-[9px] leading-relaxed text-zinc-400">
                {result.simulation_meta.selo_confianca.interpretacao}
              </p>
              <button
                type="button"
                onClick={async () => {
                  try {
                    const md = await api.buildMethodNote({
                      tipo: simulationTipo(),
                      codigo_ibge: codigoIbge || undefined,
                      simulation_meta: result.simulation_meta as Record<string, unknown>,
                      format: 'markdown',
                    });
                    const blob = new Blob([typeof md === 'string' ? md : JSON.stringify(md, null, 2)], {
                      type: 'text/markdown;charset=utf-8',
                    });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `nota-metodologica-${codigoIbge || 'sim'}.md`;
                    a.click();
                    URL.revokeObjectURL(url);
                  } catch {
                    /* ignore */
                  }
                }}
                className="mt-2 inline-flex items-center gap-1 rounded border border-sky-500/30 px-2 py-1 text-[9px] font-bold text-sky-200 hover:bg-sky-500/10"
              >
                <FileText size={11} /> Baixar nota metodológica
              </button>
            </div>
          )}

          {result.simulation_meta?.validacao_s2id?.disponivel && (
            <div className="rounded-lg border border-amber-500/25 bg-amber-950/15 px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[9px] font-extrabold uppercase tracking-wider text-amber-300">
                  Validação S2ID
                </p>
                <span className="rounded border border-amber-500/40 px-1.5 py-0.5 text-[8px] font-bold uppercase text-amber-100">
                  acordo {result.simulation_meta.validacao_s2id.acordo}
                </span>
              </div>
              <p className="mt-1 text-[9px] leading-relaxed text-zinc-400">
                {result.simulation_meta.validacao_s2id.narrativa}
              </p>
              {result.simulation_meta.validacao_s2id.hit_rate != null && (
                <p className="mt-0.5 text-[8px] font-mono text-zinc-500">
                  hit rate {(result.simulation_meta.validacao_s2id.hit_rate * 100).toFixed(0)}% ·{' '}
                  {result.simulation_meta.validacao_s2id.eventos_na_mancha}/
                  {result.simulation_meta.validacao_s2id.eventos_com_geometria} eventos na mancha
                </p>
              )}
            </div>
          )}

          {result.simulation_meta?.precision_note && (
            <p className="text-[9px] leading-relaxed text-zinc-500 italic">
              {result.simulation_meta.precision_note}
            </p>
          )}

          {result.simulation_meta?.dem_available && (
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Cota mín.</span>
                <span className="text-xs font-bold text-zinc-300">{result.simulation_meta.altitude_min_m} m</span>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Cota média</span>
                <span className="text-xs font-bold text-zinc-300">{result.simulation_meta.altitude_media_m} m</span>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Cota máx.</span>
                <span className="text-xs font-bold text-zinc-300">{result.simulation_meta.altitude_max_m} m</span>
              </div>
            </div>
          )}

          {result.scenario_type === 'ExtremeRainfall' && result.simulation_meta?.flow_accumulation_applied && (
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg border border-sky-500/20 bg-sky-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Acúmulo D8</span>
                <span className="text-xs font-bold text-sky-300">{result.simulation_meta.max_flow_accumulation ?? '—'}</span>
              </div>
              <div className="rounded-lg border border-sky-500/20 bg-sky-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Impermeab.</span>
                <span className="text-xs font-bold text-sky-300">
                  {result.simulation_meta.mean_impermeability != null
                    ? `${Math.round(result.simulation_meta.mean_impermeability * 100)}%`
                    : '—'}
                </span>
              </div>
              <div className="rounded-lg border border-sky-500/20 bg-sky-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Bairros</span>
                <span className="text-xs font-bold text-sky-300">
                  {result.simulation_meta.bairros_atingidos_count ?? result.affected_bairros.length}
                </span>
              </div>
            </div>
          )}

          {(result.contours?.features?.length > 0
            || result.flow_paths?.features?.length > 0
            || (result.vias_intransitaveis?.features?.length ?? 0) > 0
            || (result.ativos_criticos_atingidos?.features?.length ?? 0) > 0) && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2.5">
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-1.5">Visibilidade no mapa</span>
              <div className="flex flex-wrap gap-2 mb-2">
                {(
                  [
                    { key: 'showFlood' as const, label: 'Manchas de alagamento', activeClass: 'border-sky-500/40 bg-sky-500/15 text-sky-200' },
                    { key: 'showContours' as const, label: 'Curvas de nível', activeClass: 'border-lime-500/40 bg-lime-500/15 text-lime-200' },
                    { key: 'showFlow' as const, label: 'Escoamento D8', activeClass: 'border-cyan-500/40 bg-cyan-500/15 text-cyan-200' },
                    { key: 'showImpassableRoads' as const, label: 'Vias intransitáveis', activeClass: 'border-red-500/40 bg-red-500/15 text-red-200' },
                    { key: 'showCriticalAssets' as const, label: 'Ativos críticos', activeClass: 'border-amber-500/40 bg-amber-500/15 text-amber-200' },
                  ] as const
                ).map(({ key, label, activeClass }) => {
                  const active = overlayOptions[key];
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => onOverlayChange({ ...overlayOptions, [key]: !active })}
                      className={`rounded-full border px-2 py-0.5 text-[9px] transition ${
                        active ? activeClass : 'border-zinc-700 bg-zinc-900 text-zinc-500 line-through'
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-1.5">Camadas geradas</span>
              <div className="flex flex-wrap gap-2">
                {result.geometry?.features?.length > 0 && (
                  <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[9px] text-sky-200">
                    {result.geometry.features.length} mancha(s)
                  </span>
                )}
                {result.contours?.features?.length > 0 && (
                  <span className="rounded-full border border-lime-500/30 bg-lime-500/10 px-2 py-0.5 text-[9px] text-lime-200">
                    {result.contours.features.length} curvas de nível
                  </span>
                )}
                {result.flow_paths?.features?.length > 0 && (
                  <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[9px] text-cyan-200">
                    {result.flow_paths.features.length} vetores escoamento
                  </span>
                )}
                {(result.vias_intransitaveis?.features?.length ?? 0) > 0 && (
                  <span className="rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[9px] text-red-200">
                    {result.vias_intransitaveis!.features!.length} trecho(s) intransitável(is)
                    {result.simulation_meta?.impacto_operacional?.mobilidade?.vias_comprometidas_km != null
                      ? ` · ${result.simulation_meta.impacto_operacional.mobilidade.vias_comprometidas_km} km`
                      : ''}
                  </span>
                )}
                {(result.ativos_criticos_atingidos?.features?.length ?? 0) > 0 && (
                  <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[9px] text-amber-200">
                    {result.ativos_criticos_atingidos!.features!.length} ativo(s) crítico(s)
                    {result.simulation_meta?.ativos_criticos?.escolas
                      ? ` · ${result.simulation_meta.ativos_criticos.escolas} escola(s)`
                      : ''}
                    {result.simulation_meta?.ativos_criticos?.saude
                      ? ` · ${result.simulation_meta.ativos_criticos.saude} saúde`
                      : ''}
                  </span>
                )}
              </div>
            </div>
          )}

          <div>
            <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-1">Métricas de Consequência</span>
            <p className="text-xs text-zinc-300 bg-zinc-950/40 p-2 border border-zinc-800/80 rounded italic">
              {result.metric_impact}: {result.scenario_type === 'VegetationLoss' || result.scenario_type === 'HeatIsland'
                ? `Elevação térmica projetada em até +${result.impact_value}°C nos bairros mais expostos.`
                : `Aproximadamente ${result.affected_population.toLocaleString()} cidadãos residem nos setores inundáveis afetados.`}
            </p>
          </div>

          {result.affected_bairros.length > 0 && (
            <div>
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-1">Bairros Atingidos</span>
              <div className="flex flex-wrap gap-1">
                {(result.simulation_meta?.bairros_exposicao?.length
                  ? result.simulation_meta.bairros_exposicao.map((row) => (
                      <span
                        key={row.bairro}
                        className="text-[9px] bg-zinc-950 border border-zinc-800 text-zinc-300 py-0.5 px-2 rounded-full font-medium"
                        title={`${row.populacao_exposta.toLocaleString()} hab expostos`}
                      >
                        {row.bairro} · {row.exposicao_pct}%
                      </span>
                    ))
                  : result.affected_bairros.map((b) => (
                      <span key={b} className="text-[9px] bg-zinc-950 border border-zinc-800 text-zinc-300 py-0.5 px-2 rounded-full font-medium">
                        {b}
                      </span>
                    )))}
              </div>
            </div>
          )}

          {result.risk_context && result.risk_context.length > 0 && (
            <div>
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-1.5">
                Contexto IVC × IRI (top 5)
              </span>
              <div className="flex flex-col gap-1">
                {result.risk_context.slice(0, 5).map((row) => (
                  <div key={row.bairro} className="flex items-center justify-between rounded border border-zinc-800 bg-zinc-950/50 px-2 py-1">
                    <span className="text-[10px] text-zinc-300 font-medium">{row.bairro}</span>
                    <span className="text-[9px] font-mono text-indigo-300">
                      IVC {row.ivc.toFixed(2)} · IRI {row.iri.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {mitigationPlan && (
        <div className="bg-card/40 border border-emerald-500/25 p-4 rounded-xl flex flex-col gap-4 animate-fadeIn">
          <div>
            <h4 className="font-extrabold text-zinc-200 text-xs uppercase tracking-wide">Plano de Ação Sugerido</h4>
            <p className="mt-1 text-[10px] text-zinc-400">
              Severidade <strong className="text-emerald-300">{mitigationPlan.severidade}</strong> para {mitigationPlan.evento.tipo}
              {` (${mitigationPlan.evento.valor_entrada ?? mitigationPlan.evento.precipitacao_mm} ${mitigationPlan.evento.unidade || 'mm'})`},
              {` ${mitigationPlan.evento.area_afetada_km2} km²`} e {mitigationPlan.evento.populacao_afetada.toLocaleString('pt-BR')} pessoa(s) exposta(s).
            </p>
            <p className="mt-2 rounded-lg border border-teal-500/25 bg-teal-950/20 px-2.5 py-1.5 text-[10px] leading-snug text-teal-100/90">
              Ações filtradas pelo <strong className="text-teal-200">Plano Diretor</strong> do município
              {mitigationPlan.municipio?.nome ? ` (${mitigationPlan.municipio.nome})` : ''}
              — o que pode / não pode priorizar está abaixo, com base na legislação urbanística oficial.
            </p>
          </div>

          <div>
            <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-2">Ações proporcionais ao evento</span>
            <div className="flex flex-col gap-2">
              {mitigationPlan.acoes_tecnicas_padrao.map((item, idx) => (
                <div key={`${item.horizonte}-${idx}`} className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-2.5">
                  <div className="text-[10px] font-extrabold text-emerald-300">{item.horizonte}</div>
                  <p className="mt-1 text-[11px] leading-relaxed text-zinc-200">{item.acao}</p>
                  <p className="mt-1 text-[9px] leading-relaxed text-zinc-500">{item.justificativa} {item.proporcionalidade}</p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-2">Experiências do município</span>
            {mitigationPlan.experiencias_municipais.length > 0 ? (
              <div className="flex flex-col gap-2">
                {mitigationPlan.experiencias_municipais.map((item) => (
                  <div key={item.titulo} className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2">
                    <strong className="text-[10px] text-zinc-200">{item.titulo}</strong>
                    <p className="mt-1 text-[10px] leading-relaxed text-zinc-400">{item.descricao}</p>
                    <p className="mt-1 text-[9px] text-zinc-600">Fonte: {item.fonte}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2 text-[10px] text-zinc-500">
                Sem experiências municipais verificáveis para este tipo de evento.
              </p>
            )}
          </div>

          <div>
            <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-2">Municípios e casos análogos</span>
            {mitigationPlan.municipios_analogos.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {mitigationPlan.municipios_analogos.map((item) => (
                  <span key={item.codigo_ibge} className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-1 text-[9px] font-bold text-indigo-200">
                    {item.nome}-{item.uf}: {(item.coeficiente_similaridade * 100).toFixed(0)}%
                  </span>
                ))}
              </div>
            ) : (
              <p className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2 text-[10px] text-zinc-500">
                Não foram encontrados municípios análogos suficientes com os dados disponíveis.
              </p>
            )}
            {mitigationPlan.casos_analogos.length === 0 && (
              <p className="mt-2 rounded-lg border border-amber-500/20 bg-amber-950/10 p-2 text-[10px] text-amber-200/80">
                Campo de casos análogos vazio: não há solução e resultado verificáveis por fonte oficial nesta versão do banco.
              </p>
            )}
          </div>

          <div>
            <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-2">
              Plano Diretor municipal — pode fazer / não pode fazer
            </span>
            {(() => {
              const pdFontes = mitigationPlan.fontes_consultadas.filter((f) =>
                (f.tipo || '').toLowerCase().includes('plano diretor'),
              );
              if (pdFontes.length === 0) return null;
              return (
                <div className="mb-2 flex flex-col gap-1">
                  {pdFontes.map((f) => (
                    <p key={f.titulo} className="text-[10px] text-zinc-300">
                      Fonte:{' '}
                      {f.url ? (
                        <a
                          href={f.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-semibold text-teal-300 underline decoration-teal-500/40 underline-offset-2 hover:text-teal-200"
                        >
                          {f.titulo}
                        </a>
                      ) : (
                        <strong className="text-teal-200">{f.titulo}</strong>
                      )}
                      <span className="text-zinc-500"> · {f.status}</span>
                    </p>
                  ))}
                </div>
              );
            })()}
            <div className="grid grid-cols-1 gap-2">
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/10 p-2">
                <strong className="text-[10px] text-emerald-200">Pode priorizar, se compatível com o PD</strong>
                {mitigationPlan.diretrizes_plano_diretor.length > 0 ? (
                  mitigationPlan.diretrizes_plano_diretor.map((item, idx) => (
                    <p key={`${item.descricao}-${idx}`} className="mt-1 text-[10px] leading-relaxed text-zinc-400">{item.descricao} <span className="text-zinc-600">({item.fonte})</span></p>
                  ))
                ) : (
                  <p className="mt-1 text-[10px] text-zinc-500">Sem diretriz específica extraída de fonte oficial legível.</p>
                )}
              </div>
              <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-2">
                <strong className="text-[10px] text-rose-200">Não deve / depende de validação legal (PD)</strong>
                {mitigationPlan.restricoes_plano_diretor.length > 0 ? (
                  mitigationPlan.restricoes_plano_diretor.map((item, idx) => (
                    <p key={`${item.descricao}-${idx}`} className="mt-1 text-[10px] leading-relaxed text-zinc-400">{item.descricao} <span className="text-zinc-600">({item.fonte})</span></p>
                  ))
                ) : (
                  <p className="mt-1 text-[10px] text-zinc-500">Sem restrição específica extraída de fonte oficial legível.</p>
                )}
              </div>
            </div>
          </div>

          {mitigationPlan.capacidade_investimento && (
            <div>
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-2">Capacidade de Investimento</span>
              <div className="rounded-lg border border-indigo-500/20 bg-indigo-950/10 p-3 flex flex-col gap-2">
                <p className="text-[10px] text-zinc-300">
                  CAPAG: <strong>{mitigationPlan.capacidade_investimento.nota_capag || 'não informada'}</strong>
                  {' · '}IVC médio: <strong>{mitigationPlan.capacidade_investimento.media_ivc?.toFixed(2) ?? '—'}</strong>
                </p>
                {mitigationPlan.capacidade_investimento.alertas.map((item, idx) => (
                  <p key={`${item}-${idx}`} className="text-[10px] font-semibold text-amber-300">{item}</p>
                ))}
                <div>
                  <strong className="text-[10px] text-indigo-200">Fontes de financiamento compatíveis</strong>
                  <ul className="mt-1 list-disc pl-4 text-[10px] text-zinc-400">
                    {mitigationPlan.capacidade_investimento.fontes_financiamento_sugeridas.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                {mitigationPlan.capacidade_investimento.observacao && (
                  <p className="text-[9px] italic text-zinc-500">{mitigationPlan.capacidade_investimento.observacao}</p>
                )}
              </div>
            </div>
          )}

          <div>
            <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-2">Fontes e lacunas</span>
            <div className="flex flex-col gap-1">
              {mitigationPlan.fontes_consultadas.map((item) => (
                <p key={item.titulo} className="text-[9px] text-zinc-500">
                  {item.titulo}: <span className="text-zinc-400">{item.status}</span>
                </p>
              ))}
              {mitigationPlan.lacunas.map((item, idx) => (
                <p key={`${item}-${idx}`} className="text-[9px] text-amber-300/80">Lacuna: {item}</p>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
