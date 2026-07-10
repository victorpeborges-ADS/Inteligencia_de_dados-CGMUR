'use client';

import { useState, useEffect } from 'react';
import { api, HeatLstComparison, MitigationPlan, RainfallComparison, SimulationInterpret, SimulationOutput, SlopeInterpretation } from '@/utils/api';
import { Play, RotateCcw, AlertTriangle, HelpCircle, Thermometer, Droplet, FileText, Waves, Layers, Mountain, Activity, Sparkles, Copy, ClipboardCheck, Droplets, ExternalLink } from 'lucide-react';
import { georedusMunicipioUrl } from '@/config/georedus';
import PredictiveAnalysis from './PredictiveAnalysis';
import RotatingLoader, { INTERPRETATION_MESSAGES, SIMULATION_MESSAGES } from '@/components/UI/RotatingLoader';
import TermTooltip from '@/components/UI/TermTooltip';
import SimulationNextSteps from './SimulationNextSteps';
import { EmptyState } from '@/design-system';

export type SimOverlayOptions = {
  showFlood: boolean;
  showContours: boolean;
  showFlow: boolean;
};

export const DEFAULT_SIM_OVERLAYS: SimOverlayOptions = {
  showFlood: true,
  showContours: true,
  showFlow: true,
};

function isVolumeSimulation(geojson: unknown): boolean {
  const features = (geojson as { features?: Array<{ properties?: Record<string, unknown> }> })?.features;
  if (!features?.length) return false;
  return features.some(
    (f) =>
      f.properties?.layer_type === 'flood_band'
      || f.properties?.depth_band
      || f.properties?.temp_increase_celsius != null,
  );
}

interface SimulationProps {
  onSimulate: (payload: SimulationOutput | any) => void;
  onClear: () => void;
  onSimulatingChange?: (simulating: boolean) => void;
  codigoIbge?: string;
  municipioNome?: string;
  municipioLoaded?: boolean;
  overlayOptions: SimOverlayOptions;
  onOverlayChange: (options: SimOverlayOptions) => void;
  onView3D?: () => void;
  onFocusWorkshop?: () => void;
  onCrossRiskLayers?: () => void;
  mapMode3dActive?: boolean;
}

