'use client';

import { useCallback, useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import {
  api,
  type ContingencyPlan,
  type MonitoringDashboard,
  type MonitoringMapItem,
  type MonitoringTimelineGroupItem,
  type ScenarioAnalysis,
  type MonitoringCompareResult,
} from '@/utils/api';
import { useAlertWebSocket } from '@/hooks/useAlertWebSocket';
import { useAppStore } from '@/stores/useAppStore';
import { EmptyState } from '@/design-system';
import {
  Activity,
  CloudRain,
  AlertTriangle,
  Radio,
  Map,
  RefreshCw,
  Loader2,
  Sparkles,
  TrendingUp,
  History,
  CheckCircle2,
  Wind,
  Mountain,
  ChevronDown,
  ChevronUp,
  X,
  GitCompare,
  Megaphone,
} from 'lucide-react';
import PublicAlertDispatchModal from './PublicAlertDispatchModal';

const MonitoringMiniMap = dynamic(() => import('./MonitoringMiniMap'), { ssr: false });

const NIVEL_COLOR: Record<string, string> = {
  VERDE: 'bg-emerald-500',
  AMARELO: 'bg-yellow-500',
  LARANJA: 'bg-orange-500 animate-pulse',
  VERMELHO: 'bg-red-500 animate-pulse',
};

const ALERT_ICONS: Record<string, typeof CloudRain> = {
  rain: CloudRain,
  wind: Wind,
  landslide: Mountain,
  alert: AlertTriangle,
};

interface Props {
  codigoIbge: string;
  municipioNome?: string;
  onActivateContingency?: (nivel: string, plan: ContingencyPlan | null) => void;
  onToast?: (title: string, message: string) => void;
}

export default function MonitoringPanel({ codigoIbge, municipioNome, onActivateContingency, onToast }: Props) {
  const [data, setData] = useState<MonitoringDashboard | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [scenario, setScenario] = useState<ScenarioAnalysis | null>(null);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [pulseOrange, setPulseOrange] = useState(false);
  const [criticalPopup, setCriticalPopup] = useState<{ mensagem: string } | null>(null);
  const [expandedAlert, setExpandedAlert] = useState<number | null>(null);
  const [alertInterpret, setAlertInterpret] = useState<Record<number, string>>({});
  const [mapSelection, setMapSelection] = useState<MonitoringMapItem | null>(null);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareResult, setCompareResult] = useState<MonitoringCompareResult | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [alertaVivo, setAlertaVivo] = useState<{
    nivel_alerta: string;
    vivo: boolean;
    cemaden_ativos_24h: number;
    titulo_recente?: string | null;
  } | null>(null);
  const [disseminateOpen, setDisseminateOpen] = useState(false);

  const pushAgenteProativo = useAppStore((s) => s.pushAgenteProativo);
  const setAgenteAberto = useAppStore((s) => s.setAgenteAberto);
  const setAlertNivel = useAppStore((s) => s.setAlertNivel);

  const load = useCallback(async () => {
    try {
      const dash = await api.getMonitoringDashboard(codigoIbge);
      setData(dash);
      setLoadError(null);
      setAlertNivel(dash.nivel_risco_atual);
      setLastUpdate(new Date());
    } catch (e) {
      console.error(e);
      setLoadError(e instanceof Error ? e.message : 'Falha ao carregar o monitoramento.');
    } finally {
      setLoading(false);
    }
  }, [codigoIbge, setAlertNivel]);

  const loadAlertaVivo = useCallback(async () => {
    try {
      const snap = await api.getContingencyAlertaVivo(codigoIbge);
      setAlertaVivo({
        nivel_alerta: snap.nivel_alerta,
        vivo: snap.vivo,
        cemaden_ativos_24h: snap.cemaden_ativos_24h,
        titulo_recente: snap.titulo_recente,
      });
    } catch {
      setAlertaVivo(null);
    }
  }, [codigoIbge]);

  const loadScenario = useCallback(
    async (force = false) => {
      setScenarioLoading(true);
      try {
        const analysis = await api.getScenarioAnalysis(codigoIbge, force);
        setScenario(analysis);
      } catch (e) {
        console.error(e);
      } finally {
        setScenarioLoading(false);
      }
    },
    [codigoIbge],
  );

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.syncMonitoring(codigoIbge);
      onToast?.('Monitoramento', 'OpenMeteo e CEMADEN sincronizados.');
      await load();
      await loadAlertaVivo();
      await loadScenario(true);
    } catch (e) {
      onToast?.('Erro de sync', e instanceof Error ? e.message : 'Falha na sincronização');
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    load();
    loadAlertaVivo();
    const id = setInterval(() => {
      load();
      loadAlertaVivo();
    }, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [load, loadAlertaVivo]);

  useEffect(() => {
    if (!data) return;
    loadScenario(false);
  }, [data?.cemaden_ativos, data?.risk_probability, data?.precip_24h_mm, data?.precip_72h_mm, data?.nivel_risco_atual, loadScenario]);

  useAlertWebSocket(codigoIbge, (event) => {
    setWsConnected(true);
    const d = event.data as Record<string, unknown>;

    if (event.type === 'PROACTIVE_RISK') {
      const tier = String(d.tier || '');
      const msg = String(d.mensagem || 'Risco elevado detectado.');
      if (tier === 'WARN') {
        pushAgenteProativo(`⚠️ ${msg}`);
        setAgenteAberto(true);
      } else if (tier === 'ORANGE') {
        setPulseOrange(true);
        pushAgenteProativo(`🟠 ${msg} Recomendo abrir o módulo de Contingência.`);
        setAgenteAberto(true);
      } else if (tier === 'CRITICAL') {
        setCriticalPopup({ mensagem: msg });
        pushAgenteProativo(`🔴 ${msg}`);
        setAgenteAberto(true);
      }
    } else {
      const titulo = String(d.titulo || event.type);
      onToast?.(titulo, String(d.mensagem || JSON.stringify(d)));
    }
    load();
    loadScenario(true);
  });

  const toggleAlertExpand = async (item: MonitoringTimelineGroupItem) => {
    if (expandedAlert === item.id) {
      setExpandedAlert(null);
      return;
    }
    setExpandedAlert(item.id);
    if (!alertInterpret[item.id]) {
      try {
        const res = await api.getAlertInterpretation(codigoIbge, item.id);
        setAlertInterpret((prev) => ({ ...prev, [item.id]: res.interpretacao }));
      } catch {
        setAlertInterpret((prev) => ({ ...prev, [item.id]: 'Interpretação indisponível.' }));
      }
    }
  };

  const handleCompare = async () => {
    if (!mapSelection) return;
    setCompareLoading(true);
    setCompareOpen(true);
    try {
      const result = await api.compareMonitoringMunicipalities(codigoIbge, mapSelection.codigo_ibge);
      setCompareResult(result);
    } catch (e) {
      onToast?.('Comparação', e instanceof Error ? e.message : 'Falha');
    } finally {
      setCompareLoading(false);
    }
  };

  if (loading && !data) {
    return <p className="text-sm text-zinc-400">Carregando monitoramento…</p>;
  }

  if (!data && loadError) {
    return (
      <div className="rounded-xl border border-rose-700/50 bg-rose-950/30 p-4">
        <div className="flex items-center gap-2 text-rose-200">
          <AlertTriangle size={16} />
          <h3 className="text-sm font-bold">Monitoramento indisponível</h3>
        </div>
        <p className="mt-2 text-xs leading-snug text-rose-200/80">
          Não foi possível carregar o painel de {municipioNome || codigoIbge}. O nível de risco{' '}
          <strong>não pode ser confirmado agora</strong> — não assuma VERDE.
        </p>
        <p className="mt-1 font-mono text-[10px] text-rose-300/70">{loadError}</p>
        <button
          type="button"
          onClick={() => {
            setLoading(true);
            load();
          }}
          className="mt-3 flex items-center gap-1.5 rounded-lg border border-rose-600/50 bg-rose-900/40 px-3 py-1.5 text-[11px] font-bold uppercase text-rose-100 hover:bg-rose-800/50"
        >
          <RefreshCw size={12} /> Tentar novamente
        </button>
      </div>
    );
  }

  const nivel = data?.nivel_risco_atual || 'VERDE';
  const nome = data?.nome_municipio || municipioNome || codigoIbge;
  const weatherMissing = !data?.weather_disponivel && data?.precip_24h_mm == null;
  const timeline = data?.timeline_grouped?.length ? data.timeline_grouped : data?.timeline || [];
  const riskBadgeClass = pulseOrange && nivel !== 'VERMELHO' ? NIVEL_COLOR.LARANJA : NIVEL_COLOR[nivel];

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pr-1">
      {criticalPopup && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/70 p-4">
          <div className="max-w-md rounded-2xl border border-red-500/50 bg-zinc-950 p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-red-300">Alerta crítico — probabilidade &gt; 75%</h3>
            <p className="mt-3 text-sm text-zinc-300">{criticalPopup.mensagem}</p>
            <div className="mt-5 flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setCriticalPopup(null);
                  onActivateContingency?.('VERMELHO', data?.plano_ativo ?? null);
                }}
                className="flex-1 rounded-xl bg-red-600 py-2 text-xs font-bold uppercase text-white hover:bg-red-500"
              >
                Ativar plano de contingência
              </button>
              <button
                type="button"
                onClick={() => setCriticalPopup(null)}
                className="rounded-xl border border-zinc-700 px-4 py-2 text-xs text-zinc-400"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-extrabold text-zinc-100">
            <Radio size={16} className={wsConnected ? 'text-emerald-400' : 'text-zinc-500'} />
            Monitoramento operacional
          </h3>
          <p className="mt-0.5 text-[10px] text-zinc-500">
            Escopo: <strong className="text-zinc-300">{nome}</strong>
            {data?.uf ? ` — ${data.uf}` : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={handleSync}
          disabled={syncing}
          className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900/80 px-2 py-1 text-[9px] font-bold uppercase text-zinc-300"
        >
          {syncing ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
          Sincronizar
        </button>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Card icon={<AlertTriangle size={14} />} label="CEMADEN ativos" value={String(data?.cemaden_ativos ?? 0)} accent="rose" />
        <Card
          icon={<CloudRain size={14} />}
          label="Precip. 24h"
          value={data?.precip_24h_mm != null ? `${data.precip_24h_mm} mm` : '—'}
          accent="sky"
          hint={weatherMissing ? 'Sincronize OpenMeteo' : undefined}
        />
        <Card icon={<Activity size={14} />} label="Risco atual" value={nivel} accent="amber" badgeClass={riskBadgeClass} />
      </div>

      {alertaVivo && (
        <div
          className={`rounded-xl border p-3 ${
            alertaVivo.vivo
              ? 'border-rose-500/40 bg-rose-950/25'
              : 'border-zinc-700/60 bg-zinc-900/40'
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                Alerta vivo (contingência)
              </p>
              <p className="mt-1 text-sm font-extrabold text-zinc-100">
                Nível {alertaVivo.nivel_alerta}
                {alertaVivo.vivo ? (
                  <span className="ml-2 rounded-full bg-rose-500/20 px-2 py-0.5 text-[9px] font-bold uppercase text-rose-200">
                    Ativo 24h
                  </span>
                ) : (
                  <span className="ml-2 rounded-full bg-zinc-700/50 px-2 py-0.5 text-[9px] font-bold uppercase text-zinc-400">
                    Sem evento vivo
                  </span>
                )}
              </p>
              <p className="mt-1 text-[11px] text-zinc-400">
                CEMADEN 24h: {alertaVivo.cemaden_ativos_24h}
                {alertaVivo.titulo_recente ? ` · ${alertaVivo.titulo_recente}` : ''}
              </p>
            </div>
            <div className="flex shrink-0 flex-col gap-1.5">
              <button
                type="button"
                onClick={() => setDisseminateOpen(true)}
                className="inline-flex items-center justify-center gap-1 rounded-lg border border-rose-500/40 bg-rose-950/40 px-2.5 py-1.5 text-[9px] font-bold uppercase tracking-wider text-rose-100 hover:bg-rose-900/50"
              >
                <Megaphone size={11} />
                Disseminar alerta
              </button>
              {onActivateContingency && (
                <button
                  type="button"
                  onClick={() => onActivateContingency(alertaVivo.nivel_alerta, null)}
                  className="rounded-lg border border-amber-500/40 bg-amber-950/40 px-2.5 py-1.5 text-[9px] font-bold uppercase tracking-wider text-amber-100 hover:bg-amber-900/50"
                >
                  Abrir contingência
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <PublicAlertDispatchModal
        open={disseminateOpen}
        onClose={() => setDisseminateOpen(false)}
        codigoIbge={codigoIbge}
        onDone={() => {
          onToast?.('Alerta disseminado', 'Registro auditável criado para Defesa Civil / canais selecionados.');
          void load();
        }}
      />

      {data?.risk_probability != null && (
        <p className="text-xs text-zinc-400">
          Probabilidade de evento crítico:{' '}
          <strong className="text-amber-300">{(data.risk_probability * 100).toFixed(0)}%</strong>
          {data.risk_source === 'ml' && (
            <span className="ml-1 rounded bg-violet-500/15 px-1.5 py-0.5 text-[9px] font-bold uppercase text-violet-200">
              ML
            </span>
          )}
          {data.precip_72h_mm != null && (
            <span className="text-zinc-600"> · Precip. 72h: {data.precip_72h_mm} mm</span>
          )}
        </p>
      )}

      {/* Card Análise de Cenário */}
      <div className="rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-indigo-300">
            <Sparkles size={12} /> Análise de cenário
            {scenario?.updated_at && (
              <span className="font-normal normal-case text-zinc-500">
                · Atualizado {new Date(scenario.updated_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </p>
          <button
            type="button"
            onClick={() => loadScenario(true)}
            disabled={scenarioLoading}
            className="text-[9px] font-bold uppercase text-indigo-400 hover:text-indigo-200"
          >
            {scenarioLoading ? '…' : 'Recalcular'}
          </button>
        </div>
        {scenarioLoading && !scenario ? (
          <p className="text-xs text-zinc-500">Gerando análise…</p>
        ) : scenario ? (
          <div className="space-y-3 text-xs text-zinc-300">
            <p className="leading-relaxed">{scenario.interpretacao}</p>
            <p className="flex items-start gap-1.5 text-sky-300/90">
              <TrendingUp size={13} className="mt-0.5 shrink-0" />
              <span>
                <strong>Tendência:</strong> {scenario.tendencia}
              </span>
            </p>
            <div>
              <p className="mb-1 flex items-center gap-1 font-bold text-emerald-400/90">
                <CheckCircle2 size={13} /> Recomendações (Nível {scenario.recomendacao_nivel})
              </p>
              <ul className="list-inside list-disc space-y-0.5 text-zinc-400">
                {scenario.recomendacoes.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
            <p className="flex items-start gap-1.5 text-zinc-500">
              <History size={13} className="mt-0.5 shrink-0" />
              <span>{scenario.referencia_historica}</span>
            </p>
          </div>
        ) : (
          <p className="text-xs text-zinc-500">Análise indisponível.</p>
        )}
      </div>

      <div className="relative">
        <h4 className="mb-2 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
          <Map size={12} /> Rede nacional de alertas
        </h4>
        <MonitoringMiniMap highlightIbge={codigoIbge} onSelect={setMapSelection} />
        {mapSelection && mapSelection.codigo_ibge !== codigoIbge && (
          <div className="absolute bottom-8 left-2 right-2 z-[500] rounded-lg border border-zinc-600 bg-zinc-950/95 p-3 shadow-xl backdrop-blur">
            <p className="text-xs font-bold text-zinc-100">
              {mapSelection.nome} · {mapSelection.uf}
            </p>
            <p className="mt-0.5 text-[10px] text-zinc-400">
              Risco {mapSelection.nivel} · {mapSelection.cemaden_ativos ?? 0} alertas · Precip 72h:{' '}
              {mapSelection.precip_72h_mm != null ? `${mapSelection.precip_72h_mm} mm` : '—'}
            </p>
            <button
              type="button"
              onClick={handleCompare}
              className="mt-2 inline-flex items-center gap-1 rounded-lg border border-sky-500/40 bg-sky-950/40 px-2 py-1 text-[9px] font-bold uppercase text-sky-200"
            >
              <GitCompare size={11} /> Comparar com {nome.split('/')[0]}
            </button>
          </div>
        )}
      </div>

      {compareOpen && (
        <div className="rounded-xl border border-sky-500/30 bg-zinc-900/80 p-4">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[10px] font-bold uppercase text-sky-300">Comparação municipal</p>
            <button type="button" onClick={() => setCompareOpen(false)} className="text-zinc-500 hover:text-zinc-300">
              <X size={14} />
            </button>
          </div>
          {compareLoading ? (
            <p className="text-xs text-zinc-500">Comparando…</p>
          ) : compareResult ? (
            <p className="text-xs leading-relaxed text-zinc-300">{compareResult.comparacao_ia}</p>
          ) : null}
        </div>
      )}

      <div>
        <h4 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
          Timeline — {nome} · últimas 24h
        </h4>
        <ul className="max-h-56 space-y-2 overflow-y-auto">
          {(timeline as MonitoringTimelineGroupItem[]).map((a) => {
            const Icon = ALERT_ICONS[a.alert_icon || 'alert'] || AlertTriangle;
            const open = expandedAlert === a.id;
            return (
              <li key={`${a.id}-${a.titulo}`} className="rounded-lg border border-zinc-800 bg-zinc-900/60">
                <button
                  type="button"
                  onClick={() => toggleAlertExpand(a)}
                  className="flex w-full items-start gap-2 px-3 py-2 text-left text-xs"
                >
                  <Icon size={14} className="mt-0.5 shrink-0 text-zinc-400" />
                  <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${NIVEL_COLOR[a.nivel] || 'bg-zinc-500'}`} />
                  <span className="flex-1 font-bold text-zinc-200">{a.titulo_display || a.titulo}</span>
                  <span className="text-[9px] text-zinc-600">{new Date(a.created_at).toLocaleTimeString('pt-BR')}</span>
                  {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
                {a.mensagem && !open && <p className="px-3 pb-2 text-[10px] text-zinc-500">{a.mensagem}</p>}
                {open && (
                  <div className="border-t border-zinc-800 px-3 py-2 text-[10px] text-zinc-400">
                    <p className="mb-1 font-bold text-zinc-500">O que este alerta significa?</p>
                    <p>{alertInterpret[a.id] || 'Carregando…'}</p>
                  </div>
                )}
              </li>
            );
          })}
          {!timeline.length && (
            <li className="list-none">
              <EmptyState
                icon={Radio}
                compact
                title="Nenhum alerta nas últimas 24h"
                description="O monitor CEMADEN está ativo. Novos eventos aparecerão aqui e no mapa."
              />
            </li>
          )}
        </ul>
      </div>

      <button
        type="button"
        onClick={() => onActivateContingency?.(nivel, data?.plano_ativo ?? null)}
        className="mt-auto w-full rounded-xl border border-teal-500/40 bg-teal-950/40 py-3 text-xs font-bold uppercase tracking-wider text-teal-200 hover:bg-teal-900/50"
      >
        Ativar plano de contingência ({nivel})
      </button>
    </div>
  );
}

function Card({
  icon,
  label,
  value,
  accent,
  badgeClass,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  accent: string;
  badgeClass?: string;
  hint?: string;
}) {
  return (
    <div className={`rounded-xl border border-zinc-800 bg-zinc-900/50 p-3 text-${accent}-300`}>
      <div className="mb-1 flex items-center gap-1 text-[9px] font-bold uppercase text-zinc-500">
        {icon}
        {label}
      </div>
      <div className="text-sm font-extrabold text-zinc-100">
        {badgeClass ? (
          <span className={`inline-block rounded px-2 py-0.5 text-[10px] text-white ${badgeClass}`}>{value}</span>
        ) : (
          value
        )}
      </div>
      {hint && <p className="mt-1 text-[8px] text-zinc-600">{hint}</p>}
    </div>
  );
}
