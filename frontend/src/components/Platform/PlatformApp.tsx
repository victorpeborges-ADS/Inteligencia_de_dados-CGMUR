'use client';

import { useCallback, useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { usePathname, useRouter } from 'next/navigation';
import { api, getApiBaseUrl, type SocioeconomicRanking, type WorkshopDiagnostic } from '@/utils/api';
import ExecutiveDashboard from '@/components/Dashboard/ExecutiveDashboard';
import SimulationPanel, { DEFAULT_SIM_OVERLAYS, type SimOverlayOptions } from '@/components/Simulation/SimulationPanel';
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
import { useAppStore, FOCUS_MODE_STORAGE_KEY } from '@/stores/useAppStore';
import AgenteSinidu from '@/components/AgenteSinidu';
import { useAgenteProativo } from '@/hooks/useAgenteContexto';
import WorkshopCenter from '@/components/Workshop/WorkshopCenter';
import MunicipioLoadProgress from '@/components/Platform/MunicipioLoadProgress';
import OnboardingBanner from '@/components/Onboarding/OnboardingBanner';
import TabContextHint from '@/components/Platform/TabContextHint';
import LayerPanel from '@/components/Map/LayerPanel';
import { LAYER_PRESETS } from '@/components/Map/LayerPanel';

const MapContainer = dynamic(
  () => import('@/components/Map/MapContainer'),
  { ssr: false }
);

const Map3DMapLibreContainer = dynamic(
  () => import('@/components/Map/Map3DMapLibreContainer'),
  { ssr: false }
);

import { LayoutDashboard, Sliders, MessageSquare, BookOpen, MapPin, Box, Shield, Radio, Building2, ClipboardList, Server, Database, Focus } from 'lucide-react';

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
  const focusMode = useAppStore((s) => s.focusMode);
  const setFocusMode = useAppStore((s) => s.setFocusMode);
  const toggleFocusMode = useAppStore((s) => s.toggleFocusMode);

  useAgenteProativo();

  useEffect(() => {
    try {
      if (localStorage.getItem(FOCUS_MODE_STORAGE_KEY) === 'true') {
        setFocusMode(true);
      }
    } catch {
      /* localStorage indisponível */
    }
  }, [setFocusMode]);

  useEffect(() => {
    try {
      localStorage.setItem(FOCUS_MODE_STORAGE_KEY, String(focusMode));
    } catch {
      /* localStorage indisponível */
    }
  }, [focusMode]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'f' && e.key !== 'F') return;
      const target = e.target;
      if (
        target instanceof HTMLInputElement
        || target instanceof HTMLTextAreaElement
        || target instanceof HTMLSelectElement
        || (target instanceof HTMLElement && target.isContentEditable)
      ) {
        return;
      }
      e.preventDefault();
      toggleFocusMode();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [toggleFocusMode]);

  const [simGeoJSON, setSimGeoJSON] = useState<any>(null);
  const [simContours, setSimContours] = useState<any>(null);
  const [simFlowPaths, setSimFlowPaths] = useState<any>(null);
  const [simOverlays, setSimOverlays] = useState<SimOverlayOptions>(DEFAULT_SIM_OVERLAYS);
  const [diagnostic, setDiagnostic] = useState<WorkshopDiagnostic | null>(null);
  const [socioRanking, setSocioRanking] = useState<SocioeconomicRanking | null>(null);
  const [mapMode, setMapMode] = useState<'2d' | '3d'>('2d');
  const [alertToast, setAlertToast] = useState<{ title: string; message: string } | null>(null);
  const [contingencyNivel, setContingencyNivel] = useState<string>('AMARELO');
  const [malhaIndisponivel, setMalhaIndisponivel] = useState(false);
  const [scoreConfiabilidade, setScoreConfiabilidade] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [municipioLoadStep, setMunicipioLoadStep] = useState(0);
  const requestReport = useAppStore((s) => s.requestReport);

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
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

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

      if (cancelled) return;

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

      if (cancelled) return;

      setApiOnline(rootOk);
      const seedRows = seeds?.length ? seeds : SEED_MUNICIPALITIES;
      setMunicipalities(mergeMunicipalities(seedRows, loaded));

      if (!rootOk && !cancelled) {
        retryTimer = setTimeout(() => {
          load().catch(() => {});
        }, 4000);
      }
    };

    load().catch((err) => {
      console.error('Erro ao carregar municipios:', err);
      if (!cancelled) {
        setApiOnline(false);
        setMunicipalities(SEED_MUNICIPALITIES);
        retryTimer = setTimeout(() => {
          load().catch(() => {});
        }, 4000);
      }
    });

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [setApiOnline, setMunicipalities]);

  const selectedMunicipioInfo = municipalities.find((item) => item.codigo_ibge === selectedMunicipio);

  const handleMunicipioChange = useCallback(async (codigoIbge: string) => {
    if (codigoIbge === selectedMunicipio && !municipioEnsureError) return;

    setMunicipioEnsuring(true);
    setMunicipioEnsureError(null);
    setMunicipioLoadStep(0);
    setSelectedMunicipio(codigoIbge);
    setDiagnostic(null);
    setSimGeoJSON(null);
    setSimContours(null);
    setSimFlowPaths(null);
    setActiveLayers([...DEFAULT_MAP_LAYERS]);

    const stepTimer = window.setInterval(() => {
      setMunicipioLoadStep((s) => Math.min(s + 1, 3));
    }, 1200);

    try {
      setMunicipioLoadStep(1);
      let inDb = await isMunicipalityInDatabase(codigoIbge);
      if (!inDb) {
        setMunicipioLoadStep(2);
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
      setMunicipioLoadStep(3);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Falha ao integrar município';
      setMunicipioEnsureError(msg);
      setMunicipalities((prev) =>
        prev.map((m) =>
          m.codigo_ibge === codigoIbge ? { ...m, loaded: false } : m,
        ),
      );
    } finally {
      window.clearInterval(stepTimer);
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

    const isFlood =
      geojson?.features?.some(
        (f: { properties?: { layer_type?: string; depth_band?: string } }) =>
          f.properties?.layer_type === 'flood_band' || f.properties?.depth_band,
      ) ?? false;
    const isHeat =
      geojson?.features?.some(
        (f: { properties?: { temp_increase_celsius?: number } }) =>
          f.properties?.temp_increase_celsius != null,
      ) ?? false;

    if ((isFlood || isHeat) && geojson?.features?.length > 0) {
      setMapMode('3d');
      setMapFocus(getGeoJsonCenter(geojson) || mapFocus);
      setZoom(14);
    } else if (geojson?.features?.length > 0) {
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

  useEffect(() => {
    if (activeTab !== 'simulation' || !selectedMunicipio) return;
    api.getTerrainConfig(selectedMunicipio).catch(() => {
      api.processTerrainDem(selectedMunicipio).catch(() => {});
    });
  }, [activeTab, selectedMunicipio]);

  useEffect(() => {
    api.getMonitoringDashboard(selectedMunicipio)
      .then((d) => setAlertNivel(d.nivel_risco_atual))
      .catch(() => {});
  }, [selectedMunicipio]);

  useEffect(() => {
    api.getLayersMeta(selectedMunicipio)
      .then((meta) => {
        const layersMeta = meta.layers || {};
        const blocked = new Set(meta.camadas_bloqueadas || []);
        setMalhaIndisponivel(meta.malha_disponivel === false && selectedMunicipio !== '2611606');
        setScoreConfiabilidade(meta.score_confiabilidade ?? null);
        setLayerOptions((prev) =>
          prev.map((layer) => {
            const patch = layersMeta[layer.id as keyof typeof layersMeta];
            if (!patch || typeof patch !== 'object') {
              return {
                ...layer,
                disponivel: !blocked.has(layer.id),
              };
            }
            const patchObj = patch as {
              source?: string;
              quality?: string;
              disponivel?: boolean;
              tooltip_estimado?: string;
            };
            return {
              ...layer,
              source: patchObj.source ?? layer.source,
              quality: (patchObj.quality as LayerQuality) ?? layer.quality,
              disponivel: patchObj.disponivel ?? !blocked.has(layer.id),
              tooltipEstimado: patchObj.tooltip_estimado,
            };
          }),
        );
        if (blocked.size > 0) {
          setActiveLayers((prev) => prev.filter((id) => !blocked.has(id)));
        }
      })
      .catch(() => {});
  }, [selectedMunicipio, setLayerOptions, setActiveLayers]);

  useEffect(() => {
    if (!activeLayers.includes('socioeconomico')) {
      setSocioRanking(null);
      return;
    }
    api.getSocioeconomicRanking(selectedMunicipio, 5)
      .then(setSocioRanking)
      .catch(() => setSocioRanking(null));
  }, [selectedMunicipio, activeLayers]);

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

  return (
    <main className="min-h-screen bg-background text-zinc-100 flex flex-col font-sans select-none">
      {/* Premium Header */}
      <header
        className={`shrink-0 border-b border-border bg-card/65 backdrop-blur-md px-6 flex items-center justify-between z-50 transition-all duration-300 ${
          focusMode ? 'min-h-[56px] py-2' : 'h-22 min-h-[88px]'
        }`}
      >
        <div className="flex items-center gap-4">
          <img
            src="/logo-sinidu-clima.png"
            alt="Logo Sinidu+Clima"
            className={`rounded-2xl border border-zinc-800 bg-black object-cover shadow-lg shadow-indigo-600/20 transition-all duration-300 ${
              focusMode ? 'h-10 w-10' : 'h-[72px] w-[72px]'
            }`}
          />
          <div className={focusMode ? 'hidden sm:block' : undefined}>
            <h1
              className={`font-extrabold tracking-tight bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent transition-all duration-300 ${
                focusMode ? 'text-lg' : 'text-2xl'
              }`}
            >
              Sinidu+Clima <span className="text-indigo-400 font-medium">INTERNO</span>
            </h1>
            {!focusMode && (
              <span className="text-[11px] text-zinc-500 uppercase tracking-[0.22em] font-semibold block">
                Plataforma de Inteligência Territorial
              </span>
            )}
          </div>
        </div>
        
        {/* Pilot Info Badge */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggleFocusMode}
            title="Modo Focus — tecla F"
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider transition-all duration-300 ${
              focusMode
                ? 'border-teal-400/50 bg-teal-500/20 text-teal-200'
                : 'border-zinc-700 bg-zinc-950/80 text-zinc-400 hover:border-indigo-500/40 hover:text-indigo-200'
            }`}
          >
            <Focus size={12} />
            {focusMode ? 'Focus ativo' : 'Modo Focus'}
            {!focusMode && <span className="hidden md:inline text-zinc-600 font-normal normal-case">(F)</span>}
          </button>
          {!focusMode && <AuthBar />}
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
        <div className="border-b border-indigo-500/40 bg-indigo-950/40 px-6 py-3">
          <MunicipioLoadProgress visible stepIndex={municipioLoadStep} />
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
        <section
          className={`border-r border-border bg-card/10 backdrop-blur-sm flex flex-col overflow-hidden shrink-0 z-40 transition-all duration-300 ease-in-out ${
            focusMode ? 'w-0 border-r-0 opacity-0 pointer-events-none' : 'w-[450px] opacity-100'
          }`}
          aria-hidden={focusMode}
        >
          
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
          <div className="flex-1 min-h-0 overflow-y-auto p-5">
            <TabContextHint tab={activeTab} onNavigateTab={navigateTab} />
            {activeTab === 'dashboard' && (
              <div className="flex flex-col gap-4">
                <OnboardingBanner codigoIbge={selectedMunicipio} municipioNome={selectedMunicipioInfo?.nome} />
                <ExecutiveDashboard
                key={`${selectedMunicipio}-${selectedMunicipioInfo?.loaded}`}
                codigoIbge={selectedMunicipio}
                municipioLoaded={selectedMunicipioInfo?.loaded === true}
                municipioEnsuring={municipioEnsuring}
                municipioNome={selectedMunicipioInfo?.nome}
              />
              </div>
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
                onSimulatingChange={setSimulating}
                codigoIbge={selectedMunicipio}
                municipioNome={selectedMunicipioInfo?.nome}
                municipioLoaded={selectedMunicipioInfo?.loaded === true}
                overlayOptions={simOverlays}
                onOverlayChange={setSimOverlays}
                mapMode3dActive={mapMode === '3d'}
                onView3D={() => setMapMode('3d')}
                onFocusWorkshop={() => {
                  setMapMode('3d');
                  setFocusMode(true);
                }}
                onCrossRiskLayers={() => setActiveLayers([...LAYER_PRESETS.cruzarRiscos.layers])}
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
            {activeTab === 'cases' && (
              <CaseStudiesPanel
                municipioNome={selectedMunicipioInfo?.nome}
                municipioCodigo={selectedMunicipio}
              />
            )}
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
            {activeTab === 'audit' && isAdmin && <AuditPanel codigoIbge={selectedMunicipio} />}
            {activeTab === 'system' && isAdmin && <SystemPanel />}
          </div>
        </section>

        {/* Right Mapping View (60% width) */}
        <section className="relative flex-1 overflow-hidden bg-zinc-950 ring-1 ring-inset ring-zinc-900/80">
          <WorkshopCenter
            selectedMunicipio={selectedMunicipio}
            municipioNome={selectedMunicipioInfo?.nome}
            municipalities={municipalities}
            diagnostic={diagnostic}
            setDiagnostic={setDiagnostic}
            setActiveLayers={setActiveLayers}
            setMapFocus={setMapFocus}
            setZoom={setZoom}
            scoreConfiabilidade={scoreConfiabilidade}
            onGenerateRapido={() => requestReport('rapido')}
            onGenerateCompleto={() => requestReport('completo')}
          />

          {simulating && (
            <div className="pointer-events-none absolute inset-0 z-[500] animate-pulse bg-sky-500/5" aria-hidden />
          )}
          
          {!focusMode && (
            <LayerPanel
              activeLayers={activeLayers}
              setActiveLayers={setActiveLayers}
              toggleLayer={toggleLayer}
              layerOptions={layerOptions}
              malhaIndisponivel={malhaIndisponivel}
            />
          )}

          {socioRanking && activeLayers.includes('socioeconomico') && !focusMode && (
            <div className="absolute bottom-4 right-4 z-[998] w-72 rounded-xl border border-amber-500/30 bg-zinc-950/92 p-3 shadow-2xl backdrop-blur-md">
              <p className="text-[10px] font-extrabold uppercase tracking-wider text-amber-200">
                Desigualdade intra-municipal
              </p>
              <p className="mt-1 text-[9px] text-zinc-400">
                Classificação relativa (tertis) · PIB IBGE {socioRanking.pib_per_capita_ibge ? `R$ ${socioRanking.pib_per_capita_ibge.toLocaleString('pt-BR')}` : '—'} per capita
              </p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[9px] font-bold uppercase text-emerald-300">Mais ricos</span>
                  <ul className="mt-1 space-y-1">
                    {socioRanking.mais_ricos.slice(0, 3).map((row) => (
                      <li key={row.bairro} className="text-[10px] text-zinc-200">
                        {row.bairro}
                        <span className="block text-[9px] text-zinc-500">R$ {row.renda_media.toLocaleString('pt-BR')}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <span className="text-[9px] font-bold uppercase text-orange-300">Mais pobres</span>
                  <ul className="mt-1 space-y-1">
                    {socioRanking.mais_pobres.slice(0, 3).map((row) => (
                      <li key={row.bairro} className="text-[10px] text-zinc-200">
                        {row.bairro}
                        <span className="block text-[9px] text-zinc-500">R$ {row.renda_media.toLocaleString('pt-BR')}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

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
            simOverlays={simOverlays}
            selectedMunicipio={selectedMunicipio}
            simulating={simulating}
          />
          ) : (
          <Map3DMapLibreContainer
            activeLayers={activeLayers}
            simGeoJSON={simGeoJSON}
            simContours={simContours}
            simFlowPaths={simFlowPaths}
            selectedMunicipio={selectedMunicipio}
            mapFocus={mapFocus}
            simulating={simulating}
            focusMode={focusMode}
          />
          )}
        </section>
      </div>
      <AgenteSinidu />
    </main>
  );
}
