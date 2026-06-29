'use client';

import { useCallback, useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { api, type ContingencyPlan, type MonitoringDashboard } from '@/utils/api';
import { useAlertWebSocket } from '@/hooks/useAlertWebSocket';
import { Activity, CloudRain, AlertTriangle, Radio, Map, RefreshCw, Loader2 } from 'lucide-react';

const MonitoringMiniMap = dynamic(() => import('./MonitoringMiniMap'), { ssr: false });

const NIVEL_COLOR: Record<string, string> = {
  VERDE: 'bg-emerald-500',
  AMARELO: 'bg-yellow-500',
  LARANJA: 'bg-orange-500',
  VERMELHO: 'bg-red-500 animate-pulse',
};

interface Props {
  codigoIbge: string;
  municipioNome?: string;
  onActivateContingency?: (nivel: string, plan: ContingencyPlan | null) => void;
  onToast?: (title: string, message: string) => void;
}

export default function MonitoringPanel({ codigoIbge, municipioNome, onActivateContingency, onToast }: Props) {
  const [data, setData] = useState<MonitoringDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const dash = await api.getMonitoringDashboard(codigoIbge);
      setData(dash);
      setLastUpdate(new Date());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [codigoIbge]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.syncMonitoring(codigoIbge);
      onToast?.('Monitoramento', 'OpenMeteo e CEMADEN sincronizados.');
      await load();
    } catch (e) {
      onToast?.('Erro de sync', e instanceof Error ? e.message : 'Falha na sincronização');
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    load();
    const id = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [load]);

  useAlertWebSocket(codigoIbge, (event) => {
    setWsConnected(true);
    const d = event.data as { titulo?: string; mensagem?: string; nivel?: string };
    onToast?.(d.titulo || event.type, String(d.mensagem || JSON.stringify(d)));
    load();
  });

  if (loading && !data) {
    return <p className="text-sm text-zinc-400">Carregando monitoramento…</p>;
  }

  const nivel = data?.nivel_risco_atual || 'VERDE';
  const nome = data?.nome_municipio || municipioNome || codigoIbge;
  const weatherMissing = !data?.weather_disponivel && data?.precip_24h_mm == null;

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pr-1">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-extrabold text-zinc-100">
            <Radio size={16} className={wsConnected ? 'text-emerald-400' : 'text-zinc-500'} />
            Monitoramento operacional
          </h3>
          <p className="mt-0.5 text-[10px] text-zinc-500">
            Escopo: <strong className="text-zinc-300">{nome}</strong>
            {data?.uf ? ` — ${data.uf}` : ''}
            <span className="ml-1 font-mono text-zinc-600">IBGE {codigoIbge}</span>
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {lastUpdate && (
            <span className="text-[9px] text-zinc-500">Atualizado {lastUpdate.toLocaleTimeString('pt-BR')}</span>
          )}
          <button
            type="button"
            onClick={handleSync}
            disabled={syncing}
            className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900/80 px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
          >
            {syncing ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
            Sincronizar agora
          </button>
        </div>
      </div>

      <p className="rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-[10px] leading-relaxed text-zinc-400">
        KPIs abaixo referem-se ao <strong className="text-zinc-200">município selecionado</strong>.
        O mapa nacional mostra a rede de municípios integrados (alertas CEMADEN + previsão OpenMeteo).
      </p>

      <div className="grid grid-cols-3 gap-2">
        <Card
          icon={<AlertTriangle size={14} />}
          label="CEMADEN ativos"
          value={String(data?.cemaden_ativos ?? 0)}
          accent="rose"
          hint="Alertas CEMADEN nas últimas 24h neste município"
        />
        <Card
          icon={<CloudRain size={14} />}
          label="Precip. 24h"
          value={data?.precip_24h_mm != null ? `${data.precip_24h_mm} mm` : '—'}
          accent="sky"
          hint={
            weatherMissing
              ? 'Sem previsão ainda — clique em Sincronizar agora'
              : data?.weather_updated_at
                ? `OpenMeteo · ${new Date(data.weather_updated_at).toLocaleString('pt-BR')}`
                : undefined
          }
        />
        <Card
          icon={<Activity size={14} />}
          label="Risco atual"
          value={nivel}
          accent="amber"
          badgeClass={NIVEL_COLOR[nivel]}
          hint={
            data?.alertas_risco
              ? `${data.alertas_risco} alerta(s) de limiar hidrológico`
              : 'Derivado de precipitação prevista e alertas'
          }
        />
      </div>

      {data?.risk_probability != null && (
        <p className="text-xs text-zinc-400">
          Probabilidade de evento crítico:{' '}
          <strong className="text-amber-300">{(data.risk_probability * 100).toFixed(0)}%</strong>
          {data.precip_72h_mm != null && (
            <span className="text-zinc-600"> · Precip. 72h: {data.precip_72h_mm} mm</span>
          )}
        </p>
      )}

      {weatherMissing && (
        <p className="rounded-lg border border-amber-500/30 bg-amber-950/20 px-3 py-2 text-[10px] text-amber-200/90">
          Previsão meteorológica indisponível para este município. A sincronização OpenMeteo roda automaticamente
          a cada ~55 min ou manualmente pelo botão acima.
        </p>
      )}

      <div>
        <h4 className="mb-2 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
          <Map size={12} /> Rede nacional de alertas
        </h4>
        <MonitoringMiniMap highlightIbge={codigoIbge} />
      </div>

      <div>
        <h4 className="mb-2 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
          Timeline — {nome} · últimas 24h
        </h4>
        <ul className="max-h-48 space-y-2 overflow-y-auto">
          {(data?.timeline || []).map((a) => (
            <li key={a.id} className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs">
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${NIVEL_COLOR[a.nivel] || 'bg-zinc-500'}`} />
                <span className="font-bold text-zinc-200">{a.titulo}</span>
                <span className="ml-auto text-[9px] uppercase text-zinc-600">{a.tipo.replace(/_/g, ' ')}</span>
                <span className="text-[9px] text-zinc-600">{new Date(a.created_at).toLocaleTimeString('pt-BR')}</span>
              </div>
              {a.mensagem && <p className="mt-1 text-zinc-500">{a.mensagem}</p>}
            </li>
          ))}
          {!data?.timeline?.length && (
            <li className="rounded-lg border border-dashed border-zinc-800 px-3 py-4 text-center text-xs text-zinc-500">
              Nenhum alerta nas últimas 24h para {nome}.
              <br />
              <span className="text-[10px] text-zinc-600">Sincronize para buscar alertas CEMADEN e atualizar previsão.</span>
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
      {hint && <p className="mt-1 text-[8px] leading-snug text-zinc-600">{hint}</p>}
    </div>
  );
}
