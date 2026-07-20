'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { api, type ContingencyPlan, type RoutingStatus } from '@/utils/api';
import { Save, ChevronRight, ChevronLeft, FileDown, Shield, Navigation, CheckCircle2, Siren } from 'lucide-react';

const ContingencyDrawMap = dynamic(() => import('./ContingencyDrawMap'), { ssr: false });

const CENARIOS = ['INUNDACAO', 'DESLIZAMENTO', 'MULTIPLO'] as const;
const NIVEIS = ['VERDE', 'AMARELO', 'LARANJA', 'VERMELHO'] as const;
const DEFAULT_OSRM_UFS = ['PE', 'AL', 'SE', 'PB', 'RN', 'CE', 'PI', 'MA'];

interface Props {
  codigoIbge: string;
  municipioNome?: string;
  municipioUf?: string;
  mapFocus: [number, number];
  simGeoJSON?: any;
  initialNivel?: string;
  initialPlan?: ContingencyPlan | null;
  onPlanActivated?: (plan: ContingencyPlan) => void;
}

function hydrateFromPlan(
  plan: ContingencyPlan,
  setters: {
    setPlanId: (id: number) => void;
    setCenario: (v: string) => void;
    setNivel: (v: string) => void;
    setZonas: (v: any[]) => void;
    setRotas: (v: any[]) => void;
    setPontos: (v: any[]) => void;
    setContatos: (v: Array<{ nome: string; cargo: string; telefone: string; whatsapp: string }>) => void;
    setAcoes: (v: Record<string, string[]>) => void;
  },
) {
  setters.setPlanId(plan.id);
  if (plan.cenario_tipo) setters.setCenario(plan.cenario_tipo);
  if (plan.nivel_alerta) setters.setNivel(plan.nivel_alerta);
  setters.setZonas(plan.zonas_evacuacao || []);
  setters.setRotas(plan.rotas_fuga || []);
  setters.setPontos(plan.pontos_apoio || []);
  if (plan.contatos_defesa_civil?.length) {
    setters.setContatos(
      plan.contatos_defesa_civil.map((c) => ({
        nome: c.nome,
        cargo: c.cargo ?? '',
        telefone: c.telefone ?? '',
        whatsapp: c.whatsapp ?? '',
      })),
    );
  }
  if (plan.acoes_por_nivel) setters.setAcoes(plan.acoes_por_nivel);
}

