'use client';

import { useState, useEffect, useRef } from 'react';
import { api, HeatLstComparison, MitigationPlan, RainfallComparison, SimulationInterpret, SimulationOutput, SlopeInterpretation } from '@/utils/api';
import { Play, RotateCcw, AlertTriangle, HelpCircle, Thermometer, Droplet, FileText, Waves, Layers, Mountain, Droplets, ExternalLink, ChevronDown, ChevronRight, Info } from 'lucide-react';
import { georedusMunicipioUrl } from '@/config/georedus';
import PredictiveAnalysis from './PredictiveAnalysis';
import RotatingLoader, { SIMULATION_MESSAGES } from '@/components/UI/RotatingLoader';
import { EmptyState } from '@/design-system';
import Badge from '@/design-system/components/Badge';
import SimulationResults from './SimulationResults';
import { formatDuration, isVolumeSimulation } from './simulationFormat';

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

// 17g.3 — escala de tempo do evento simulado: 1h a 7 dias (índices mapeiam para minutos).
const DURATION_STEPS_MIN = [60, 120, 180, 360, 720, 1440, 2160, 2880, 4320, 7200, 10080];

function durationStepIndex(min: number): number {
  let best = 0;
  let bestDelta = Infinity;
  DURATION_STEPS_MIN.forEach((v, i) => {
    const delta = Math.abs(v - min);
    if (delta < bestDelta) {
      bestDelta = delta;
      best = i;
    }
  });
  return best;
}

export type SimulationTab = 'waterproofing' | 'heat_island' | 'rainfall' | 'drainage' | 'mitigation' | 'climate_extra';

interface SimulationProps {
  onSimulate: (payload: SimulationOutput | any) => void;
  onClear: () => void;
  onSimulatingChange?: (simulating: boolean) => void;
  onFloodClockChange?: (clock: {
    t_h: number;
    fase: string;
    narrativa: string;
    playing: boolean;
    max_depth_m: number | null;
    flood_patches: number | null;
    has_features: boolean;
    duration_h: number;
  } | null) => void;
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
  onFloodClockChange,
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
  const [activeTab, setActiveTab] = useState<SimulationTab>('rainfall');
  const [contingencyNotice, setContingencyNotice] = useState<{ tone: 'ok' | 'error'; message: string } | null>(null);
  const [limitsOpen, setLimitsOpen] = useState(true);
  const [waterproofingPct, setWaterproofingPct] = useState(25);
  const [heatPeakTempC, setHeatPeakTempC] = useState(36);
  // Mudança líquida de cobertura vegetal: negativo = desmatamento, positivo = arborização
  const [heatVegChangePct, setHeatVegChangePct] = useState(20);
  const [heatImpermExtraPct, setHeatImpermExtraPct] = useState(15);
  const [heatShadePct, setHeatShadePct] = useState(0);
  const [heatVentPct, setHeatVentPct] = useState(0);
  const [rainfallMm, setRainfallMm] = useState(105);
  const [rainSlider, setRainSlider] = useState({ min: 20, max: 350, step: 5 });
  const [rainDurationMin, setRainDurationMin] = useState(60);
  const [rainAnchors, setRainAnchors] = useState<
    Array<{
      id: string;
      label: string;
      data: string;
      precipitacao_mm: number;
      duracao_h: number;
      antecedente_mm: number;
      bairros: string[];
      fonte: string;
      url?: string;
      nota?: string;
    }>
  >([]);
  const [showMlScore, setShowMlScore] = useState(false);
  const [idfTr, setIdfTr] = useState<number | null>(null);
  const [idfCurves, setIdfCurves] = useState<
    Array<{ periodo_retorno_anos: number; duracao_min: number; precipitacao_mm: number; label: string }>
  >([]);
  const [idfFonte, setIdfFonte] = useState<string | null>(null);
  const [seaCoastal, setSeaCoastal] = useState(false);
  const [seaScenarios, setSeaScenarios] = useState<Array<{ id: string; label: string; nivel_mar_m: number }>>([]);
  const [seaScenario, setSeaScenario] = useState('atual');
  const [antecedentMm, setAntecedentMm] = useState(0);
  const [showRainAdvanced, setShowRainAdvanced] = useState(false);
  const [aplicarDrenagem, setAplicarDrenagem] = useState(true);
  const [drainageCapMmH, setDrainageCapMmH] = useState(18);
  const [drainageFonte, setDrainageFonte] = useState<string | null>(null);
  const [compareRainfall, setCompareRainfall] = useState(true);
  const [baselineRainfallMm, setBaselineRainfallMm] = useState(80);
  const [rainfallComparison, setRainfallComparison] = useState<RainfallComparison | null>(null);
  const [heatLstComparison, setHeatLstComparison] = useState<HeatLstComparison | null>(null);
  const [lstCompareLoading, setLstCompareLoading] = useState(false);
  const [drainageDeficitPct, setDrainageDeficitPct] = useState(45);
  const [climateModo, setClimateModo] = useState<'seca' | 'arbovirus'>('seca');
  const [climatePrecip72, setClimatePrecip72] = useState(15);
  const [climateTempC, setClimateTempC] = useState(28);
  const [climatePrecip7d, setClimatePrecip7d] = useState(45);
  const [mitigationMode, setMitigationMode] = useState<'solar' | 'green_roof' | 'green_heat' | 'shadow' | 'compare'>('solar');
  const [greenRoofPct, setGreenRoofPct] = useState(30);
  const [greenRoofRainMm, setGreenRoofRainMm] = useState(100);
  const [greenHeatArborPct, setGreenHeatArborPct] = useState(25);
  const [greenHeatPeakC, setGreenHeatPeakC] = useState(36);
  const [shadowHour, setShadowHour] = useState(14);
  const [compareTipo, setCompareTipo] = useState<'telhado_verde' | 'infraverde_calor' | 'solar'>('telhado_verde');
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulationOutput | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [contingencyLoading, setContingencyLoading] = useState(false);
  const [mitigationPlan, setMitigationPlan] = useState<MitigationPlan | null>(null);
  const [exportLoading, setExportLoading] = useState<'geojson' | 'pdf' | 'kmz' | null>(null);
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
  const [floodTIndex, setFloodTIndex] = useState(0);
  const [floodPlaying, setFloodPlaying] = useState(false);
  const [floodLoop, setFloodLoop] = useState(true);
  const [floodSpeedMs, setFloodSpeedMs] = useState(500);
  const floodPlayRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [calibBusy, setCalibBusy] = useState(false);
  const [calibMsg, setCalibMsg] = useState<string | null>(null);

