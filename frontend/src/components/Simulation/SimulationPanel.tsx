'use client';

import { useState } from 'react';
import { api, MitigationPlan, SimulationAnalysis, SimulationOutput } from '@/utils/api';
import { Play, RotateCcw, AlertTriangle, HelpCircle, Thermometer, Droplet, FileText, Waves, Layers, Mountain, Activity, Brain, Sparkles } from 'lucide-react';
import PredictiveAnalysis from './PredictiveAnalysis';

interface SimulationProps {
  onSimulate: (payload: SimulationOutput | any) => void;
  onClear: () => void;
  codigoIbge?: string;
  municipioNome?: string;
  municipioLoaded?: boolean;
}

export default function SimulationPanel({ onSimulate, onClear, codigoIbge, municipioNome, municipioLoaded }: SimulationProps) {
  const [activeTab, setActiveTab] = useState<'waterproofing' | 'veg_loss' | 'rainfall' | 'drainage' | 'predictive'>('rainfall');
  const [waterproofingPct, setWaterproofingPct] = useState(25);
  const [vegLossPct, setVegLossPct] = useState(40);
  const [rainfallMm, setRainfallMm] = useState(120);
  const [drainageDeficitPct, setDrainageDeficitPct] = useState(45);
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulationOutput | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [contingencyLoading, setContingencyLoading] = useState(false);
  const [mitigationPlan, setMitigationPlan] = useState<MitigationPlan | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState<SimulationAnalysis | null>(null);

  const runAiAnalysis = async (data: SimulationOutput) => {
    setAnalysisLoading(true);
    try {
      const analysis = await api.analyzeSimulation(data, codigoIbge);
      setAiAnalysis(analysis);
    } catch (err) {
      console.error('Error running AI analysis:', err);
      setAiAnalysis(null);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleSimulate = async () => {
    setLoading(true);
    setMitigationPlan(null);
    setAiAnalysis(null);
    try {
      let data: SimulationOutput;
      if (activeTab === 'waterproofing') {
        data = await api.simulateWaterproofing(waterproofingPct, codigoIbge);
      } else if (activeTab === 'veg_loss') {
        data = await api.simulateVegetationLoss(vegLossPct, codigoIbge);
      } else if (activeTab === 'drainage') {
        data = await api.simulateDrainageDeficit(drainageDeficitPct, codigoIbge);
      } else {
        data = await api.simulateExtremeRainfall(rainfallMm, codigoIbge);
      }
      setResult(data);
      onSimulate(data);
      void runAiAnalysis(data);
    } catch (err) {
      console.error('Error running simulation:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setMitigationPlan(null);
    setAiAnalysis(null);
    onClear();
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
        activeTab === 'drainage' || activeTab === 'rainfall' ? 'INUNDACAO' : activeTab === 'veg_loss' ? 'DESLIZAMENTO' : 'MULTIPLO';
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
    <div className="flex flex-col gap-5 p-1 overflow-y-auto max-h-[85vh]">
      {/* Simulation Selector tabs */}
      <div className="grid grid-cols-5 gap-1 bg-zinc-950 p-1 rounded-lg border border-border">
        {(['rainfall', 'predictive', 'waterproofing', 'veg_loss', 'drainage'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setResult(null); setMitigationPlan(null); setAiAnalysis(null); if (tab !== 'predictive') onClear(); }}
            className={`py-1.5 px-1 rounded text-[9px] font-bold uppercase tracking-wider transition-all ${
              activeTab === tab 
                ? 'bg-card text-indigo-400 border border-zinc-800' 
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {tab === 'rainfall' ? 'Chuva' : tab === 'predictive' ? 'Preditiva' : tab === 'waterproofing' ? 'Asfalto' : tab === 'veg_loss' ? 'Vegetação' : 'Drenagem'}
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
                    DEM SRTM · Curvas de nível · Manchas por profundidade
                  </p>
                </div>
                <span className="shrink-0 rounded-md border border-sky-500/30 bg-sky-500/10 px-2 py-1 text-[9px] font-bold text-sky-200">
                  v2.0
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
                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-sky-500"
              />
              <div className="flex justify-between text-[8px] text-zinc-600 font-mono">
                <span>40 mm</span>
                <span>150 mm (Q100 ref.)</span>
                <span>250 mm</span>
              </div>
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
                O motor cruza precipitação, raster SRTM 30 m, corpos d&apos;água MapBiomas, índice IRI
                (modula profundidade por bairro), IVC, histórico S2ID e alertas CEMADEN. Deslizamentos
                são derivados da declividade DEM (não mais bairros fixos). A cota de enchente simulada
                parte do percentil 20 de elevação municipal + incremento pluviométrico.
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

        {activeTab === 'veg_loss' && (
          <div className="flex flex-col gap-4">
            <div>
              <h4 className="font-extrabold text-sm text-zinc-200 flex items-center gap-1.5">
                <Thermometer size={16} className="text-accent-rose" /> Perda de Cobertura Vegetal
              </h4>
              <p className="text-[11px] text-zinc-400 mt-1">Redução de áreas florestadas e impacto no microclima.</p>
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex justify-between text-xs text-zinc-300">
                <span>Remoção da Cobertura Verde</span>
                <span className="font-bold text-accent-rose">-{vegLossPct}%</span>
              </div>
              <input
                type="range"
                min="10"
                max="100"
                step="5"
                value={vegLossPct}
                onChange={(e) => setVegLossPct(Number(e.target.value))}
                className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-rose-500"
              />
              <span className="text-[9px] text-zinc-500 italic">Calcula o efeito de ilha de calor decorrente de desmatamento local.</span>
            </div>
            <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-3">
              <h5 className="mb-2 flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wide text-rose-200">
                <HelpCircle size={13} /> Metodologia da vegetação
              </h5>
              <p className="text-[10px] leading-relaxed text-zinc-400">
                A simulação usa a cobertura vegetal e a área urbana para estimar a expansão de ilhas de calor quando há
                perda de cobertura vegetal. O percentual informado amplia a zona térmica e estima a população dentro da área afetada.
              </p>
              <p className="mt-2 text-[9px] italic leading-relaxed text-zinc-500">
                Resultado demonstrativo: serve para priorizar arborização, corredores verdes e proteção de remanescentes,
                não substitui inventário arbóreo ou medição microclimática de campo.
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
      {result && (
        <div className="bg-card/40 border border-border p-4 rounded-xl flex flex-col gap-4 animate-fadeIn">
          <div className="flex items-start justify-between gap-2">
            <div>
              <h4 className="font-extrabold text-zinc-200 text-xs uppercase tracking-wide">Resultados da Simulação</h4>
              {result.simulation_meta?.dem_available && (
                <p className="mt-0.5 text-[9px] text-lime-400/80 font-mono">
                  DEM: {result.simulation_meta.dem_source} · Δh max {result.simulation_meta.max_depth_m} m
                </p>
              )}
            </div>
            {result.simulation_meta?.method && (
              <span className="rounded border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[8px] font-bold uppercase text-indigo-200">
                {result.simulation_meta.method}
              </span>
            )}
          </div>
          <div className="h-px bg-zinc-800 w-full" />

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-zinc-950/60 p-2.5 rounded-lg border border-zinc-800">
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block">Área Afetada</span>
              <span className="text-sm font-extrabold text-zinc-200">{result.affected_area_km2} km²</span>
            </div>
            <div className="bg-zinc-950/60 p-2.5 rounded-lg border border-zinc-800">
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block">Impacto Estimado</span>
              <span className="text-sm font-extrabold text-accent-rose">
                {result.scenario_type === 'VegetationLoss' 
                  ? `+${result.impact_value}°C` 
                  : `${result.impact_value.toLocaleString()} hab`}
              </span>
            </div>
          </div>

          {result.simulation_meta?.dem_available && (
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg border border-lime-500/20 bg-lime-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Cota min</span>
                <span className="text-xs font-bold text-lime-300">{result.simulation_meta.altitude_min_m} m</span>
              </div>
              <div className="rounded-lg border border-lime-500/20 bg-lime-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Cota média</span>
                <span className="text-xs font-bold text-lime-300">{result.simulation_meta.altitude_media_m} m</span>
              </div>
              <div className="rounded-lg border border-lime-500/20 bg-lime-950/10 p-2 text-center">
                <span className="block text-[8px] uppercase text-zinc-500">Isolinhas</span>
                <span className="text-xs font-bold text-lime-300">{result.simulation_meta.contour_interval_m} m</span>
              </div>
            </div>
          )}

          {(result.contours?.features?.length > 0 || result.flow_paths?.features?.length > 0) && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2.5">
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-1.5">Camadas no mapa</span>
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
              {result.metric_impact}: {result.scenario_type === 'VegetationLoss' 
                ? `Elevação térmica superficial projetada em +${result.impact_value}°C nas áreas desprovidas de cobertura.` 
                : `Aproximadamente ${result.affected_population.toLocaleString()} cidadãos residem nos setores inundáveis afetados.`}
            </p>
          </div>

          {result.affected_bairros.length > 0 && (
            <div>
              <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-1">Bairros Atingidos</span>
              <div className="flex flex-wrap gap-1">
                {result.affected_bairros.map((b) => (
                  <span key={b} className="text-[9px] bg-zinc-950 border border-zinc-800 text-zinc-300 py-0.5 px-2 rounded-full font-medium">
                    {b}
                  </span>
                ))}
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

      {(analysisLoading || aiAnalysis) && (
        <div className="bg-card/40 border border-violet-500/25 p-4 rounded-xl flex flex-col gap-3 animate-fadeIn">
          <div className="flex items-center justify-between gap-2">
            <h4 className="font-extrabold text-zinc-200 text-xs uppercase tracking-wide flex items-center gap-1.5">
              <Brain size={14} className="text-violet-400" />
              Análise Interpretativa
            </h4>
            {aiAnalysis && (
              <span className={`rounded border px-2 py-0.5 text-[8px] font-bold uppercase ${
                aiAnalysis.ai_provider === 'deterministic'
                  ? 'border-zinc-600 text-zinc-400'
                  : 'border-violet-500/40 text-violet-200'
              }`}>
                {aiAnalysis.ai_provider === 'deterministic' ? 'Regras' : aiAnalysis.ai_provider}
                {aiAnalysis.confidence && ` · ${aiAnalysis.confidence}`}
              </span>
            )}
          </div>

          {analysisLoading && (
            <p className="text-[10px] text-zinc-500 flex items-center gap-1.5">
              <Sparkles size={12} className="animate-pulse text-violet-400" />
              Gerando interpretação territorial…
            </p>
          )}

          {aiAnalysis && !analysisLoading && (
            <>
              {aiAnalysis.key_findings.length > 0 && (
                <ul className="space-y-1">
                  {aiAnalysis.key_findings.map((item, idx) => (
                    <li key={idx} className="text-[10px] leading-relaxed text-zinc-300 flex gap-1.5">
                      <span className="text-violet-400 shrink-0">•</span>
                      {item}
                    </li>
                  ))}
                </ul>
              )}

              {aiAnalysis.bairros_prioritarios.length > 0 && (
                <div>
                  <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-1.5">
                    Bairros prioritários
                  </span>
                  <div className="flex flex-col gap-1">
                    {aiAnalysis.bairros_prioritarios.map((b) => (
                      <div key={b.nome} className="rounded border border-violet-500/20 bg-violet-950/10 px-2 py-1.5">
                        <div className="flex justify-between text-[10px]">
                          <strong className="text-violet-200">{b.nome}</strong>
                          {(b.ivc != null || b.iri != null) && (
                            <span className="font-mono text-[9px] text-zinc-400">
                              {b.ivc != null && `IVC ${b.ivc.toFixed(2)}`}
                              {b.ivc != null && b.iri != null && ' · '}
                              {b.iri != null && `IRI ${b.iri.toFixed(2)}`}
                            </span>
                          )}
                        </div>
                        {b.rationale && (
                          <p className="mt-0.5 text-[9px] text-zinc-500">{b.rationale}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {aiAnalysis.suggested_actions.length > 0 && (
                <div>
                  <span className="text-[9px] text-zinc-400 font-bold uppercase tracking-wider block mb-1.5">
                    Ações sugeridas
                  </span>
                  <ul className="space-y-1">
                    {aiAnalysis.suggested_actions.map((action, idx) => (
                      <li key={idx} className="text-[10px] text-emerald-200/90 flex gap-1.5">
                        <span className="text-emerald-500 shrink-0">→</span>
                        {action}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {aiAnalysis.data_gaps.length > 0 && (
                <div className="rounded border border-amber-500/20 bg-amber-950/10 p-2">
                  <span className="text-[9px] font-bold uppercase text-amber-300">Lacunas de dados</span>
                  <ul className="mt-1 space-y-0.5">
                    {aiAnalysis.data_gaps.map((gap, idx) => (
                      <li key={idx} className="text-[9px] text-amber-200/70">{gap}</li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="text-[8px] italic text-zinc-600">{aiAnalysis.disclaimer}</p>
            </>
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