export default function ContingencyWizard({
  codigoIbge,
  municipioNome,
  municipioUf,
  mapFocus,
  simGeoJSON,
  initialNivel = 'AMARELO',
  initialPlan = null,
  onPlanActivated,
}: Props) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planId, setPlanId] = useState<number | null>(initialPlan?.id ?? null);

  const [cenario, setCenario] = useState<string>(initialPlan?.cenario_tipo || 'INUNDACAO');
  const [nivel, setNivel] = useState(initialPlan?.nivel_alerta || initialNivel);
  const [nivelManual, setNivelManual] = useState(false);
  const [alertaVivo, setAlertaVivo] = useState<{
    nivel_alerta: string;
    cemaden_ativos_24h: number;
    alertas_total_24h: number;
    vivo: boolean;
    fonte: string;
    titulo_recente?: string | null;
  } | null>(null);
  const [zonas, setZonas] = useState<any[]>(initialPlan?.zonas_evacuacao || []);
  const [rotas, setRotas] = useState<any[]>(initialPlan?.rotas_fuga || []);
  const [pontos, setPontos] = useState<any[]>(initialPlan?.pontos_apoio || []);
  const [contatos, setContatos] = useState(
    initialPlan?.contatos_defesa_civil?.length
      ? initialPlan.contatos_defesa_civil.map((c) => ({
          nome: c.nome,
          cargo: c.cargo ?? '',
          telefone: c.telefone ?? '',
          whatsapp: c.whatsapp ?? '',
        }))
      : [{ nome: '', cargo: 'Coordenador DC', telefone: '', whatsapp: '' }],
  );
  const [acoes, setAcoes] = useState<Record<string, string[]>>(initialPlan?.acoes_por_nivel || {});
  const [drawMode, setDrawMode] = useState<'zone' | 'support' | 'view'>('zone');
  const [routingStatus, setRoutingStatus] = useState<RoutingStatus | null>(null);

  useEffect(() => {
    api.getRoutingStatus()
      .then(setRoutingStatus)
      .catch(() => setRoutingStatus(null));
  }, []);

  useEffect(() => {
    api.getContingencyActionTemplates(cenario).then(setAcoes).catch(() => {});
  }, [cenario]);

  useEffect(() => {
    if (initialNivel && !initialPlan?.nivel_alerta) {
      setNivel(initialNivel);
      setNivelManual(false);
    }
  }, [initialNivel, initialPlan?.nivel_alerta]);

  useEffect(() => {
    if (!initialPlan?.id) return;
    hydrateFromPlan(initialPlan, {
      setPlanId,
      setCenario,
      setNivel,
      setZonas,
      setRotas,
      setPontos,
      setContatos,
      setAcoes,
    });
  }, [initialPlan?.id]);

  useEffect(() => {
    let cancelled = false;
    setAlertaVivo(null);
    setNivelManual(false);
    api
      .getContingencyAlertaVivo(codigoIbge)
      .then((snap) => {
        if (cancelled) return;
        setAlertaVivo(snap);
        if (
          !initialPlan?.nivel_alerta &&
          NIVEIS.includes(snap.nivel_alerta as (typeof NIVEIS)[number])
        ) {
          setNivel(snap.nivel_alerta);
        }
      })
      .catch(() => {
        if (!cancelled) setAlertaVivo(null);
      });
    return () => {
      cancelled = true;
    };
  }, [codigoIbge, initialPlan?.nivel_alerta]);

  const osrmCoveredUfs = routingStatus?.covered_ufs ?? DEFAULT_OSRM_UFS;
  const coveredSet = new Set(osrmCoveredUfs.map((uf) => uf.toUpperCase()));
  const ufCovered = municipioUf ? coveredSet.has(municipioUf.toUpperCase()) : true;
  const osrmOnline = routingStatus?.available === true;
  const osrmReady = osrmOnline && ufCovered;
  const rotasAproximadas =
    rotas.length > 0 &&
    (!osrmReady ||
      rotas.some((r) => r.aproximada || r.malha_viaria === false || r.fonte_rota === 'fallback'));

  const generateFromSimulation = async () => {
    if (!simGeoJSON) {
      setError('Execute uma simulação primeiro para gerar zonas automaticamente.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const plan = await api.generateContingencyFromSimulation({
        codigo_ibge: codigoIbge,
        cenario_tipo: cenario,
        risk_geojson: simGeoJSON,
        buffer_m: 500,
        nivel_alerta: nivel,
      });
      setPlanId(plan.id);
      setZonas(plan.zonas_evacuacao || []);
      setRotas(plan.rotas_fuga || []);
      setPontos(plan.pontos_apoio || []);
      if (plan.nivel_alerta) setNivel(plan.nivel_alerta);
      setContatos(
        plan.contatos_defesa_civil?.length
          ? plan.contatos_defesa_civil.map((c) => ({
              nome: c.nome,
              cargo: c.cargo ?? '',
              telefone: c.telefone ?? '',
              whatsapp: c.whatsapp ?? '',
            }))
          : contatos,
      );
      setAcoes(plan.acoes_por_nivel || {});
      setStep(2);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const saveDraft = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = {
        cenario_tipo: cenario,
        nivel_alerta: nivel,
        zonas_evacuacao: zonas,
        rotas_fuga: rotas,
        pontos_apoio: pontos,
        contatos_defesa_civil: contatos,
        acoes_por_nivel: acoes,
        status: 'RASCUNHO',
      };
      let plan: ContingencyPlan;
      if (planId) {
        plan = await api.saveContingencyPlan(planId, payload);
      } else {
        plan = await api.createContingencyPlan({ codigo_ibge: codigoIbge, ...payload });
        setPlanId(plan.id);
      }
      return plan;
    } catch (e: any) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const activatePlan = async () => {
    const saved = await saveDraft();
    if (!saved?.id) return;
    setLoading(true);
    try {
      const active = await api.activateContingencyPlan(saved.id);
      onPlanActivated?.(active);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const exportPdf = async () => {
    let id = planId;
    if (!id) {
      const saved = await saveDraft();
      if (!saved?.id) return;
      id = saved.id;
      setPlanId(id);
    }
    setLoading(true);
    setError(null);
    try {
      const meta = await api.exportContingencyPdf(id);
      await api.downloadContingencyPdf(id, meta.filename);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto pr-1 text-zinc-200">
      <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-teal-300">
        <Shield size={14} /> Plano de Contingenciamento — Etapa {step}/4
      </div>

      {error && <p className="rounded-lg border border-rose-500/40 bg-rose-950/30 px-3 py-2 text-xs text-rose-200">{error}</p>}

      {step === 1 && (
        <div className="space-y-3">
          <div
            className={`rounded-lg border px-3 py-2.5 ${
              osrmReady
                ? 'border-emerald-500/35 bg-emerald-950/20'
                : 'border-amber-500/35 bg-amber-950/20'
            }`}
          >
            <div className="flex items-start gap-2">
              {osrmReady ? (
                <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-400" />
              ) : (
                <Navigation size={16} className="mt-0.5 shrink-0 text-amber-300" />
              )}
              <div>
                <p className="text-[10px] font-extrabold uppercase tracking-wide text-zinc-200">
                  Malha viária OSRM — {routingStatus?.region || 'nordeste'}
                </p>
                <p className="mt-1 text-[10px] leading-relaxed text-zinc-400">
                  {osrmReady
                    ? `Rotas de evacuação usarão malha real (${osrmCoveredUfs.join(', ')}). Ideal para demo Recife/PE.`
                    : osrmOnline && !ufCovered
                      ? `OSRM online, mas ${municipioUf || 'esta UF'} não está na cobertura (${osrmCoveredUfs.join(', ')}). Rotas serão geodésicas.`
                      : 'OSRM offline — rotas aproximadas (linha reta). Ative: OSRM_REGION=pe-se bash scripts/osrm-enable.sh'}
                </p>
              </div>
            </div>
          </div>

          <p className="text-xs text-zinc-400">
            Município: <strong className="text-zinc-100">{municipioNome || codigoIbge}</strong>
          </p>
          <label className="block text-[10px] font-bold uppercase text-zinc-500">Cenário COBRADE</label>
          <select
            value={cenario}
            onChange={(e) => setCenario(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs"
          >
            {CENARIOS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          {alertaVivo && (
            <div
              className={`rounded-lg border px-3 py-2 ${
                alertaVivo.vivo
                  ? 'border-rose-500/40 bg-rose-950/20'
                  : 'border-emerald-500/30 bg-emerald-950/15'
              }`}
            >
              <div className="flex items-start gap-2">
                <Siren
                  size={16}
                  className={`mt-0.5 shrink-0 ${alertaVivo.vivo ? 'text-rose-300' : 'text-emerald-400'}`}
                />
                <div>
                  <p className="text-[10px] font-extrabold uppercase tracking-wide text-zinc-200">
                    Alerta vivo · {alertaVivo.nivel_alerta}
                  </p>
                  <p className="mt-1 text-[10px] leading-relaxed text-zinc-400">
                    {alertaVivo.cemaden_ativos_24h} CEMADEN · {alertaVivo.alertas_total_24h} alertas/24h
                    {alertaVivo.titulo_recente ? ` · ${alertaVivo.titulo_recente}` : ''}
                    {!nivelManual ? ' — nível pré-preenchido no plano' : ' — você ajustou o nível manualmente'}
                  </p>
                </div>
              </div>
            </div>
          )}
          <label className="block text-[10px] font-bold uppercase text-zinc-500">Nível de alerta referência</label>
          <select
            value={nivel}
            onChange={(e) => {
              setNivelManual(true);
              setNivel(e.target.value);
            }}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs"
          >
            {NIVEIS.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          {simGeoJSON && (
            <button
              type="button"
              onClick={generateFromSimulation}
              disabled={loading}
              className="w-full rounded-lg bg-teal-600 py-2 text-xs font-bold uppercase text-white hover:bg-teal-500 disabled:opacity-50"
            >
              Gerar automaticamente da simulação
            </button>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="space-y-2">
          <p className="text-[10px] text-zinc-500">Desenhe polígonos de evacuação no mapa (Leaflet.Draw)</p>
          <div className="flex gap-1">
            <button type="button" onClick={() => setDrawMode('zone')} className={`rounded px-2 py-1 text-[10px] font-bold ${drawMode === 'zone' ? 'bg-orange-600' : 'bg-zinc-800'}`}>Zonas</button>
            <button type="button" onClick={() => setDrawMode('view')} className={`rounded px-2 py-1 text-[10px] font-bold ${drawMode === 'view' ? 'bg-zinc-600' : 'bg-zinc-800'}`}>Visualizar</button>
          </div>
          <ContingencyDrawMap
            mapFocus={mapFocus}
            zonas={zonas}
            rotas={rotas}
            pontosApoio={pontos}
            onZonasChange={setZonas}
            onPontosChange={setPontos}
            drawMode={drawMode}
          />
          <p className="text-[10px] text-zinc-500">{zonas.length} zona(s) · {rotas.length} rota(s) gerada(s)</p>
          {rotasAproximadas && rotas.length > 0 && (
            <p className="rounded-lg border border-amber-500/40 bg-amber-950/25 px-3 py-2 text-[10px] text-amber-200/90">
              <strong>Sem malha viária OSRM</strong> — rotas exibidas são geodésicas (linha reta).
              {municipioUf && !coveredSet.has(municipioUf.toUpperCase())
                ? ` Malha OSRM (${osrmCoveredUfs.join(', ') || '—'}) não cobre ${municipioUf}.`
                : ' Serviço OSRM indisponível ou fora da área coberta pelo PBF processado.'}
            </p>
          )}
        </div>
      )}

      {step === 3 && (
        <div className="space-y-2">
          <p className="text-[10px] text-zinc-500">Clique no mapa para marcar pontos de apoio (UBS, escolas, ginásios)</p>
          <button type="button" onClick={() => setDrawMode('support')} className="rounded bg-sky-700 px-3 py-1 text-[10px] font-bold">Modo: marcar pontos</button>
          <ContingencyDrawMap
            mapFocus={mapFocus}
            zonas={zonas}
            rotas={rotas}
            pontosApoio={pontos}
            onZonasChange={setZonas}
            onPontosChange={setPontos}
            drawMode="support"
          />
        </div>
      )}

      {step === 4 && (
        <div className="space-y-3 max-h-[320px] overflow-y-auto">
          {contatos.map((c, i) => (
            <div key={i} className="grid grid-cols-2 gap-2">
              <input placeholder="Nome" value={c.nome} onChange={(e) => {
                const next = [...contatos]; next[i] = { ...c, nome: e.target.value }; setContatos(next);
              }} className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs col-span-2" />
              <input placeholder="Telefone" value={c.telefone} onChange={(e) => {
                const next = [...contatos]; next[i] = { ...c, telefone: e.target.value }; setContatos(next);
              }} className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs" />
              <input placeholder="WhatsApp" value={c.whatsapp} onChange={(e) => {
                const next = [...contatos]; next[i] = { ...c, whatsapp: e.target.value }; setContatos(next);
              }} className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs" />
            </div>
          ))}
          {NIVEIS.map((n) => (
            <div key={n}>
              <label className="text-[10px] font-bold uppercase text-zinc-500">{n}</label>
              <textarea
                rows={2}
                value={(acoes[n] || []).join('\n')}
                onChange={(e) => setAcoes({ ...acoes, [n]: e.target.value.split('\n').filter(Boolean) })}
                className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs"
              />
            </div>
          ))}
        </div>
      )}

      <div className="mt-auto flex flex-wrap gap-2 border-t border-zinc-800 pt-3">
        {step > 1 && (
          <button type="button" onClick={() => setStep((s) => s - 1)} className="flex items-center gap-1 rounded-lg border border-zinc-700 px-3 py-2 text-[10px] font-bold">
            <ChevronLeft size={12} /> Voltar
          </button>
        )}
        {step < 4 && (
          <button type="button" onClick={() => setStep((s) => s + 1)} className="flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-2 text-[10px] font-bold text-white">
            Próximo <ChevronRight size={12} />
          </button>
        )}
        <button type="button" onClick={saveDraft} disabled={loading} className="flex items-center gap-1 rounded-lg border border-teal-600/50 px-3 py-2 text-[10px] font-bold text-teal-300">
          <Save size={12} /> Rascunho
        </button>
        {step === 4 && (
          <>
            <button type="button" onClick={activatePlan} disabled={loading} className="rounded-lg bg-emerald-600 px-3 py-2 text-[10px] font-bold text-white">
              Ativar plano
            </button>
            <button type="button" onClick={exportPdf} className="flex items-center gap-1 rounded-lg border border-zinc-600 px-3 py-2 text-[10px] font-bold">
              <FileDown size={12} /> PDF
            </button>
          </>
        )}
      </div>
    </div>
  );
}