  const publishFloodClock = (
    data: SimulationOutput | null,
    tIndex: number,
    playing: boolean,
  ) => {
    if (!onFloodClockChange) return;
    const timeline = data?.simulation_meta?.flood_timeline;
    if (!timeline) {
      onFloodClockChange(null);
      return;
    }
    const step = timeline.steps[tIndex] || timeline.steps[timeline.peak_index];
    const hasFeatures = Boolean(data?.simulation_meta?.flood_timeline_features?.length);
    onFloodClockChange({
      t_h: step?.t_h ?? 0,
      fase: step?.fase || '—',
      narrativa:
        step?.narrativa
        || (step?.fase === 'pico'
          ? 'Pico da inundação estimada neste cenário.'
          : step?.fase === 'subida'
            ? 'A mancha sobe — áreas mais baixas começam a alagar.'
            : 'A água recua — mancha reduz (aproximação, sem routing 2D).'),
      playing,
      max_depth_m: step?.max_depth_m ?? null,
      flood_patches: step?.flood_patches ?? null,
      has_features: hasFeatures,
      duration_h: timeline.duration_h,
    });
  };

  const applyFloodTimelineFrame = (data: SimulationOutput, tIndex: number, playing = floodPlaying) => {
    const timeline = data.simulation_meta?.flood_timeline;
    const byStep = data.simulation_meta?.flood_timeline_features;
    publishFloodClock(data, tIndex, playing);
    if (!timeline || !byStep?.length) return;
    const idx = Math.max(0, Math.min(tIndex, byStep.length - 1));
    const floodFeats = byStep[idx] || [];
    const landslides = (data.geometry?.features || []).filter(
      (f: { properties?: { layer_type?: string } }) => f?.properties?.layer_type === 'landslide',
    );
    onSimulate({
      ...data,
      geometry: {
        type: 'FeatureCollection',
        features: [...floodFeats, ...landslides],
      },
    });
  };