export default function SimulationPanel({
  onSimulate,
  onClear,
  onSimulatingChange,
  codigoIbge,
  municipioNome,
  municipioLoaded,
  overlayOptions,
  onOverlayChange,
  onView3D,
  onFocusWorkshop,
  onCrossRiskLayers,
  mapMode3dActive = false,
}: SimulationProps) {
  const [activeTab, setActiveTab] = useState<'waterproofing' | 'heat_island' | 'rainfall' | 'drainage' | 'predictive'>('rainfall');
  const [waterproofingPct, setWaterproofingPct] = useState(25);
  const [heatPeakTempC, setHeatPeakTempC] = useState(36);
  // Mudança líquida de cobertura vegetal: negativo = desmatamento, positivo = arborização
  const [heatVegChangePct, setHeatVegChangePct] = useState(20);
  const [heatImpermExtraPct, setHeatImpermExtraPct] = useState(15);
  const [rainfallMm, setRainfallMm] = useState(120);
  const [compareRainfall, setCompareRainfall] = useState(true);
  const [baselineRainfallMm, setBaselineRainfallMm] = useState(80);
  const [rainfallComparison, setRainfallComparison] = useState<RainfallComparison | null>(null);
  const [heatLstComparison, setHeatLstComparison] = useState<HeatLstComparison | null>(null);
  const [lstCompareLoading, setLstCompareLoading] = useState(false);
  const [drainageDeficitPct, setDrainageDeficitPct] = useState(45);
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulationOutput | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [contingencyLoading, setContingencyLoading] = useState(false);
  const [mitigationPlan, setMitigationPlan] = useState<MitigationPlan | null>(null);
  const [exportLoading, setExportLoading] = useState<'geojson' | 'pdf' | null>(null);
  const [simInterpret, setSimInterpret] = useState<SimulationInterpret | null>(null);
  const [slopeInterpret, setSlopeInterpret] = useState<SlopeInterpretation | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [interpretError, setInterpretError] = useState<string | null>(null);
  const [copyOk, setCopyOk] = useState(false);
  const [lidarUploading, setLidarUploading] = useState(false);
  const [lidarMessage, setLidarMessage] = useState<string | null>(null);
  const [simError, setSimError] = useState<string | null>(null);
  const [simProgress, setSimProgress] = useState<{ progress: number; stage_label?: string } | null>(null);
  const [demStatus, setDemStatus] = useState<'idle' | 'warming' | 'ready' | 'error'>('idle');

  useEffect(() => {
    if (!codigoIbge) {
      setDemStatus('idle');
      return;
    }
    let cancelled = false;
    setDemStatus('warming');
    api.getTerrainConfig(codigoIbge)
      .then(() => {
        if (!cancelled) setDemStatus('ready');
      })
      .catch(() =>
        api.processTerrainDem(codigoIbge)
          .then(() => {
            if (!cancelled) setDemStatus('ready');
          })
          .catch(() => {
            if (!cancelled) setDemStatus('error');
          }),
      );
    return () => {
      cancelled = true;
    };
  }, [codigoIbge]);

  useEffect(() => {
    if (analysisLoading) {
      document.getElementById('interpretacao-ia')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [analysisLoading]);

  const HYDRO_MODEL_VERSION = process.env.NEXT_PUBLIC_HYDRO_MODEL_VERSION ?? '2.3';
  const displayedModelVersion = result?.simulation_meta?.model_version ?? HYDRO_MODEL_VERSION;

  const PILOT_IBGE = '2611606';
  const isPilot = codigoIbge?.replace(/\D/g, '').padStart(7, '0').slice(-7) === PILOT_IBGE;

  const handleLidarUpload = async (file: File) => {
    if (!codigoIbge) return;
    setLidarUploading(true);
    setLidarMessage(null);
    try {
      const result = await api.importLocalDem(codigoIbge, file, true);
      const cfg = result.config as { dem_source?: string; dem_resolution_m?: number } | undefined;
      setLidarMessage(
        `DEM importado: ${cfg?.dem_source ?? 'LiDAR local'}${cfg?.dem_resolution_m != null ? ` (${cfg.dem_resolution_m} m)` : ''}`,
      );
    } catch (e) {
      setLidarMessage(e instanceof Error ? e.message : 'Falha no upload LiDAR');
    } finally {
      setLidarUploading(false);
    }
  };

  const simulationTipo = (): 'chuva' | 'asfalto' | 'vegetacao' | 'drenagem' | 'calor' => {
    if (activeTab === 'waterproofing') return 'asfalto';
    if (activeTab === 'heat_island') return 'calor';
    if (activeTab === 'drainage') return 'drenagem';
    return 'chuva';
  };

  const interpretForPdf = (interpret: SimulationInterpret): SimulationInterpret => ({
    ...interpret,
    findings: interpret.findings?.length
      ? interpret.findings
      : [
          interpret.resumo_executivo,
          ...interpret.areas_criticas,
          ...interpret.equipamentos_em_risco,
          interpret.comparacao_historica,
          ...interpret.recomendacoes_imediatas,
        ].filter(Boolean) as string[],
  });

  const runInterpret = async (
    data: SimulationOutput,
    comparison: RainfallComparison | null,
    lstComparison: HeatLstComparison | null = null,
  ) => {
    if (!codigoIbge) return;
    setAnalysisLoading(true);
    setSimInterpret(null);
    setSlopeInterpret(null);
    setInterpretError(null);
    try {
      const interpret = await api.interpretSimulation({
        municipio_codigo: codigoIbge,
        tipo_simulacao: simulationTipo(),
        parametro_atual: data.input_value,
        parametro_referencia: baselineRainfallMm,
        resultado_simulacao: data,
        resultado_referencia: comparison?.baseline,
        comparacao_delta: comparison?.delta,
        lst_comparison: lstComparison ?? undefined,
      });
      setSimInterpret(interpret);
      const meta = data.simulation_meta;
      if (meta?.landslide_zones && Number(meta.landslide_zones) > 0) {
        api.getSlopeInterpretation(codigoIbge, data.input_value).then(setSlopeInterpret).catch(() => null);
      }
    } catch (err) {
      console.error('Interpretation failed:', err);
      setInterpretError(err instanceof Error ? err.message : 'Falha ao gerar interpretação.');
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleSimulate = async () => {
    setLoading(true);
    onSimulatingChange?.(true);
    setSimError(null);
    setSimProgress(null);
    setMitigationPlan(null);
    setSimInterpret(null);
    setSlopeInterpret(null);
    setInterpretError(null);
    setRainfallComparison(null);
    setHeatLstComparison(null);
    try {
      let data: SimulationOutput;
      let comparison: RainfallComparison | null = null;
      let lstComparison: HeatLstComparison | null = null;
      const onJobProgress = (p: { progress: number; stage_label?: string }) => {
        setSimProgress({ progress: p.progress, stage_label: p.stage_label });
      };

      if (activeTab === 'waterproofing') {
        data = await api.simulateWaterproofing(waterproofingPct, codigoIbge);
      } else if (activeTab === 'heat_island') {
        data = await api.simulateHeatIsland({
          temperaturaPicoC: heatPeakTempC,
          perdaVegetalPct: heatVegChangePct < 0 ? -heatVegChangePct : 0,
          ganhoVegetalPct: heatVegChangePct > 0 ? heatVegChangePct : 0,
          impermeabilizacaoExtraPct: heatImpermExtraPct,
          codigoIbge,
        });
        setLstCompareLoading(true);
        try {
          lstComparison = await api.compareHeatLst(data, codigoIbge);
          setHeatLstComparison(lstComparison);
        } catch (lstErr) {
          console.error('LST comparison failed:', lstErr);
          setHeatLstComparison(null);
        } finally {
          setLstCompareLoading(false);
        }
      } else if (activeTab === 'drainage') {
        data = await api.simulateDrainageDeficit(drainageDeficitPct, codigoIbge);
      } else if (compareRainfall) {
        comparison = await api.compareRainfallScenariosAsync(
          rainfallMm,
          baselineRainfallMm,
          codigoIbge,
          onJobProgress,
        );
        setRainfallComparison(comparison);
        data = comparison.scenario;
      } else {
        data = await api.simulateExtremeRainfallAsync(rainfallMm, codigoIbge, onJobProgress);
      }
      setResult(data);
      onSimulate(data);
      void runInterpret(
        data,
        compareRainfall && activeTab === 'rainfall' ? comparison : null,
        activeTab === 'heat_island' ? lstComparison : null,
      );
    } catch (err) {
      console.error('Error running simulation:', err);
      setSimError(err instanceof Error ? err.message : 'Falha na simulação pluvial.');
    } finally {
      setLoading(false);
      setSimProgress(null);
      onSimulatingChange?.(false);
    }
  };

  const handleExportGeojson = async () => {
    if (!result) return;
    setExportLoading('geojson');
    try {
      const meta = await api.exportSimulationGeojson(
        result,
        codigoIbge,
        rainfallComparison?.delta,
      );
      await api.downloadReport(meta.download_url, meta.nome_arquivo);
    } catch (err) {
      console.error('Export GeoJSON failed:', err);
    } finally {
      setExportLoading(null);
    }
  };

  const handleExportPdf = async () => {
    if (!result) return;
    setExportLoading('pdf');
    try {
      const meta = await api.exportSimulationPdf(result, codigoIbge, {
        comparisonDelta: rainfallComparison?.delta,
        analysis: simInterpret ? interpretForPdf(simInterpret) : undefined,
      });
      await api.downloadReport(meta.download_url, meta.nome_arquivo);
    } catch (err) {
      console.error('Export PDF failed:', err);
    } finally {
      setExportLoading(null);
    }
  };

  const handleReset = () => {
    setResult(null);
    setMitigationPlan(null);
    setSimInterpret(null);
    setSlopeInterpret(null);
    setInterpretError(null);
    setRainfallComparison(null);
    setHeatLstComparison(null);
    onClear();
  };

  const handleCopyInterpret = async () => {
    if (!simInterpret) return;
    const text = [
      simInterpret.resumo_executivo,
      '',
      'ÁREAS CRÍTICAS:',
      ...simInterpret.areas_criticas.map((a) => `• ${a}`),
      '',
      'EQUIPAMENTOS EM RISCO:',
      ...simInterpret.equipamentos_em_risco.map((e) => `• ${e}`),
      '',
      `HISTÓRICO: ${simInterpret.comparacao_historica}`,
      simInterpret.interpretacao_diferencial ? `\nCOMPARAÇÃO: ${simInterpret.interpretacao_diferencial}` : '',
      '',
      'RECOMENDAÇÕES:',
      ...simInterpret.recomendacoes_imediatas.map((r) => `→ ${r}`),
      '',
      simInterpret.disclaimer,
    ].join('\n');
    await navigator.clipboard.writeText(text);
    setCopyOk(true);
    setTimeout(() => setCopyOk(false), 2000);
  };

  const handleIncludeInReport = () => {
    if (!simInterpret || !codigoIbge) return;
    sessionStorage.setItem(
      `sinidu_sim_interpret_${codigoIbge}`,
      JSON.stringify({ ...simInterpret, saved_at: new Date().toISOString() }),
    );
    void handleExportPdf();
  };

  const handleGenerateMitigationPlan = async () => {
    if (!result) return;
    setPlanLoading(true);
    try {
      const plan = await api.generateMitigationPlan(result.scenario_type, result.input_value, codigoIbge);
      setMitigationPlan(plan);
    } catch (err) {
      console.error('Error generating mitigation plan:', err);
    } finally {
      setPlanLoading(false);
    }
  };

  const handleGenerateContingency = async () => {
    if (!result?.geometry || !codigoIbge) return;
    setContingencyLoading(true);
    try {
      const cenario =
        activeTab === 'drainage' || activeTab === 'rainfall' ? 'INUNDACAO' : activeTab === 'heat_island' ? 'CALOR' : 'MULTIPLO';
      await api.generateContingencyFromSimulation({
        codigo_ibge: codigoIbge,
        cenario_tipo: cenario,
        risk_geojson: result.geometry,
        buffer_m: 500,
        simulacao_ref: { scenario: result.scenario_type, input: result.input_value },
      });
      alert('Plano de contingência gerado como rascunho. Abra a aba Contingência para editar.');
    } catch (err) {
      console.error('Error generating contingency plan:', err);
    } finally {
      setContingencyLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 p-1">
      {codigoIbge && (
        <div className="rounded-lg border border-sky-800/50 bg-sky-950/30 px-3 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-xs font-semibold text-sky-200">
                DEM / LiDAR{municipioNome ? ` — ${municipioNome}` : ''}
              </p>
              <p className="text-[10px] text-zinc-500">
                GeoTIFF (.tif) para curvas de nível e simulação em alta resolução
                {!isPilot && ' · piloto refinado: Recife (2611606)'}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {demStatus === 'ready' && (
                <span className="rounded-full border border-lime-500/40 bg-lime-950/40 px-2 py-0.5 text-[9px] font-bold uppercase text-lime-200">
                  DEM aquecido
                </span>
              )}
              {demStatus === 'warming' && (
                <span className="rounded-full border border-sky-500/30 bg-sky-950/40 px-2 py-0.5 text-[9px] font-bold uppercase text-sky-200 animate-pulse">
                  Preparando DEM…
                </span>
              )}
              <label
              className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-sky-700 bg-sky-900/40 px-3 py-1.5 text-xs font-medium text-sky-100 hover:bg-sky-800/50 ${lidarUploading ? 'opacity-50' : ''}`}
            >
              <Mountain className="h-3.5 w-3.5" />
              {lidarUploading ? 'Enviando…' : 'Importar LiDAR'}
              <input
                type="file"
                accept=".tif,.tiff,.geotiff"
                className="hidden"
                disabled={lidarUploading}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleLidarUpload(file);
                  e.target.value = '';
                }}
              />
            </label>
            </div>
          </div>
          {lidarMessage && <p className="mt-2 text-[10px] text-sky-100">{lidarMessage}</p>}
        </div>
      )}
      {/* Simulation Selector tabs */}
      <div className="grid grid-cols-5 gap-1 bg-zinc-950 p-1 rounded-lg border border-border">
        {(['rainfall', 'predictive', 'waterproofing', 'heat_island', 'drainage'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setResult(null); setMitigationPlan(null); setSimInterpret(null); setInterpretError(null); if (tab !== 'predictive') onClear(); }}
            className={`py-1.5 px-1 rounded text-[9px] font-bold uppercase tracking-wider transition-all ${
              activeTab === tab 
                ? 'bg-card text-indigo-400 border border-zinc-800' 
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {tab === 'rainfall' ? 'Chuva' : tab === 'predictive' ? 'Preditiva' : tab === 'waterproofing' ? 'Asfalto' : tab === 'heat_island' ? 'Calor' : 'Drenagem'}
          </button>
        ))}
      </div>

      {/* Simulator Forms */}
      <div className="bg-card/40 backdrop-blur-md border border-border p-4 rounded-xl">
        {activeTab === 'predictive' && (
          <PredictiveAnalysis
            codigoIbge={codigoIbge}
            municipioNome={municipioNome}
            municipioLoaded={municipioLoaded}
            onPredict={onSimulate}
            onClear={onClear}
          />
        )}

        {activeTab === 'rainfall' && (
          <div className="flex flex-col gap-4">
            <div className="rounded-lg border border-sky-500/25 bg-gradient-to-br from-sky-950/40 to-zinc-950/60 p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h4 className="font-extrabold text-sm text-zinc-100 flex items-center gap-1.5">
                    <Droplet size={16} className="text-accent-sky" /> Modelo Pluvial Territorial
                  </h4>
                  <p className="text-[10px] text-sky-200/70 mt-1 uppercase tracking-wider font-bold">
                    <TermTooltip term="SRTM" label="DEM SRTM" /> · Curvas de nível · Manchas por profundidade
                  </p>
                </div>
                <span className="shrink-0 rounded-md border border-sky-500/30 bg-sky-500/10 px-2 py-1 text-[9px] font-bold text-sky-200">
                  v{displayedModelVersion}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-2 text-center">
                <span className="block text-[8px] font-bold uppercase tracking-wider text-zinc-500">Precipitação</span>
                <span className="text-lg font-extrabold text-sky-300">{rainfallMm}</span>
                <span className="text-[9px] text-zinc-500"> mm</span>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-2 text-center">
                <span className="block text-[8px] font-bold uppercase tracking-wider text-zinc-500">Resolução</span>
                <span className="text-lg font-extrabold text-lime-300">30</span>
                <span className="text-[9px] text-zinc-500"> m</span>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-2 text-center">
                <span className="block text-[8px] font-bold uppercase tracking-wider text-zinc-500">Faixas</span>
                <span className="text-lg font-extrabold text-indigo-300">3</span>
                <span className="text-[9px] text-zinc-500"> prof.</span>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs text-zinc-300">
                <span className="flex items-center gap-1"><Activity size={12} className="text-sky-400" /> Intensidade pluviométrica</span>
                <span className="font-bold text-accent-sky">{rainfallMm} mm</span>
              </div>
              <input
                type="range"
                min="40"
                max="250"
                step="10"
                value={rainfallMm}
                onChange={(e) => setRainfallMm(Number(e.target.value))}
                onPointerDown={() => {}}
                onPointerUp={() => {
                  if (activeTab === 'rainfall' && codigoIbge && municipioLoaded !== false) {
                    void handleSimulate();
                  }
                }}
                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-sky-500"
              />
              <div className="flex justify-between text-[8px] text-zinc-600 font-mono">
                <span>40 mm</span>
                <span>150 mm (Q100 ref.)</span>
                <span>250 mm</span>
              </div>
            </div>

            <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 space-y-3">
              <label className="flex items-center justify-between gap-2 cursor-pointer">
                <span className="text-[10px] font-bold text-zinc-300 uppercase tracking-wide">Comparar com referência</span>
                <input
                  type="checkbox"
                  checked={compareRainfall}
                  onChange={(e) => setCompareRainfall(e.target.checked)}
                  className="accent-sky-500"
                />
              </label>
              {compareRainfall && (
                <div className="flex flex-col gap-1.5">
                  <div className="flex justify-between text-[10px] text-zinc-400">
                    <span>Referência (mm)</span>
                    <span className="font-bold text-zinc-200">{baselineRainfallMm} mm</span>
                  </div>
                  <input
                    type="range"
                    min="40"
                    max="150"
                    step="10"
                    value={baselineRainfallMm}
                    onChange={(e) => setBaselineRainfallMm(Number(e.target.value))}
                    className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-zinc-500"
                  />
                  <p className="text-[9px] text-zinc-500">
                    Cenário atual ({rainfallMm} mm) será comparado com a referência para calcular delta de área, população e profundidade.
                  </p>
                </div>
              )}
            </div>

            <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
              <h5 className="mb-2 flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wide text-zinc-300">
                <Layers size={13} className="text-lime-400" /> Camadas geradas no mapa
              </h5>
              <ul className="space-y-1.5 text-[10px] text-zinc-400">
                <li className="flex items-center gap-2"><span className="h-2 w-4 rounded-sm bg-gradient-to-r from-sky-400 to-indigo-900" /> Manchas por profundidade (superficial → crítica)</li>
                <li className="flex items-center gap-2"><span className="h-0.5 w-4 bg-lime-400" /> Curvas de nível isolinhas (DEM)</li>
                <li className="flex items-center gap-2"><span className="h-0.5 w-4 border-t border-dashed border-cyan-400" /> Vetores de escoamento D8</li>
                <li className="flex items-center gap-2"><span className="h-2 w-4 rounded-sm bg-red-600/70" /> Zonas de deslizamento (encosta)</li>
              </ul>
            </div>

            <div className="rounded-lg border border-sky-500/20 bg-sky-950/10 p-3">
              <h5 className="mb-2 flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wide text-sky-200">
                <Mountain size={13} /> Metodologia
              </h5>
              <p className="text-[10px] leading-relaxed text-zinc-400">
                O motor cruza precipitação, raster SRTM 30 m (±16 m vertical), acúmulo de fluxo D8,
                índice de umidade topográfica (TWI), impermeabilização MapBiomas, corpos d&apos;água,
                IRI por bairro, IVC, histórico S2ID e alertas CEMADEN.
                Isolinhas com intervalo adaptativo ao desnível local; profundidade concentra-se
                em vales e linhas de drenagem.
              </p>
              <p className="mt-2 text-[9px] italic leading-relaxed text-zinc-500">
                Proxy territorial para planejamento — não substitui modelagem hidrodinâmica 2D/HEC-RAS.
              </p>
            </div>
          </div>
        )}

        {activeTab === 'waterproofing' && (
          <div className="flex flex-col gap-4">
            <div>
              <h4 className="font-extrabold text-sm text-zinc-200 flex items-center gap-1.5">
                <AlertTriangle size={16} className="text-accent-sky" /> Aumento de Impermeabilização
              </h4>
              <p className="text-[11px] text-zinc-400 mt-1">Expansão de pavimentação asfáltica e escoamento superficial.</p>
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs text-zinc-300">
                <span>Adicional de Área Impermeável</span>
                <span className="font-bold text-accent-sky">+{waterproofingPct}%</span>
              </div>
              <input
                type="range"
                min="5"
                max="100"
                step="5"
                value={waterproofingPct}
                onChange={(e) => setWaterproofingPct(Number(e.target.value))}
                className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-sky-500"
              />
              <span className="text-[9px] text-zinc-500 italic">Simula a impermeabilização de solo permeável por asfalto/concreto.</span>
            </div>
            <div className="rounded-lg border border-indigo-500/20 bg-indigo-950/10 p-3">
              <h5 className="mb-2 flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wide text-indigo-200">
                <HelpCircle size={13} /> Metodologia da impermeabilização
              </h5>
              <p className="text-[10px] leading-relaxed text-zinc-400">
                A análise aumenta a pressão de escoamento superficial conforme o percentual de área impermeável informado.
                O sistema cruza corpos d'água, bairros, setores censitários e cobertura urbana para estimar a expansão da
                mancha de inundação e a população exposta.
              </p>
              <p className="mt-2 text-[9px] italic leading-relaxed text-zinc-500">
                Resultado demonstrativo: indica sensibilidade territorial à impermeabilização, não substitui estudo de
                drenagem, projeto viário ou licenciamento urbanístico.
              </p>
            </div>
          </div>
        )}

        {activeTab === 'heat_island' && (
          <div className="flex flex-col gap-4">
            <div className="rounded-lg border border-rose-500/25 bg-gradient-to-br from-rose-950/40 to-zinc-950/60 p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h4 className="font-extrabold text-sm text-zinc-100 flex items-center gap-1.5">
                    <Thermometer size={16} className="text-rose-400" /> Ilha de Calor Urbana
                  </h4>
                  <p className="text-[10px] text-rose-200/70 mt-1 uppercase tracking-wider font-bold">
                    MapBiomas · INMET · IVC · densidade por bairro
                  </p>
                </div>
                <span className="shrink-0 rounded-md border border-rose-500/30 bg-rose-500/10 px-2 py-1 text-[9px] font-bold text-rose-200">
                  v{displayedModelVersion}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="rounded-md border border-sky-500/35 bg-sky-500/10 px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-sky-200">
                  Simulação Sinidu · Derivado
                </span>
                {codigoIbge ? (
                  <a
                    href={georedusMunicipioUrl(codigoIbge)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 rounded-md border border-emerald-500/35 bg-emerald-500/10 px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-emerald-200 transition hover:bg-emerald-500/20"
                    title="Ative a camada LST observada no mapa ou abra o GeoReDUS para o município"
                  >
                    LST observada · Observado
                    <ExternalLink size={10} />
                  </a>
                ) : (
                  <span className="rounded-md border border-emerald-500/25 bg-emerald-950/20 px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-emerald-300/70">
                    LST observada · Referência externa
                  </span>
                )}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-2 text-center">
                <span className="block text-[8px] font-bold uppercase tracking-wider text-zinc-500">Pico previsto</span>
                <span className="text-lg font-extrabold text-rose-300">{heatPeakTempC}</span>
                <span className="text-[9px] text-zinc-500"> °C</span>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-2 text-center">
                <span className="block text-[8px] font-bold uppercase tracking-wider text-zinc-500">
                  {heatVegChangePct >= 0 ? 'Arborização' : 'Desmatamento'}
                </span>
                <span className={`text-lg font-extrabold ${heatVegChangePct >= 0 ? 'text-lime-300' : 'text-rose-300'}`}>
                  {heatVegChangePct > 0 ? '+' : ''}{heatVegChangePct}
                </span>
                <span className="text-[9px] text-zinc-500"> %</span>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-2 text-center">
                <span className="block text-[8px] font-bold uppercase tracking-wider text-zinc-500">Asfalto extra</span>
                <span className="text-lg font-extrabold text-amber-300">{heatImpermExtraPct}</span>
                <span className="text-[9px] text-zinc-500"> %</span>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs text-zinc-300">
                <span>Temperatura de pico prevista</span>
                <span className="font-bold text-rose-300">{heatPeakTempC}°C</span>
              </div>
              <input
                type="range"
                min="28"
                max="46"
                step="1"
                value={heatPeakTempC}
                onChange={(e) => setHeatPeakTempC(Number(e.target.value))}
                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-rose-500"
              />
              <div className="flex justify-between text-[8px] text-zinc-600 font-mono">
                <span>28 °C</span>
                <span>36 °C (onda típica)</span>
                <span>46 °C</span>
              </div>
              <span className="text-[9px] text-zinc-500 italic">
                Informe a temperatura máxima prevista (previsão do tempo). Os bairros mais
                impermeabilizados chegam a esse pico somado à intensidade da ilha de calor.
              </span>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs text-zinc-300">
                <span>Cobertura vegetal (desmatar ↔ arborizar)</span>
                <span className={`font-bold ${heatVegChangePct >= 0 ? 'text-lime-300' : 'text-rose-300'}`}>
                  {heatVegChangePct > 0 ? '+' : ''}{heatVegChangePct}%
                </span>
              </div>
              <input
                type="range"
                min="-60"
                max="60"
                step="5"
                value={heatVegChangePct}
                onChange={(e) => setHeatVegChangePct(Number(e.target.value))}
                className={`w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer ${heatVegChangePct >= 0 ? 'accent-lime-500' : 'accent-rose-500'}`}
              />
              <div className="flex justify-between text-[8px] text-zinc-600 font-mono">
                <span>-60% desmatar</span>
                <span>0 atual</span>
                <span>+60% arborizar</span>
              </div>
              <span className="text-[9px] text-zinc-500 italic">
                Positivo simula arborização, telhados verdes e novos parques — converte
                superfície impermeável em vegetada e reduz a ilha de calor.
              </span>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs text-zinc-300">
                <span>Impermeabilização urbana adicional</span>
                <span className="font-bold text-amber-300">{heatImpermExtraPct}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="50"
                step="5"
                value={heatImpermExtraPct}
                onChange={(e) => setHeatImpermExtraPct(Number(e.target.value))}
                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
              />
            </div>

            <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-3">
              <h5 className="mb-2 flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wide text-rose-200">
                <HelpCircle size={13} /> Metodologia
              </h5>
              <p className="text-[10px] leading-relaxed text-zinc-400">
                Modelo temperatura-driven: a partir do pico previsto, a intensidade da ilha de calor (ΔT) de cada
                bairro deriva da impermeabilização e vegetação (MapBiomas) e da densidade populacional, seguindo
                a relação de Oke (1982), e é amplificada pela severidade da onda de calor. A temperatura local
                de cada bairro = pico + ΔT. Arborizar converte superfície impermeável em vegetada e o sistema
                mede o resfriamento obtido contra o cenário sem arborização. O IVC prioriza a exposição da
                população vulnerável. A Sinidu·IA interpreta equipamentos expostos e sugere onde plantar.
              </p>
              <p className="mt-2 text-[9px] italic leading-relaxed text-zinc-500">
                Proxy territorial para oficinas — não substitui medição LST nem estudo microclimático de campo.
              </p>
            </div>
          </div>
        )}

        {activeTab === 'drainage' && (
          <div className="flex flex-col gap-4">
            <div>
              <h4 className="font-extrabold text-sm text-zinc-200 flex items-center gap-1.5">
                <Waves size={16} className="text-cyan-400" /> Déficit de Drenagem Urbana
              </h4>
              <p className="text-[11px] text-zinc-400 mt-1">Estima exposição territorial a falhas operacionais da drenagem.</p>
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs text-zinc-300">
                <span>Déficit Operacional Estimado</span>
                <span className="font-bold text-cyan-300">{drainageDeficitPct}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={drainageDeficitPct}
                onChange={(e) => setDrainageDeficitPct(Number(e.target.value))}
                className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
              />
              <span className="text-[9px] text-zinc-500 italic">Simula perda de desempenho da rede por obstrução, subdimensionamento ou saturação operacional.</span>
            </div>
            <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/10 p-3">
              <h5 className="mb-2 flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wide text-cyan-200">
                <HelpCircle size={13} /> Metodologia da drenagem
              </h5>
              <p className="text-[10px] leading-relaxed text-zinc-400">
                A análise combina o índice de risco de inundação, a presença de área urbana, proximidade com corpos d'água
                e o déficit operacional informado. O modelo estima quais bairros teriam maior exposição caso a rede de
                microdrenagem perca desempenho.
              </p>
              <p className="mt-2 text-[9px] italic leading-relaxed text-zinc-500">
                Resultado demonstrativo: orienta inspeção, limpeza e priorização de obras, mas não substitui cadastro
                técnico completo da rede nem modelagem hidráulica.
              </p>
            </div>
          </div>
        )}

        {activeTab !== 'predictive' && loading && activeTab === 'rainfall' && (
          <div className="mt-4 rounded-lg border border-sky-500/30 bg-sky-950/20 p-3 space-y-2">
            {simProgress && (
              <>
                <div className="flex items-center justify-between text-[10px] text-sky-200">
                  <span>{simProgress.stage_label || 'Processando…'}</span>
                  <span>{simProgress.progress}%</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                  <div
                    className="h-full bg-sky-500 transition-all duration-500"
                    style={{ width: `${Math.max(simProgress.progress, 4)}%` }}
                  />
                </div>
              </>
            )}
            <RotatingLoader messages={SIMULATION_MESSAGES(rainfallMm)} className="text-sky-200" />
          </div>
        )}
        {simError && (
          <p className="mt-2 rounded-lg border border-rose-800/50 bg-rose-950/30 px-3 py-2 text-[10px] text-rose-200">{simError}</p>
        )}

        {activeTab !== 'predictive' && !result && !loading && (
          <EmptyState
            icon={Droplets}
            compact
            className="mt-4"
            title={municipioLoaded === false ? 'Município não integrado' : 'Nenhuma simulação rodada'}
            description={
              municipioLoaded === false
                ? 'Execute o onboarding na aba Municípios para habilitar DEM e simulações hidrológicas.'
                : 'Defina o cenário (mm de chuva, impermeabilização, etc.) e clique em Rodar Simulação. O mapa e o terreno 3D serão atualizados automaticamente.'
            }
          />
        )}

        {/* Action buttons — ocultos na aba preditiva (tem botão próprio) */}
        {activeTab !== 'predictive' && (
        <div className="flex gap-2 mt-5 border-t border-zinc-800 pt-4">
          <button
            onClick={handleSimulate}
            disabled={loading}
            className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-800/40 text-white rounded-lg py-2 px-3 text-xs font-bold transition-all flex items-center justify-center gap-1.5 shadow-md"
          >
            <Play size={14} />
            {loading ? 'Calculando...' : 'Rodar Simulação'}
          </button>
          
          <button
            onClick={handleReset}
            className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg py-2 px-3 text-xs font-bold transition-all flex items-center justify-center gap-1 border border-zinc-700"
          >
            <RotateCcw size={14} />
            Limpar
          </button>
        </div>
        )}
        {activeTab !== 'predictive' && result && (
          <button
            onClick={handleGenerateMitigationPlan}
            disabled={planLoading}
            className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-3 py-2 text-xs font-extrabold text-emerald-200 transition-all hover:bg-emerald-500/25 disabled:opacity-60"
          >
            <FileText size={14} />
            {planLoading ? 'Gerando plano...' : 'Gerar Plano de Ação Sugerido'}
          </button>
        )}
        {activeTab !== 'predictive' && result && (
          <button
            onClick={handleGenerateContingency}
            disabled={contingencyLoading}
            className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-teal-500/40 bg-teal-500/15 px-3 py-2 text-xs font-extrabold text-teal-200 transition-all hover:bg-teal-500/25 disabled:opacity-60"
          >
            <AlertTriangle size={14} />
            {contingencyLoading ? 'Gerando contingência...' : 'Gerar Plano de Contingência'}
          </button>
        )}
      </div>

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
              onClick={handleExportPdf}
              disabled={exportLoading !== null}
              className="rounded-lg border border-sky-500/30 bg-sky-950/20 px-3 py-1.5 text-[10px] font-bold uppercase text-sky-200 hover:bg-sky-950/40 disabled:opacity-50"
            >
              {exportLoading === 'pdf' ? 'Gerando PDF…' : 'PDF para oficina'}
            </button>
          </div>
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
                Observado × simulado — LST GeoReDUS vs Sinidu
              </span>
              {lstCompareLoading && (
                <p className="text-[10px] text-zinc-400 italic">Consultando LST observada nos bairros críticos…</p>
              )}
              {heatLstComparison && !lstCompareLoading && (
                <>
                  <div className="grid grid-cols-2 gap-2 text-[10px]">
                    <div className="rounded border border-zinc-800 bg-zinc-950/60 p-2">
                      <span className="text-zinc-500 block">LST mediana (obs.)</span>
                      <strong className="text-sky-200">
                        {heatLstComparison.lst_mediana_c != null ? `${heatLstComparison.lst_mediana_c}°C` : '—'}
                      </strong>
                    </div>
                    <div className="rounded border border-zinc-800 bg-zinc-950/60 p-2">
                      <span className="text-zinc-500 block">Simulação mediana</span>
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
                            <th className="px-2 py-1 font-bold">LST</th>
                            <th className="px-2 py-1 font-bold">Sim.</th>
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
                      {heatLstComparison.limites_metodologicos.slice(0, 3).map((item) => (
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
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block">Área Afetada</span>
              <span className="text-sm font-extrabold text-zinc-200">{result.affected_area_km2} km²</span>
            </div>
            <div className="bg-zinc-950/60 p-2.5 rounded-lg border border-zinc-800">
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block">Impacto Estimado</span>
              <span className="text-sm font-extrabold text-accent-rose">
                {result.scenario_type === 'VegetationLoss' || result.scenario_type === 'HeatIsland'
                  ? `+${result.impact_value}°C`
                  : `${result.impact_value.toLocaleString()} hab`}
              </span>
            </div>
          </div>

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

          {(result.contours?.features?.length > 0 || result.flow_paths?.features?.length > 0) && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2.5">
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-1.5">Visibilidade no mapa</span>
              <div className="flex flex-wrap gap-2 mb-2">
                {(
                  [
                    { key: 'showFlood' as const, label: 'Manchas de alagamento', activeClass: 'border-sky-500/40 bg-sky-500/15 text-sky-200' },
                    { key: 'showContours' as const, label: 'Curvas de nível', activeClass: 'border-lime-500/40 bg-lime-500/15 text-lime-200' },
                    { key: 'showFlow' as const, label: 'Escoamento D8', activeClass: 'border-cyan-500/40 bg-cyan-500/15 text-cyan-200' },
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
            <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-2">Plano Diretor: pode fazer / não pode fazer</span>
            <div className="grid grid-cols-1 gap-2">
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/10 p-2">
                <strong className="text-[10px] text-emerald-200">Pode priorizar, se compatível</strong>
                {mitigationPlan.diretrizes_plano_diretor.length > 0 ? (
                  mitigationPlan.diretrizes_plano_diretor.map((item, idx) => (
                    <p key={`${item.descricao}-${idx}`} className="mt-1 text-[10px] leading-relaxed text-zinc-400">{item.descricao} <span className="text-zinc-600">({item.fonte})</span></p>
                  ))
                ) : (
                  <p className="mt-1 text-[10px] text-zinc-500">Sem diretriz específica extraída de fonte oficial legível.</p>
                )}
              </div>
              <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-2">
                <strong className="text-[10px] text-rose-200">Não deve / depende de validação legal</strong>
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
    </div>
  );
}
