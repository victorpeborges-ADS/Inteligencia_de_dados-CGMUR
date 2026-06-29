'use client';

import { useCallback, useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { usePathname, useRouter } from 'next/navigation';
import { api, getApiBaseUrl, type MunicipalityComparison, type WorkshopDiagnostic } from '@/utils/api';
import ExecutiveDashboard from '@/components/Dashboard/ExecutiveDashboard';
import SimulationPanel from '@/components/Simulation/SimulationPanel';
import AssistantPanel from '@/components/Assistant/AssistantPanel';
import CaseStudiesPanel from '@/components/CaseStudies/CaseStudiesPanel';
import ContingencyWizard from '@/components/Contingency/ContingencyWizard';
import MonitoringPanel from '@/components/Monitoring/MonitoringPanel';
import OnboardingPanel from '@/components/Onboarding/OnboardingPanel';
import AuditPanel from '@/components/Audit/AuditPanel';
import SystemPanel from '@/components/System/SystemPanel';
import DataCatalogPanel from '@/components/DataCatalog/DataCatalogPanel';
import { AuthBar, useAuth } from '@/components/Auth/AuthProvider';
import { useAlertWebSocket } from '@/hooks/useAlertWebSocket';
import { SEED_MUNICIPALITIES } from '@/data/municipalities_seed';
import {
  DEFAULT_MAP_LAYERS,
  getGeoJsonCenter,
  isMunicipalityInDatabase,
  resolveMunicipalityCenter,
} from '@/utils/municipalitySync';
import {
  mergeMunicipalities,
  ROUTE_TO_TAB,
  TAB_ROUTES,
  type ActiveTab,
  type LayerQuality,
} from '@/config/platformTabs';
import { useAppStore } from '@/stores/useAppStore';

const MapContainer = dynamic(
  () => import('@/components/Map/MapContainer'),
  { ssr: false }
);

const Map3DMapLibreContainer = dynamic(
  () => import('@/components/Map/Map3DMapLibreContainer'),
  { ssr: false }
);

import { LayoutDashboard, Sliders, MessageSquare, BookOpen, Layers, MapPin, Eye, Sparkles, FileText, PlayCircle, Box, Shield, Radio, Building2, ClipboardList, Server, Database } from 'lucide-react';

type PlatformAppProps = {
  initialTab?: ActiveTab;
};

export default function PlatformApp({ initialTab }: PlatformAppProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { authEnabled, user, openLogin } = useAuth();

  const activeTab = useAppStore((s) => s.activeTab);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const activeLayers = useAppStore((s) => s.activeLayers);
  const setActiveLayers = useAppStore((s) => s.setActiveLayers);
  const toggleLayer = useAppStore((s) => s.toggleLayer);
  const resetMapLayers = useAppStore((s) => s.resetMapLayers);
  const mapFocus = useAppStore((s) => s.mapFocus);
  const setMapFocus = useAppStore((s) => s.setMapFocus);
  const zoom = useAppStore((s) => s.zoom);
  const setZoom = useAppStore((s) => s.setZoom);
  const municipalities = useAppStore((s) => s.municipalities);
  const setMunicipalities = useAppStore((s) => s.setMunicipalities);
  const selectedMunicipio = useAppStore((s) => s.selectedMunicipio);
  const setSelectedMunicipio = useAppStore((s) => s.setSelectedMunicipio);
  const apiOnline = useAppStore((s) => s.apiOnline);
  const setApiOnline = useAppStore((s) => s.setApiOnline);
  const alertNivel = useAppStore((s) => s.alertNivel);
  const setAlertNivel = useAppStore((s) => s.setAlertNivel);
  const municipioEnsuring = useAppStore((s) => s.municipioEnsuring);
  const setMunicipioEnsuring = useAppStore((s) => s.setMunicipioEnsuring);
  const municipioEnsureError = useAppStore((s) => s.municipioEnsureError);
  const setMunicipioEnsureError = useAppStore((s) => s.setMunicipioEnsureError);
  const layerOptions = useAppStore((s) => s.layerOptions);
  const setLayerOptions = useAppStore((s) => s.setLayerOptions);

  const [simGeoJSON, setSimGeoJSON] = useState<any>(null);
  const [simContours, setSimContours] = useState<any>(null);
  const [simFlowPaths, setSimFlowPaths] = useState<any>(null);
  const [diagnostic, setDiagnostic] = useState<WorkshopDiagnostic | null>(null);
  const [diagnosticLoading, setDiagnosticLoading] = useState(false);
  const [storyStep, setStoryStep] = useState<string | null>(null);
  const [comparison, setComparison] = useState<MunicipalityComparison | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [mapMode, setMapMode] = useState<'2d' | '3d'>('2d');
  const [alertToast, setAlertToast] = useState<{ title: string; message: string } | null>(null);
  const [contingencyNivel, setContingencyNivel] = useState<string>('AMARELO');

  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab, setActiveTab]);

  useEffect(() => {
    const tabFromRoute = ROUTE_TO_TAB[pathname];
    if (tabFromRoute) {
      setActiveTab(tabFromRoute);
    }
  }, [pathname, setActiveTab]);

  const navigateTab = useCallback(
    (tab: ActiveTab) => {
      setActiveTab(tab);
      const target = TAB_ROUTES[tab];
      if (pathname !== target) {
        router.push(target);
      }
    },
    [pathname, router, setActiveTab],
  );

  useEffect(() => {
    resolveMunicipalityCenter(selectedMunicipio).then(setMapFocus).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const load = async () => {
      let rootOk = false;
      let seeds = null as Awaited<ReturnType<typeof api.getSeedMunicipalities>> | null;
      let loaded = null as Awaited<ReturnType<typeof api.getMunicipalities>> | null;

      try {
        const rootRes = await fetch(`${getApiBaseUrl()}/health/live`);
        rootOk = rootRes.ok;
      } catch {
        rootOk = false;
      }

      try {
        seeds = await api.getSeedMunicipalities();
      } catch {
        seeds = null;
      }

      try {
        loaded = await api.getMunicipalities();
      } catch {
        loaded = null;
      }

      setApiOnline(rootOk);
      const seedRows = seeds?.length ? seeds : SEED_MUNICIPALITIES;
      setMunicipalities(mergeMunicipalities(seedRows, loaded));
    };

    load().catch((err) => {
      console.error('Erro ao carregar municipios:', err);
      setApiOnline(false);
      setMunicipalities(SEED_MUNICIPALITIES);
    });
  }, [setApiOnline, setMunicipalities]);

  const selectedMunicipioInfo = municipalities.find((item) => item.codigo_ibge === selectedMunicipio);

  const handleMunicipioChange = useCallback(async (codigoIbge: string) => {
    if (codigoIbge === selectedMunicipio && !municipioEnsureError) return;

    setMunicipioEnsuring(true);
    setMunicipioEnsureError(null);
    setSelectedMunicipio(codigoIbge);
    setDiagnostic(null);
    setStoryStep(null);
    setSimGeoJSON(null);
    setSimContours(null);
    setSimFlowPaths(null);
    setComparison(null);
    setActiveLayers([...DEFAULT_MAP_LAYERS]);

    try {
      let inDb = await isMunicipalityInDatabase(codigoIbge);
      if (!inDb) {
        const ensured = await api.ensureMunicipality(codigoIbge);
        inDb = ensured.loaded;
        setMunicipalities((prev) =>
          prev.map((m) =>
            m.codigo_ibge === codigoIbge
              ? { ...m, nome: ensured.nome, uf: ensured.uf, loaded: true }
              : m,
          ),
        );
      } else {
        setMunicipalities((prev) =>
          prev.map((m) =>
            m.codigo_ibge === codigoIbge ? { ...m, loaded: true } : m,
          ),
        );
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Falha ao integrar município';
      setMunicipioEnsureError(msg);
      setMunicipalities((prev) =>
        prev.map((m) =>
          m.codigo_ibge === codigoIbge ? { ...m, loaded: false } : m,
        ),
      );
    } finally {
      setMunicipioEnsuring(false);
    }

    const center = await resolveMunicipalityCenter(codigoIbge);
    setMapFocus(center);
    setZoom(12);
  }, [selectedMunicipio, municipioEnsureError]);

  const handleSimulate = (payload: any) => {
    const geojson = payload?.geometry ?? payload;
    setSimGeoJSON(geojson);
    setSimContours(payload?.contours ?? null);
    setSimFlowPaths(payload?.flow_paths ?? null);

    if (geojson?.features?.length > 0) {
        setMapFocus(getGeoJsonCenter(geojson) || mapFocus);
      setZoom(13);
    }
  };

  const handleClearSimulation = async () => {
    setSimGeoJSON(null);
    setSimContours(null);
    setSimFlowPaths(null);
    const center = await resolveMunicipalityCenter(selectedMunicipio);
    setMapFocus(center);
    setZoom(12);
  };

  const handleAssistantLayerToggle = (layerName: string) => {
    setActiveLayers((prev) => (
      prev.includes(layerName) ? prev : [...prev, layerName]
    ));
  };

  const handleAssistantFocusMap = (coords: [number, number], customZoom: number) => {
    setMapFocus(coords);
    setZoom(customZoom);
  };

  const loadDiagnostic = async () => {
    setDiagnosticLoading(true);
    try {
      const data = await api.getWorkshopDiagnostic(selectedMunicipio);
      setDiagnostic(data);
      setActiveLayers(data.recommended_layers);
      if (data.critical_areas[0]) {
        setMapFocus(data.critical_areas[0].coordinates);
        setZoom(13);
      }
      return data;
    } finally {
      setDiagnosticLoading(false);
    }
  };

  const startGuidedStory = async () => {
    const data = diagnostic || await loadDiagnostic();
    setSimGeoJSON(null);
    for (const step of data.narrative_steps) {
      setStoryStep(`${step.title}: ${step.description}`);
      setActiveLayers(step.layers);
      setMapFocus(step.focus);
      setZoom(step.zoom);
      await new Promise((resolve) => setTimeout(resolve, 3200));
    }
    setStoryStep('Narrativa concluída: áreas prioritárias e carteira de ação integradas no Sinidu+Clima.');
    setTimeout(() => setStoryStep(null), 5000);
  };

  const exportDiagnosticReport = async () => {
    const data = diagnostic || await loadDiagnostic();
    const rows = data.ranking.slice(0, 8).map((item, idx) => `
      <tr>
        <td>${idx + 1}</td>
        <td>${item.bairro}</td>
        <td>${item.score_sinidu}</td>
        <td>${item.indice_vulnerabilidade.toFixed(2)}</td>
        <td>${item.indice_risco_inundacao.toFixed(2)}</td>
        <td>${item.acao_recomendada}</td>
      </tr>
    `).join('');
    const opportunities = data.opportunities.map((item) => `<li>${item}</li>`).join('');
    const report = `
      <!doctype html>
      <html lang="pt-BR">
        <head>
          <meta charset="utf-8" />
          <title>Relatório Sinidu+Clima - ${data.municipio.nome}</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 40px; color: #111827; }
            h1 { color: #1e3a8a; }
            h2 { margin-top: 28px; color: #334155; }
            table { border-collapse: collapse; width: 100%; margin-top: 12px; }
            th, td { border: 1px solid #cbd5e1; padding: 8px; font-size: 13px; text-align: left; }
            th { background: #e0e7ff; }
            .card { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 12px; padding: 16px; }
          </style>
        </head>
        <body>
          <h1>Relatório Executivo Sinidu+Clima</h1>
          <div class="card">
            <strong>${data.municipio.nome} - ${data.municipio.uf}</strong><br />
            IBGE: ${data.municipio.codigo_ibge}<br />
            População: ${data.municipio.populacao.toLocaleString('pt-BR')} habitantes<br />
            Área: ${data.municipio.area_km2.toLocaleString('pt-BR')} km²
          </div>
          <h2>Diagnóstico</h2>
          <p>${data.headline}</p>
          <p><strong>Fórmula:</strong> ${data.score_formula}</p>
          <h2>Ranking de Prioridade Territorial</h2>
          <table>
            <thead>
              <tr><th>#</th><th>Bairro</th><th>Score</th><th>IVC</th><th>IRI</th><th>Ação recomendada</th></tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
          <h2>Oportunidades para a oficina</h2>
          <ul>${opportunities}</ul>
          <script>window.print();</script>
        </body>
      </html>
    `;
    const win = window.open('', '_blank');
    win?.document.write(report);
    win?.document.close();
  };

  const formatCompact = (value: number) => {
    if (value >= 1_000_000_000) return `R$ ${(value / 1_000_000_000).toFixed(1)} bi`;
    if (value >= 1_000_000) return `R$ ${(value / 1_000_000).toFixed(1)} mi`;
    if (value >= 1_000) return `R$ ${(value / 1_000).toFixed(1)} mil`;
    return `R$ ${value.toFixed(0)}`;
  };

  const runComparison = async () => {
    setComparisonLoading(true);
    try {
      const comparisonCodes = Array.from(new Set([
        selectedMunicipio,
        ...municipalities.map((item) => item.codigo_ibge).filter((code) => code !== selectedMunicipio).slice(0, 2)
      ]));
      const data = await api.compareMunicipalities(comparisonCodes);
      setComparison(data);
    } finally {
      setComparisonLoading(false);
    }
  };

  useEffect(() => {
    api.getMonitoringDashboard(selectedMunicipio)
      .then((d) => setAlertNivel(d.nivel_risco_atual))
      .catch(() => {});
  }, [selectedMunicipio]);

  useEffect(() => {
    api.getLayersMeta(selectedMunicipio)
      .then((meta) => {
        const saneamento = meta.layers?.saneamento_drenagem;
        if (!saneamento) return;
        setLayerOptions((prev) =>
          prev.map((layer) =>
            layer.id === 'saneamento_drenagem'
              ? {
                  ...layer,
                  source: saneamento.source,
                  quality: saneamento.quality as LayerQuality,
                }
              : layer,
          ),
        );
      })
      .catch(() => {});
  }, [selectedMunicipio]);

  useAlertWebSocket(selectedMunicipio, (event) => {
    const d = event.data as { titulo?: string; mensagem?: string; nivel?: string };
    if (d.nivel) setAlertNivel(String(d.nivel));
    setAlertToast({
      title: d.titulo || event.type,
      message: String(d.mensagem || 'Novo evento de monitoramento'),
    });
    window.setTimeout(() => setAlertToast(null), 8000);
  });

  const isAdmin = !authEnabled || user?.role === 'admin';
  const isGestorOrAdmin = !authEnabled || user?.role === 'admin' || user?.role === 'gestor_municipal';

  const tabConfig: { id: ActiveTab; label: string; Icon: typeof LayoutDashboard }[] = [
    { id: 'dashboard', label: 'Painel', Icon: LayoutDashboard },
    { id: 'onboarding', label: 'Municípios', Icon: Building2 },
    { id: 'catalog', label: 'Catálogo', Icon: Database },
    { id: 'simulation', label: 'Simulações', Icon: Sliders },
    { id: 'monitoring', label: 'Monitor', Icon: Radio },
    { id: 'contingency', label: 'Contingência', Icon: Shield },
    { id: 'assistant', label: 'Assistente', Icon: MessageSquare },
    { id: 'cases', label: 'Casos', Icon: BookOpen },
    ...(isAdmin ? [
      { id: 'audit' as const, label: 'Auditoria', Icon: ClipboardList },
      { id: 'system' as const, label: 'Sistema', Icon: Server },
    ] : []),
  ];

  const layerGroups = Array.from(new Set(layerOptions.map((opt) => opt.group)));

  return (
    <main className="min-h-screen bg-background text-zinc-100 flex flex-col font-sans select-none">
      {/* Premium Header */}
      <header className="h-22 min-h-[88px] shrink-0 border-b border-border bg-card/65 backdrop-blur-md px-6 flex items-center justify-between z-50">
        <div className="flex items-center gap-4">
          <img
            src="/logo-sinidu-clima.png"
            alt="Logo Sinidu+Clima"
            className="h-[72px] w-[72px] rounded-2xl border border-zinc-800 bg-black object-cover shadow-lg shadow-indigo-600/20"
          />
          <div>
            <h1 className="font-extrabold text-2xl tracking-tight bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
              Sinidu+Clima <span className="text-indigo-400 font-medium">INTERNO</span>
            </h1>
            <span className="text-[11px] text-zinc-500 uppercase tracking-[0.22em] font-semibold block">Plataforma de Inteligência Territorial</span>
          </div>
        </div>
        
        {/* Pilot Info Badge */}
        <div className="flex items-center gap-3">
          <AuthBar />
          <select
            value={selectedMunicipio}
            onChange={(e) => handleMunicipioChange(e.target.value)}
            className="max-w-[280px] rounded-full border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-xs font-semibold text-zinc-200 outline-none focus:border-indigo-400"
            title="Município analisado — atualiza mapa, painéis, monitor e relatórios"
          >
            {municipalities.map((m) => (
              <option key={m.codigo_ibge} value={m.codigo_ibge}>
                {m.loaded === false ? '○ ' : ''}{m.nome} - {m.uf} ({m.codigo_ibge})
              </option>
            ))}
          </select>
          {(alertNivel === 'LARANJA' || alertNivel === 'VERMELHO') && (
            <div className="flex items-center gap-2 rounded-full border border-rose-500/60 bg-rose-950/40 px-3 py-1.5 text-xs font-semibold text-rose-200 animate-pulse">
              <MapPin size={12} className="text-rose-400" />
              Alerta {alertNivel}
            </div>
          )}
        </div>
      </header>

      {municipioEnsuring && (
        <div className="border-b border-indigo-500/40 bg-indigo-950/40 px-6 py-2 text-center text-xs text-indigo-100">
          Integrando dados territoriais de <strong>{selectedMunicipioInfo?.nome || selectedMunicipio}</strong>… geometria IBGE, bairros, indicadores e integrações públicas.
        </div>
      )}

      {municipioEnsureError && (
        <div className="border-b border-rose-500/40 bg-rose-950/40 px-6 py-2 text-center text-xs text-rose-100">
          {municipioEnsureError} — tente novamente ou use a aba <strong>Municípios</strong> para onboarding completo.
        </div>
      )}

      {alertToast && (
        <div className="border-b border-amber-500/40 bg-amber-950/50 px-6 py-2 text-xs text-amber-100">
          <strong>{alertToast.title}</strong> — {alertToast.message}
        </div>
      )}

      {apiOnline === false && (
        <div className="flex flex-wrap items-center justify-center gap-3 border-b border-rose-500/40 bg-rose-950/40 px-6 py-2 text-center text-xs text-rose-100">
          <span>
            Backend offline — verifique a API em <strong>{getApiBaseUrl()}</strong>.
            {authEnabled ? ' Faça login para carregar KPIs e mapa quando a API voltar.' : ''}
            {' '}O seletor lista os 61 municípios prioritários mesmo sem API.
          </span>
          {authEnabled && (
            <button
              type="button"
              onClick={openLogin}
              className="shrink-0 rounded-lg border border-cyan-700 bg-cyan-950/60 px-3 py-1 font-semibold text-cyan-200 hover:bg-cyan-900/50"
            >
              Entrar
            </button>
          )}
        </div>
      )}

      {/* Workspace Area */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Sidepanel (Glassmorphism, 40% width) */}
        <section className="w-[450px] border-r border-border bg-card/15 backdrop-blur-md flex flex-col overflow-hidden shrink-0 z-40">
          
          {/* Tab Navigation */}
          <div className="flex flex-wrap border-b border-border bg-zinc-950/60 p-2 gap-1 shrink-0">
            {tabConfig.map(({ id, label, Icon }) => (
                <button
                  key={id}
                  onClick={() => navigateTab(id)}
                  className={`flex min-w-[72px] flex-1 flex-col items-center gap-1 py-2 px-1 rounded-lg text-[8px] font-bold uppercase tracking-wider transition-all duration-200 ${
                    activeTab === id
                      ? 'bg-zinc-900 border border-zinc-800 text-indigo-400'
                      : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  <Icon size={16} />
                  <span>{label}</span>
                </button>
            ))}
          </div>

          {/* Active Tab Panel Content */}
          <div className="flex-1 p-5 overflow-hidden">
            {activeTab === 'dashboard' && (
              <ExecutiveDashboard
                key={`${selectedMunicipio}-${selectedMunicipioInfo?.loaded}`}
                codigoIbge={selectedMunicipio}
                municipioLoaded={selectedMunicipioInfo?.loaded === true}
                municipioEnsuring={municipioEnsuring}
                municipioNome={selectedMunicipioInfo?.nome}
              />
            )}
            {activeTab === 'onboarding' && (
              <OnboardingPanel
                selectedCodigoIbge={selectedMunicipio}
                onSelectMunicipio={handleMunicipioChange}
                onMunicipioOnboarded={async (codigoIbge) => {
                  await handleMunicipioChange(codigoIbge);
                  try {
                    const loaded = await api.getMunicipalities();
                    setMunicipalities((prev) => {
                      const byCode = new Map(prev.map((m) => [m.codigo_ibge, m]));
                      loaded.forEach((m) => {
                        byCode.set(m.codigo_ibge, {
                          codigo_ibge: m.codigo_ibge,
                          nome: m.nome,
                          uf: m.uf,
                          loaded: true,
                        });
                      });
                      return Array.from(byCode.values()).sort((a, b) =>
                        a.nome.localeCompare(b.nome, 'pt-BR'),
                      );
                    });
                  } catch {
                    /* lista local permanece */
                  }
                }}
              />
            )}
            {activeTab === 'catalog' && (
              <DataCatalogPanel codigoIbge={selectedMunicipio} isGestorOrAdmin={isGestorOrAdmin} />
            )}
            {activeTab === 'simulation' && (
              <SimulationPanel
                key={selectedMunicipio}
                onSimulate={handleSimulate}
                onClear={handleClearSimulation}
                codigoIbge={selectedMunicipio}
                municipioNome={selectedMunicipioInfo?.nome}
                municipioLoaded={selectedMunicipioInfo?.loaded === true}
              />
            )}
            {activeTab === 'assistant' && (
              <AssistantPanel
                key={selectedMunicipio}
                codigoIbge={selectedMunicipio}
                onToggleLayer={handleAssistantLayerToggle}
                onFocusMap={handleAssistantFocusMap}
              />
            )}
            {activeTab === 'cases' && <CaseStudiesPanel municipioNome={selectedMunicipioInfo?.nome} />}
            {activeTab === 'monitoring' && (
              <MonitoringPanel
                key={selectedMunicipio}
                codigoIbge={selectedMunicipio}
                municipioNome={selectedMunicipioInfo?.nome}
                onToast={(title, message) => {
                  setAlertToast({ title, message });
                  window.setTimeout(() => setAlertToast(null), 8000);
                }}
                onActivateContingency={(nivel) => {
                  setContingencyNivel(nivel);
                  navigateTab('contingency');
                }}
              />
            )}
            {activeTab === 'contingency' && (
              <ContingencyWizard
                key={`${selectedMunicipio}-${contingencyNivel}`}
                codigoIbge={selectedMunicipio}
                municipioNome={selectedMunicipioInfo?.nome}
                municipioUf={selectedMunicipioInfo?.uf}
                mapFocus={mapFocus}
                simGeoJSON={simGeoJSON}
                initialNivel={contingencyNivel}
              />
            )}
            {activeTab === 'audit' && isAdmin && <AuditPanel />}
            {activeTab === 'system' && isAdmin && <SystemPanel />}
          </div>
        </section>

        {/* Right Mapping View (60% width) */}
        <section className="flex-1 relative bg-zinc-950 overflow-hidden">
          {/* Workshop Impact Panel */}
          <div className="absolute top-4 left-[18rem] right-80 z-[998] rounded-xl border border-indigo-500/30 bg-zinc-950/90 p-3 shadow-2xl backdrop-blur-md">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wider text-indigo-300">
                  <Sparkles size={13} /> Central da Oficina Sinidu+Clima
                </p>
                <p className="mt-1 text-xs text-zinc-300">
                  {diagnostic?.headline || 'Gere um diagnóstico automático, apresente a narrativa guiada e exporte relatório executivo.'}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  onClick={loadDiagnostic}
                  disabled={diagnosticLoading}
                  className="rounded-lg border border-indigo-500/40 bg-indigo-500/15 px-3 py-2 text-[10px] font-bold uppercase text-indigo-200 hover:bg-indigo-500/25 disabled:opacity-60"
                >
                  {diagnosticLoading ? 'Gerando...' : 'Diagnóstico'}
                </button>
                <button
                  onClick={startGuidedStory}
                  className="flex items-center gap-1 rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-3 py-2 text-[10px] font-bold uppercase text-emerald-200 hover:bg-emerald-500/25"
                >
                  <PlayCircle size={12} /> Apresentar
                </button>
                <button
                  onClick={exportDiagnosticReport}
                  className="flex items-center gap-1 rounded-lg border border-zinc-600 bg-zinc-900 px-3 py-2 text-[10px] font-bold uppercase text-zinc-200 hover:bg-zinc-800"
                >
                  <FileText size={12} /> Relatório
                </button>
                <button
                  onClick={runComparison}
                  disabled={comparisonLoading}
                  className="rounded-lg border border-sky-500/40 bg-sky-500/15 px-3 py-2 text-[10px] font-bold uppercase text-sky-200 hover:bg-sky-500/25 disabled:opacity-60"
                >
                  {comparisonLoading ? 'Comparando...' : 'Comparar'}
                </button>
              </div>
            </div>

            {storyStep && (
              <div className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-950/40 px-3 py-2 text-xs text-emerald-100">
                {storyStep}
              </div>
            )}

            {diagnostic && (
              <div className="mt-3 grid grid-cols-3 gap-2">
                {diagnostic.critical_areas.map((item, idx) => (
                  <button
                    key={item.bairro}
                    onClick={() => {
                      setMapFocus(item.coordinates);
                      setZoom(14);
                      setActiveLayers(['bairros', 'prioridade_planejamento', 'vulnerabilidade', 'inundacao']);
                    }}
                    className="rounded-lg border border-zinc-700 bg-zinc-900/80 p-2 text-left hover:border-indigo-400/60"
                  >
                    <span className="text-[9px] font-bold uppercase text-zinc-500">Prioridade {idx + 1}</span>
                    <div className="mt-1 flex items-center justify-between">
                      <strong className="text-xs text-zinc-100">{item.bairro}</strong>
                      <span className="rounded-full bg-rose-500/20 px-2 py-0.5 text-[10px] font-extrabold text-rose-200">{item.score_sinidu}</span>
                    </div>
                    {item.score_componentes && (
                      <div className="mt-1 grid grid-cols-3 gap-1 text-[8px] text-zinc-400">
                        <span>IVC {item.score_componentes.vulnerabilidade_pct}</span>
                        <span>IRI {item.score_componentes.inundacao_pct}</span>
                        <span>ADP {item.score_componentes.deficit_adaptacao_pct}</span>
                      </div>
                    )}
                    <p className="mt-1 line-clamp-2 text-[10px] leading-snug text-zinc-400">{item.acao_recomendada}</p>
                  </button>
                ))}
              </div>
            )}

            {comparison && (
              <div className="mt-3 rounded-lg border border-sky-500/20 bg-sky-950/20 p-2">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-sky-200">Comparação municipal</span>
                  <span className="text-[9px] text-zinc-500">Oficial + Estimado + Derivado</span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {comparison.municipios.map((row) => (
                    <button
                      key={row.codigo_ibge}
                      onClick={() => handleMunicipioChange(row.codigo_ibge)}
                      className="rounded-lg border border-zinc-700 bg-zinc-900/80 p-2 text-left hover:border-sky-400/60"
                    >
                      <div className="flex items-center justify-between">
                        <strong className="text-xs text-zinc-100">{row.nome}</strong>
                        <span className="rounded-full bg-sky-500/20 px-2 py-0.5 text-[10px] font-extrabold text-sky-200">{row.score_sinidu}</span>
                      </div>
                      <p className="mt-1 text-[9px] text-zinc-400">Renda: R$ {row.renda_media_setores.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</p>
                      <p className="text-[9px] text-zinc-400">Verde: {row.cobertura_vegetal_percent}% | IVC: {row.media_ivc}</p>
                      <p className="text-[9px] text-zinc-400">Danos: {formatCompact(row.danos_materiais_total)}</p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          {/* Layer Selector Overlay Widget */}
          <div className="absolute top-4 left-4 z-[999] bg-card/85 backdrop-blur-md border border-border p-3 rounded-xl shadow-2xl flex flex-col gap-2 w-64">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5 mb-1.5">
              <span className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider flex items-center gap-1.5">
                <Layers size={12} className="text-indigo-400" /> Camadas Espaciais
              </span>
              <span className="text-[9px] text-zinc-500 italic">{activeLayers.length} ativa(s)</span>
            </div>

            <div className="grid grid-cols-2 gap-1.5">
              <button
                onClick={() => setActiveLayers(['bairros', 'vulnerabilidade', 'inundacao'])}
                className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-2 py-1 text-[10px] font-bold text-indigo-300 hover:bg-indigo-500/20"
              >
                Cruzar riscos
              </button>
              <button
                onClick={() => setActiveLayers([])}
                className="rounded-lg border border-zinc-700 bg-zinc-950/70 px-2 py-1 text-[10px] font-bold text-zinc-400 hover:text-zinc-100"
              >
                Limpar
              </button>
            </div>
            
            <div className="flex max-h-[62vh] flex-col gap-3 overflow-y-auto pr-1">
              {layerGroups.map((group) => (
                <div key={group} className="flex flex-col gap-1">
                  <span className="px-1 text-[9px] font-extrabold uppercase tracking-wider text-zinc-500">{group}</span>
                  {layerOptions.filter((opt) => opt.group === group).map((opt) => {
                    const isActive = activeLayers.includes(opt.id);
                    return (
                      <button
                        key={opt.id}
                        onClick={() => toggleLayer(opt.id)}
                        className={`w-full text-left py-1.5 px-2.5 rounded-lg text-xs transition-all flex items-center justify-between border ${
                          isActive
                            ? 'bg-zinc-900 border-indigo-500/40 text-indigo-300 font-bold' 
                            : 'border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/40'
                        }`}
                      >
                        <span className="flex min-w-0 flex-1 flex-col gap-1 pr-2">
                          <span className="truncate">{opt.label}</span>
                          <span className={`w-fit rounded-md border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide ${
                            isActive
                              ? 'border-indigo-400/40 bg-indigo-500/15 text-indigo-200'
                              : 'border-zinc-700 bg-zinc-950/70 text-zinc-500'
                          }`}>
                            Origem: {opt.source}
                          </span>
                          <span className={`w-fit rounded-md border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide ${
                            opt.quality === 'Oficial'
                              ? 'border-emerald-400/40 bg-emerald-500/10 text-emerald-300'
                              : opt.quality === 'Estimado'
                                ? 'border-amber-400/40 bg-amber-500/10 text-amber-300'
                                : 'border-sky-400/40 bg-sky-500/10 text-sky-300'
                          }`}>
                            {opt.quality}
                          </span>
                        </span>
                        <span className={`h-4 w-4 rounded border flex items-center justify-center ${
                          isActive ? 'border-indigo-400 bg-indigo-500/20 text-indigo-200' : 'border-zinc-700'
                        }`}>
                          {isActive && <Eye size={11} />}
                        </span>
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>

          {/* Toggle 2D / 3D */}
          <div className="absolute right-4 top-4 z-[1200] flex gap-2 rounded-xl border border-zinc-800 bg-zinc-950/95 p-1 shadow-lg backdrop-blur-md">
            <button
              type="button"
              onClick={() => setMapMode('2d')}
              className={`rounded-lg border px-3 py-2 text-[10px] font-bold uppercase tracking-wider ${
                mapMode === '2d'
                  ? 'border-indigo-400/50 bg-indigo-500/20 text-indigo-200'
                  : 'border-zinc-700 bg-zinc-950/90 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              Mapa 2D
            </button>
            <button
              type="button"
              onClick={() => setMapMode('3d')}
              className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-[10px] font-bold uppercase tracking-wider ${
                mapMode === '3d'
                  ? 'border-teal-400/50 bg-teal-500/20 text-teal-200'
                  : 'border-zinc-700 bg-zinc-950/90 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Box size={12} />
              Terreno 3D
            </button>
          </div>

          {mapMode === '2d' ? (
          <MapContainer 
            activeLayers={activeLayers}
            mapFocus={mapFocus} 
            zoom={zoom} 
            simGeoJSON={simGeoJSON}
            simContours={simContours}
            simFlowPaths={simFlowPaths}
            selectedMunicipio={selectedMunicipio}
          />
          ) : (
          <Map3DMapLibreContainer
            activeLayers={activeLayers}
            simGeoJSON={simGeoJSON}
            simContours={simContours}
            simFlowPaths={simFlowPaths}
            selectedMunicipio={selectedMunicipio}
            mapFocus={mapFocus}
          />
          )}
        </section>
      </div>
    </main>
  );
}