  useEffect(() => {
    if (!result?.simulation_meta?.flood_timeline) {
      setFloodPlaying(false);
      onFloodClockChange?.(null);
      return;
    }
    const peak = result.simulation_meta.flood_timeline.peak_index ?? 0;
    setFloodTIndex(peak);
    setFloodPlaying(false);
    publishFloodClock(result, peak, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  useEffect(() => {
    if (floodPlayRef.current) {
      clearInterval(floodPlayRef.current);
      floodPlayRef.current = null;
    }
    if (!floodPlaying || !result?.simulation_meta?.flood_timeline) return;
    const n = result.simulation_meta.flood_timeline.n_steps;
    floodPlayRef.current = setInterval(() => {
      setFloodTIndex((prev) => {
        let next = prev + 1;
        if (next >= n) {
          if (!floodLoop) {
            setFloodPlaying(false);
            publishFloodClock(result, prev, false);
            return prev;
          }
          next = 0;
        }
        applyFloodTimelineFrame(result, next, true);
        return next;
      });
    }, floodSpeedMs);
    return () => {
      if (floodPlayRef.current) clearInterval(floodPlayRef.current);
      floodPlayRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [floodPlaying, result, floodSpeedMs, floodLoop]);

  useEffect(() => {
    if (!codigoIbge) {
      setIdfCurves([]);
      setIdfFonte(null);
      setIdfTr(null);
      setSeaCoastal(false);
      setSeaScenarios([]);
      setSeaScenario('atual');
      setDrainageFonte(null);
      return;
    }
    let cancelled = false;
    api
      .getIdfCurves(codigoIbge)
      .then((cat) => {
        if (cancelled) return;
        // Preferir 24h (série diária APAC/INMET) quando existir; senão 60 min.
        const preferDur = (cat.curvas || []).some((c) => c.duracao_min === 1440) ? 1440 : (cat.default_duracao_min || 60);
        const curves = (cat.curvas || []).filter((c) => c.duracao_min === preferDur);
        setIdfCurves(curves.length ? curves : (cat.curvas || []).filter((c) => c.duracao_min === 60));
        setIdfFonte(cat.fonte);
      })
      .catch(() => {
        if (!cancelled) {
          setIdfCurves([]);
          setIdfFonte(null);
        }
      });
    api
      .getRainfallAnchors(codigoIbge)
      .then((cat) => {
        if (cancelled) return;
        setRainAnchors(cat.anchors || []);
        if (cat.slider) {
          setRainSlider({
            min: Math.round(cat.slider.min_mm),
            max: Math.round(cat.slider.max_mm),
            step: Math.round(cat.slider.step_mm) || 5,
          });
          if (cat.slider.default_mm != null) {
            setRainfallMm((prev) => (prev === 105 || prev === 120 ? Math.round(cat.slider.default_mm) : prev));
          }
        }
      })
      .catch(() => {
        if (!cancelled) setRainAnchors([]);
      });
    api
      .getSeaLevelScenarios(codigoIbge)
      .then((sl) => {
        if (cancelled) return;
        setSeaCoastal(Boolean(sl.costeiro));
        setSeaScenarios(sl.cenarios_disponiveis || []);
      })
      .catch(() => {
        if (!cancelled) {
          setSeaCoastal(false);
          setSeaScenarios([]);
        }
      });
    api
      .getDrainageCapacity(codigoIbge, rainfallMm, 60)
      .then((d) => {
        if (cancelled) return;
        if (d.capacidade_mm_h != null) setDrainageCapMmH(Math.round(d.capacidade_mm_h));
        setDrainageFonte(d.fonte || null);
      })
      .catch(() => {
        if (!cancelled) setDrainageFonte(null);
      });
    return () => {
      cancelled = true;
    };
  }, [codigoIbge]);

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
    if (activeTab === 'heat_island' || activeTab === 'climate_extra') return 'calor';
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
      } else if (activeTab === 'climate_extra') {
        data = await api.simulateClimateModule({
          codigoIbge,
          modo: climateModo,
          ...(climateModo === 'seca'
            ? { precip72hMm: climatePrecip72, precipEsperada72hMm: 25 }
            : { temperaturaMediaC: climateTempC, precip7dMm: climatePrecip7d }),
        });
      } else if (activeTab === 'heat_island') {
        data = await api.simulateHeatIsland({
          temperaturaPicoC: heatPeakTempC,
          perdaVegetalPct: heatVegChangePct < 0 ? -heatVegChangePct : 0,
          ganhoVegetalPct: heatVegChangePct > 0 ? heatVegChangePct : 0,
          impermeabilizacaoExtraPct: heatImpermExtraPct,
          sombreamentoPct: heatShadePct,
          corredoresVentoPct: heatVentPct,
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
      } else if (activeTab === 'mitigation') {
        if (mitigationMode === 'solar') {
          data = await api.simulateSolarRooftop(codigoIbge) as SimulationOutput;
        } else if (mitigationMode === 'green_roof') {
          data = await api.simulateGreenRoof({
            codigoIbge,
            precipitacaoMm: greenRoofRainMm,
            telhadoVerdePct: greenRoofPct,
          }) as SimulationOutput;
        } else if (mitigationMode === 'green_heat') {
          data = await api.simulateGreenInfraHeat({
            codigoIbge,
            temperaturaPicoC: greenHeatPeakC,
            arborizacaoPct: greenHeatArborPct,
          }) as SimulationOutput;
        } else if (mitigationMode === 'shadow') {
          data = await api.simulateShadowInsolation({
            codigoIbge,
            horaLocal: shadowHour,
          }) as SimulationOutput;
        } else {
          data = await api.compareInterventions({
            codigoIbge,
            tipo: compareTipo,
            precipitacaoMm: greenRoofRainMm,
            telhadoVerdePct: greenRoofPct,
            temperaturaPicoC: greenHeatPeakC,
            arborizacaoPct: greenHeatArborPct,
          }) as SimulationOutput;
        }
      } else if (compareRainfall) {
        comparison = await api.compareRainfallScenariosAsync(
          rainfallMm,
          baselineRainfallMm,
          codigoIbge,
          onJobProgress,
          rainDurationMin,
        );
        setRainfallComparison(comparison);
        data = comparison.scenario;
      } else {
        data = await api.simulateExtremeRainfallAsync(
          rainfallMm,
          codigoIbge,
          onJobProgress,
          {
            ...(idfTr != null ? { periodoRetornoAnos: idfTr } : {}),
            duracaoMin: rainDurationMin,
            ...(seaCoastal && seaScenario !== 'atual' ? { cenarioNivelMar: seaScenario } : {}),
            chuvaAntecedenteMm: antecedentMm,
            aplicarDrenagem,
            drainageCapacityMmH: aplicarDrenagem ? drainageCapMmH : undefined,
          },
        );
      }
      setResult(data);
      if (data?.geometry?.features?.length || (data as { features?: unknown[] })?.features?.length) {
        const peak = data.simulation_meta?.flood_timeline?.peak_index;
        if (peak != null && data.simulation_meta?.flood_timeline_features?.length) {
          setFloodTIndex(peak);
          applyFloodTimelineFrame(data, peak);
        } else {
          onSimulate(data);
        }
      } else {
        setSimError('Simulação concluída, mas sem manchas para exibir no mapa.');
      }
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

  const handleExportKmz = async () => {
    if (!result) return;
    setExportLoading('kmz');
    try {
      const meta = await api.exportSimulationKmz(
        result,
        codigoIbge,
        rainfallComparison?.delta,
      );
      await api.downloadReport(meta.download_url, meta.nome_arquivo);
    } catch (err) {
      console.error('Export KMZ failed:', err);
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
      setContingencyNotice({
        tone: 'ok',
        message: 'Plano de contingência gerado como rascunho. Abra a aba Contingência para editar.',
      });
    } catch (err) {
      console.error('Error generating contingency plan:', err);
      setContingencyNotice({
        tone: 'error',
        message: err instanceof Error ? err.message : 'Falha ao gerar o plano de contingência.',
      });
    } finally {
      setContingencyLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 p-1">
      {contingencyNotice && (
        <div
          className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-[11px] ${
            contingencyNotice.tone === 'ok'
              ? 'border-emerald-700/50 bg-emerald-950/30 text-emerald-100'
              : 'border-rose-700/50 bg-rose-950/30 text-rose-100'
          }`}
        >
          <span className="flex-1">{contingencyNotice.message}</span>
          <button
            type="button"
            onClick={() => setContingencyNotice(null)}
            className="shrink-0 opacity-70 hover:opacity-100"
            aria-label="Dispensar aviso"
          >
            ✕
          </button>
        </div>
      )}
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
      {/* Simulation Selector tabs — Chuva unifica mancha DEM + score preditivo */}
      <div className="grid grid-cols-6 gap-1 bg-zinc-950 p-1 rounded-lg border border-border">
        {(['rainfall', 'waterproofing', 'heat_island', 'climate_extra', 'drainage', 'mitigation'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setResult(null); setMitigationPlan(null); setSimInterpret(null); setInterpretError(null); onClear(); }}
            className={`py-1.5 px-0.5 rounded text-[8px] font-bold uppercase tracking-wider transition-all ${
              activeTab === tab 
                ? 'bg-card text-indigo-400 border border-zinc-800' 
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {tab === 'rainfall' ? 'Chuva' : tab === 'waterproofing' ? 'Asfalto' : tab === 'heat_island' ? 'Calor' : tab === 'climate_extra' ? 'Seca/Arb' : tab === 'drainage' ? 'Drenagem' : 'Mitigar'}
          </button>
        ))}
      </div>

      {/* 20h.2 — limites metodológicos sempre visíveis na aba Simulações */}
      <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 px-3 py-2.5">
          <button
            type="button"
            onClick={() => setLimitsOpen((v) => !v)}
            className="flex w-full items-center justify-between gap-2 text-left"
          >
            <span className="flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wider text-amber-200">
              <Info size={12} />
              Limites metodológicos · triagem ≠ laudo
            </span>
            {limitsOpen ? <ChevronDown size={14} className="text-amber-300" /> : <ChevronRight size={14} className="text-amber-300" />}
          </button>
          {limitsOpen && (
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <div>
                <p className="text-[9px] font-bold uppercase tracking-wide text-emerald-300/90">O que é</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[10px] leading-relaxed text-zinc-300">
                  <li>Triagem territorial para priorizar bairros e ensaiar contingência</li>
                  <li>Estimativa com DEM, chuva/cenário e proxies de uso do solo</li>
                  <li>Selo de qualidade visível (Oficial · Observado · Estimado · Derivado)</li>
                </ul>
              </div>
              <div>
                <p className="text-[9px] font-bold uppercase tracking-wide text-rose-300/90">O que não é</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[10px] leading-relaxed text-zinc-300">
                  <li>Laudo de engenharia, perícia ou projeto executivo</li>
                  <li>HEC-RAS / SWMM / hidrodinâmica 2D completa</li>
                  <li>Alerta oficial CEMADEN / Defesa Civil</li>
                  <li>Metodologia oficial ANA/CPRM/IDF (salvo selo Oficial explícito)</li>
                </ul>
              </div>
            </div>
          )}
        </div>

      {/* Simulator Forms */}
      <div className="bg-card/40 backdrop-blur-md border border-border p-4 rounded-xl">
        {activeTab === 'rainfall' && (
          <div className="flex flex-col gap-4">
            <div className="rounded-lg border border-sky-500/25 bg-gradient-to-br from-sky-950/40 to-zinc-950/60 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h4 className="font-extrabold text-sm text-zinc-100 flex items-center gap-1.5">
                    <Droplet size={16} className="text-accent-sky" /> Onde alaga se chover forte?
                  </h4>
                  <p className="mt-1.5 text-[11px] leading-relaxed text-zinc-400">
                    Um único fluxo: volume de chuva (IDF + eventos históricos APAC/CEMADEN/imprensa) →
                    mancha DEM no mapa, população atingida, deslizamento, mobilidade e tempo de escoamento.
                    Score multi-horizonte (ML) fica opcional abaixo — mesmo cenário.
                  </p>
                </div>
                <Badge tone="derived">Simulação · Derivado</Badge>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs text-zinc-300">
                <span className="font-semibold">Quanto chove neste cenário?</span>
                <span className="font-bold text-accent-sky">{rainfallMm} mm</span>
              </div>
              {idfCurves.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <p className="text-[11px] text-zinc-400">
                    Atalhos IDF{idfFonte ? ` · ${idfFonte}` : ''} (quanto mais raro, mais mm)
                  </p>
                  <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
                    {idfCurves.map((c) => {
                      const active = idfTr === c.periodo_retorno_anos;
                      const label =
                        c.periodo_retorno_anos === 2
                          ? 'Frequente'
                          : c.periodo_retorno_anos === 10
                            ? 'Forte'
                            : c.periodo_retorno_anos === 25
                              ? 'Muito forte'
                              : 'Extrema';
                      return (
                        <button
                          key={c.periodo_retorno_anos}
                          type="button"
                          title={`Evento que ocorre em média 1 vez a cada ${c.periodo_retorno_anos} anos · ${c.duracao_min} min`}
                          onClick={() => {
                            setIdfTr(c.periodo_retorno_anos);
                            setRainfallMm(Math.round(c.precipitacao_mm));
                            setRainDurationMin(DURATION_STEPS_MIN[durationStepIndex(c.duracao_min)]);
                          }}
                          className={`rounded-lg border px-2 py-2 text-left transition ${
                            active
                              ? 'border-sky-400/50 bg-sky-500/20 text-sky-100'
                              : 'border-zinc-700 bg-zinc-950/70 text-zinc-300 hover:border-zinc-500'
                          }`}
                        >
                          <span className="block text-[11px] font-bold">{label}</span>
                          <span className="block text-[10px] text-zinc-400">
                            ~{Math.round(c.precipitacao_mm)} mm · 1/{c.periodo_retorno_anos} anos
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
              {rainAnchors.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <p className="text-[11px] text-zinc-400">
                    Eventos históricos documentados (calibram o volume — não são a mancha)
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {rainAnchors.map((a) => {
                      const active = Math.abs(rainfallMm - a.precipitacao_mm) <= 8;
                      return (
                        <button
                          key={a.id}
                          type="button"
                          title={a.nota || a.fonte}
                          onClick={() => {
                            setIdfTr(null);
                            setRainfallMm(Math.round(a.precipitacao_mm));
                            setRainDurationMin(DURATION_STEPS_MIN[durationStepIndex(a.duracao_h * 60)]);
                            setAntecedentMm(Math.round(a.antecedente_mm));
                            setShowRainAdvanced(true);
                          }}
                          className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition ${
                            active
                              ? 'border-amber-400/50 bg-amber-500/20 text-amber-100'
                              : 'border-zinc-700 bg-zinc-950/70 text-zinc-300 hover:border-amber-500/40'
                          }`}
                        >
                          {a.label} · {Math.round(a.precipitacao_mm)} mm/{formatDuration(a.duracao_h * 60)}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
              <input
                type="range"
                min={rainSlider.min}
                max={rainSlider.max}
                step={rainSlider.step}
                value={Math.min(rainSlider.max, Math.max(rainSlider.min, rainfallMm))}
                onChange={(e) => {
                  setIdfTr(null);
                  setRainfallMm(Number(e.target.value));
                }}
                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-sky-500"
              />
              <div className="flex justify-between text-[9px] text-zinc-600">
                <span>{rainSlider.min} mm</span>
                <span className="text-zinc-500">passo {rainSlider.step} mm · ajuste e clique em Rodar Simulação</span>
                <span>{rainSlider.max} mm</span>
              </div>
            </div>

            <div className="flex flex-col gap-2 rounded-lg border border-violet-500/25 bg-violet-950/10 p-2.5">
              <div className="flex flex-wrap items-baseline justify-between gap-1">
                <span className="text-xs font-semibold text-zinc-300">
                  Em quanto tempo cai essa chuva?
                </span>
                <span className="font-bold text-violet-300">
                  {formatDuration(rainDurationMin)}
                  <span className="ml-1.5 font-normal text-[10px] text-zinc-500">
                    ≈ {(rainfallMm / (rainDurationMin / 60)).toFixed(rainDurationMin >= 1440 ? 1 : 0)} mm/h
                  </span>
                </span>
              </div>
              <p className="text-[10px] leading-relaxed text-zinc-500">
                Mesmos {rainfallMm} mm concentrados em 1h formam mancha muito mais abrupta que
                espalhados em vários dias — a duração muda intensidade, mancha, deslizamento e hidrograma.
              </p>
              <input
                type="range"
                min={0}
                max={DURATION_STEPS_MIN.length - 1}
                step={1}
                value={durationStepIndex(rainDurationMin)}
                onChange={(e) => setRainDurationMin(DURATION_STEPS_MIN[Number(e.target.value)])}
                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-violet-500"
              />
              <div className="flex justify-between text-[9px] text-zinc-600">
                <span>1 h (flash)</span>
                <span>24 h</span>
                <span>7 dias (sustentada)</span>
              </div>
            </div>

            <div className="rounded-lg border border-zinc-800 bg-zinc-950/50">
              <button
                type="button"
                onClick={() => setShowRainAdvanced((v) => !v)}
                className="flex w-full items-center justify-between px-3 py-2.5 text-left"
              >
                <span className="text-[11px] font-semibold text-zinc-300">
                  Opções avançadas
                  {(seaCoastal && seaScenario !== 'atual') || antecedentMm > 0 || !aplicarDrenagem ? (
                    <span className="ml-1.5 text-[9px] font-normal text-sky-400/80">· ativas</span>
                  ) : null}
                </span>
                <span className="text-zinc-500">{showRainAdvanced ? '−' : '+'}</span>
              </button>
              {showRainAdvanced && (
                <div className="space-y-3 border-t border-zinc-800 px-3 py-3">
                  {seaCoastal && seaScenarios.length > 0 && (
                    <div className="space-y-1.5">
                      <p className="text-[11px] font-semibold text-zinc-200">Mar mais alto (cidade costeira)</p>
                      <p className="text-[10px] leading-snug text-zinc-500">
                        Simula maré meteórica ou elevação futura do mar — a água sobe a partir de uma cota mais alta e a mancha de alagamento cresce nas áreas baixas.
                      </p>
                      <select
                        value={seaScenario}
                        onChange={(e) => setSeaScenario(e.target.value)}
                        className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-[11px] text-zinc-200"
                      >
                        {seaScenarios.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  <div className="space-y-1.5">
                    <label className="flex items-center justify-between gap-2 cursor-pointer">
                      <div>
                        <span className="block text-[11px] font-semibold text-zinc-200">Rede de drenagem (proxy)</span>
                        <span className="block text-[10px] text-zinc-500">
                          Remove parte da água como se galerias/bueiros absorvessem a chuva (SNIS/densidade). Não é inventário de rede.
                          {drainageFonte ? ` · fonte ${drainageFonte}` : ''}
                        </span>
                      </div>
                      <input
                        type="checkbox"
                        checked={aplicarDrenagem}
                        onChange={(e) => setAplicarDrenagem(e.target.checked)}
                        className="accent-cyan-500"
                      />
                    </label>
                    {aplicarDrenagem && (
                      <>
                        <div className="flex justify-between text-[11px]">
                          <span className="text-zinc-400">Capacidade da rede</span>
                          <span className="text-cyan-300">{drainageCapMmH} mm/h</span>
                        </div>
                        <input
                          type="range"
                          min="8"
                          max="50"
                          step="1"
                          value={drainageCapMmH}
                          onChange={(e) => setDrainageCapMmH(Number(e.target.value))}
                          className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                        />
                        <div className="flex justify-between text-[9px] text-zinc-600">
                          <span>Rede frágil</span>
                          <span>Rede robusta</span>
                        </div>
                      </>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex justify-between text-[11px]">
                      <span className="font-semibold text-zinc-200">Solo já molhado (dias anteriores)</span>
                      <span className="text-amber-300">{antecedentMm} mm</span>
                    </div>
                    <p className="text-[10px] leading-snug text-zinc-500">
                      Se choveu antes, o solo satura e encostas escorregam com mais facilidade. Ajuste para ver risco de deslizamento além do alagamento.
                    </p>
                    <input
                      type="range"
                      min="0"
                      max="200"
                      step="10"
                      value={antecedentMm}
                      onChange={(e) => setAntecedentMm(Number(e.target.value))}
                      className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
                    />
                    <div className="flex justify-between text-[9px] text-zinc-600">
                      <span>Solo seco</span>
                      <span>Solo saturado</span>
                    </div>
                  </div>

                  <label className="flex items-center justify-between gap-2 cursor-pointer pt-1">
                    <div>
                      <span className="block text-[11px] font-semibold text-zinc-200">Comparar com outro volume</span>
                      <span className="block text-[10px] text-zinc-500">Mostra a diferença (área e gente afetada) entre dois totais de chuva.</span>
                    </div>
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
                        <span>Referência</span>
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
                    </div>
                  )}
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

            <div className="rounded-lg border border-violet-500/25 bg-violet-950/10">
              <button
                type="button"
                onClick={() => setShowMlScore((v) => !v)}
                className="flex w-full items-center justify-between px-3 py-2.5 text-left"
              >
                <span className="text-[11px] font-semibold text-violet-200">
                  Score preditivo multi-horizonte (ML) — opcional
                </span>
                <span className="text-zinc-500">{showMlScore ? '−' : '+'}</span>
              </button>
              {showMlScore && (
                <div className="border-t border-violet-500/20 px-3 py-3">
                  <PredictiveAnalysis
                    embedded
                    codigoIbge={codigoIbge}
                    municipioNome={municipioNome}
                    municipioLoaded={municipioLoaded}
                    precipEventMm={rainfallMm}
                    antecedentMm={antecedentMm}
                    onPredict={onSimulate}
                    onClear={onClear}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'waterproofing' && (
          <div className="flex flex-col gap-4">
            <div>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h4 className="font-extrabold text-sm text-zinc-200 flex items-center gap-1.5">
                    <AlertTriangle size={16} className="text-accent-sky" /> Aumento de Impermeabilização
                  </h4>
                  <p className="text-[11px] text-zinc-400 mt-1">Expansão de pavimentação asfáltica e escoamento superficial.</p>
                </div>
                <Badge tone="derived">Simulação · Derivado</Badge>
              </div>
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
                <Badge tone="derived">Cenário Sinidu · Derivado</Badge>
                {codigoIbge ? (
                  <a
                    href={georedusMunicipioUrl(codigoIbge)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 rounded-md border border-sky-500/35 bg-sky-500/10 px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-sky-200 transition hover:bg-sky-500/20"
                    title="Ative a camada LST observada no mapa ou abra o GeoReDUS para o município"
                  >
                    LST GeoReDUS · Observado
                    <ExternalLink size={10} />
                  </a>
                ) : (
                  <Badge tone="info">LST observada · Observado</Badge>
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

            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs text-zinc-300">
                <span>Sombreamento adicional (edifícios / dossel)</span>
                <span className="font-bold text-sky-300">{heatShadePct}%</span>
              </div>
              <p className="text-[9px] text-zinc-500">
                Combina altura média das edificações com intervenção (toldos, galerias, fachadas). Reduz o ΔT da ilha de calor.
              </p>
              <input
                type="range"
                min="0"
                max="80"
                step="5"
                value={heatShadePct}
                onChange={(e) => setHeatShadePct(Number(e.target.value))}
                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-sky-500"
              />
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs text-zinc-300">
                <span>Corredores de vento / espaço aberto</span>
                <span className="font-bold text-cyan-300">{heatVentPct}%</span>
              </div>
              <p className="text-[9px] text-zinc-500">
                Aberturas e vias alinhadas ao vento — proxy por tecido urbano aberto + intervenção. Atenua o calor de dossel.
              </p>
              <input
                type="range"
                min="0"
                max="80"
                step="5"
                value={heatVentPct}
                onChange={(e) => setHeatVentPct(Number(e.target.value))}
                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
              />
            </div>

            <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-3">
              <h5 className="mb-2 flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wide text-rose-200">
                <HelpCircle size={13} /> Metodologia
              </h5>
              <p className="text-[10px] leading-relaxed text-zinc-400">
                Modelo temperatura-driven: a partir do pico previsto, a intensidade da ilha de calor (ΔT) de cada
                bairro deriva da impermeabilização e vegetação (MapBiomas) e da densidade populacional, seguindo
                a relação de Oke (1982), e é amplificada pela severidade da onda de calor. Sombreamento por
                edificações e corredores de vento atenuam o ΔT. Arborizar converte superfície impermeável em vegetada.
                O IVC prioriza a exposição da população vulnerável.
              </p>
              <p className="mt-2 text-[9px] italic leading-relaxed text-zinc-500">
                Proxy territorial — não substitui LST, ray-tracing de sombra nem estudo de vento de campo.
              </p>
            </div>
          </div>
        )}

        {activeTab === 'climate_extra' && (
          <div className="flex flex-col gap-4">
            <div>
              <h4 className="font-extrabold text-zinc-100 text-sm">Seca e arbovírus (proxy)</h4>
              <p className="text-[11px] text-zinc-400 mt-1">
                Módulos climáticos extras: estresse hídrico e condições ambientais favoráveis a Aedes — sem incidência epidemiológica.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-1 rounded-lg border border-zinc-800 bg-zinc-950 p-1">
              <button
                type="button"
                onClick={() => setClimateModo('seca')}
                className={`rounded px-2 py-1.5 text-[10px] font-bold uppercase ${
                  climateModo === 'seca' ? 'bg-amber-500/20 text-amber-100' : 'text-zinc-500'
                }`}
              >
                Estresse hídrico
              </button>
              <button
                type="button"
                onClick={() => setClimateModo('arbovirus')}
                className={`rounded px-2 py-1.5 text-[10px] font-bold uppercase ${
                  climateModo === 'arbovirus' ? 'bg-rose-500/20 text-rose-100' : 'text-zinc-500'
                }`}
              >
                Proxy arbovírus
              </button>
            </div>

            {climateModo === 'seca' ? (
              <div className="space-y-2">
                <div className="flex justify-between text-[11px]">
                  <span className="font-semibold text-zinc-200">Chuva recente (72h)</span>
                  <span className="text-amber-300">{climatePrecip72} mm</span>
                </div>
                <p className="text-[10px] text-zinc-500">
                  Menos chuva que o esperado → maior estresse, pior onde há muita impermeabilização e pouca vegetação.
                </p>
                <input
                  type="range"
                  min="0"
                  max="80"
                  step="5"
                  value={climatePrecip72}
                  onChange={(e) => setClimatePrecip72(Number(e.target.value))}
                  className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
                />
              </div>
            ) : (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <div className="flex justify-between text-[11px]">
                    <span className="font-semibold text-zinc-200">Temperatura média</span>
                    <span className="text-rose-300">{climateTempC} °C</span>
                  </div>
                  <p className="text-[10px] text-zinc-500">Ótimo Aedes ~28 °C (faixa útil 18–34 °C).</p>
                  <input
                    type="range"
                    min="18"
                    max="36"
                    step="1"
                    value={climateTempC}
                    onChange={(e) => setClimateTempC(Number(e.target.value))}
                    className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-rose-500"
                  />
                </div>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-[11px]">
                    <span className="font-semibold text-zinc-200">Chuva recente (proxy 7d)</span>
                    <span className="text-sky-300">{climatePrecip7d} mm</span>
                  </div>
                  <p className="text-[10px] text-zinc-500">
                    Água parada pós-chuva × drenagem fraca × habitat urbano (impermeável / baixa vegetação).
                  </p>
                  <input
                    type="range"
                    min="0"
                    max="150"
                    step="5"
                    value={climatePrecip7d}
                    onChange={(e) => setClimatePrecip7d(Number(e.target.value))}
                    className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-sky-500"
                  />
                </div>
              </div>
            )}

            <div className="rounded-lg border border-amber-500/20 bg-amber-950/10 p-3">
              <p className="text-[10px] leading-relaxed text-zinc-400">
                {climateModo === 'seca'
                  ? 'Índice municipal 0–100 por déficit de precipitação × cobertura do solo (MapBiomas). Não é SPEI/SPI oficial.'
                  : 'Proxy ambiental (temperatura × água parada × habitat). Não estima casos de dengue/zika nem substitui vigilância epidemiológica.'}
              </p>
            </div>
          </div>
        )}

        {activeTab === 'drainage' && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h4 className="font-extrabold text-sm text-zinc-200 flex items-center gap-1.5">
                  <Waves size={16} className="text-cyan-400" /> Déficit de Drenagem Urbana
                </h4>
                <p className="text-[11px] text-zinc-400 mt-1">Estima exposição territorial a falhas operacionais da drenagem.</p>
              </div>
              <Badge tone="derived">Simulação · Derivado</Badge>
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

        {activeTab === 'mitigation' && (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-1 rounded-lg border border-zinc-800 bg-zinc-950 p-1 sm:grid-cols-5">
              {([
                ['solar', 'Solar'],
                ['green_roof', 'Telhado verde'],
                ['green_heat', 'Verde × calor'],
                ['shadow', 'Sombra'],
                ['compare', 'Comparar'],
              ] as const).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => { setMitigationMode(id); setResult(null); }}
                  className={`rounded px-2 py-1.5 text-[9px] font-bold uppercase ${
                    mitigationMode === id
                      ? 'border border-lime-500/30 bg-lime-500/20 text-lime-200'
                      : 'text-zinc-400'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {mitigationMode === 'solar' && (
              <div className="rounded-lg border border-amber-500/20 bg-amber-950/10 p-3 space-y-2">
                <h4 className="text-sm font-extrabold text-zinc-100">Potencial solar (LOD1)</h4>
                <p className="text-[10px] leading-relaxed text-zinc-400">
                  Estima kWp e geração anual a partir da área de footprint × HSP local.
                </p>
              </div>
            )}

            {mitigationMode === 'green_roof' && (
              <div className="space-y-3">
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs text-zinc-300">
                    <span>Telhados convertidos em verdes</span>
                    <span className="font-bold text-lime-300">{greenRoofPct}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={greenRoofPct}
                    onChange={(e) => setGreenRoofPct(Number(e.target.value))}
                    className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-lime-500"
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs text-zinc-300">
                    <span>Chuva de referência</span>
                    <span className="font-bold text-sky-300">{greenRoofRainMm} mm</span>
                  </div>
                  <input
                    type="range"
                    min="40"
                    max="250"
                    step="10"
                    value={greenRoofRainMm}
                    onChange={(e) => setGreenRoofRainMm(Number(e.target.value))}
                    className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-sky-500"
                  />
                </div>
              </div>
            )}

            {mitigationMode === 'green_heat' && (
              <div className="space-y-3">
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs text-zinc-300">
                    <span>Arborização / parques</span>
                    <span className="font-bold text-lime-300">+{greenHeatArborPct}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="60"
                    step="5"
                    value={greenHeatArborPct}
                    onChange={(e) => setGreenHeatArborPct(Number(e.target.value))}
                    className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-lime-500"
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs text-zinc-300">
                    <span>Pico de temperatura</span>
                    <span className="font-bold text-rose-300">{greenHeatPeakC} °C</span>
                  </div>
                  <input
                    type="range"
                    min="28"
                    max="46"
                    step="1"
                    value={greenHeatPeakC}
                    onChange={(e) => setGreenHeatPeakC(Number(e.target.value))}
                    className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-rose-500"
                  />
                </div>
                <p className="text-[9px] text-zinc-500 italic">
                  Compara ΔT da ilha de calor sem vs com ganho de vegetação.
                </p>
              </div>
            )}

            {mitigationMode === 'shadow' && (
              <div className="space-y-3">
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs text-zinc-300">
                    <span>Hora do dia (local)</span>
                    <span className="font-bold text-amber-300">{shadowHour}h</span>
                  </div>
                  <input
                    type="range"
                    min="6"
                    max="18"
                    step="1"
                    value={shadowHour}
                    onChange={(e) => setShadowHour(Number(e.target.value))}
                    className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
                  />
                </div>
                <p className="text-[9px] text-zinc-500 italic">
                  Insolação por edifício (posição solar × sombra de vizinhos mais altos).
                </p>
              </div>
            )}

            {mitigationMode === 'compare' && (
              <div className="space-y-3">
                <p className="text-[10px] text-zinc-400">Escolha a intervenção para ver antes/depois:</p>
                <div className="grid grid-cols-3 gap-1">
                  {([
                    ['telhado_verde', 'Telhado'],
                    ['infraverde_calor', 'Calor'],
                    ['solar', 'Solar'],
                  ] as const).map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setCompareTipo(id)}
                      className={`rounded border px-2 py-1.5 text-[9px] font-bold uppercase ${
                        compareTipo === id
                          ? 'border-indigo-500/40 bg-indigo-500/20 text-indigo-200'
                          : 'border-zinc-800 text-zinc-500'
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {compareTipo === 'telhado_verde' && (
                  <p className="text-[9px] text-zinc-500">Usa {greenRoofPct}% telhados · {greenRoofRainMm} mm</p>
                )}
                {compareTipo === 'infraverde_calor' && (
                  <p className="text-[9px] text-zinc-500">Usa +{greenHeatArborPct}% vegetação · {greenHeatPeakC} °C</p>
                )}
              </div>
            )}
          </div>
        )}

        {loading && activeTab === 'rainfall' && (
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

        {!result && !loading && (
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

        {/* Action buttons */}
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
        {result && (
          <button
            onClick={handleGenerateMitigationPlan}
            disabled={planLoading}
            className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-3 py-2 text-xs font-extrabold text-emerald-200 transition-all hover:bg-emerald-500/25 disabled:opacity-60"
          >
            <FileText size={14} />
            {planLoading ? 'Gerando plano...' : 'Gerar Plano de Ação Sugerido'}
          </button>
        )}
        {result && (
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

      <SimulationResults
        result={result}
        mitigationPlan={mitigationPlan}
        simInterpret={simInterpret}
        slopeInterpret={slopeInterpret}
        analysisLoading={analysisLoading}
        interpretError={interpretError}
        copyOk={copyOk}
        exportLoading={exportLoading}
        rainfallComparison={rainfallComparison}
        heatLstComparison={heatLstComparison}
        lstCompareLoading={lstCompareLoading}
        activeTab={activeTab}
        rainfallMm={rainfallMm}
        compareRainfall={compareRainfall}
        baselineRainfallMm={baselineRainfallMm}
        floodTIndex={floodTIndex}
        floodPlaying={floodPlaying}
        floodLoop={floodLoop}
        floodSpeedMs={floodSpeedMs}
        calibBusy={calibBusy}
        calibMsg={calibMsg}
        codigoIbge={codigoIbge}
        overlayOptions={overlayOptions}
        onOverlayChange={onOverlayChange}
        mapMode3dActive={mapMode3dActive}
        onView3D={onView3D}
        onFocusWorkshop={onFocusWorkshop}
        onCrossRiskLayers={onCrossRiskLayers}
        setFloodPlaying={setFloodPlaying}
        setFloodTIndex={setFloodTIndex}
        setFloodSpeedMs={setFloodSpeedMs}
        setFloodLoop={setFloodLoop}
        setCalibBusy={setCalibBusy}
        setCalibMsg={setCalibMsg}
        applyFloodTimelineFrame={applyFloodTimelineFrame}
        runInterpret={runInterpret}
        handleExportGeojson={handleExportGeojson}
        handleExportKmz={handleExportKmz}
        handleExportPdf={handleExportPdf}
        handleIncludeInReport={handleIncludeInReport}
        handleCopyInterpret={handleCopyInterpret}
        simulationTipo={simulationTipo}
      />
    </div>
  );
}
