'use client';

import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Banknote,
  ChevronDown,
  ChevronRight,
  FileDown,
  Landmark,
  Loader2,
  MapPin,
  School,
  Shield,
  Stethoscope,
  Users,
  Wrench,
} from 'lucide-react';
import {
  api,
  type RiskNivel,
  type RiskPanelBairro,
  type RiskPanelMedida,
  type RiskPanelResponse,
} from '@/utils/api';
import { useAppStore } from '@/stores/useAppStore';
import TermTooltip from '@/components/UI/TermTooltip';

/** Presets locais — evita import circular/pesado de LayerPanel. */
const RISK_MAP_PRESETS = {
  riscoConsolidado: ['bairros', 'risco_consolidado'] as string[],
  desastresInundacao: ['bairros', 'desastres', 'inundacao'] as string[],
};

const CUSTO_STYLE: Record<string, string> = {
  Baixo: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200',
  Médio: 'border-amber-500/40 bg-amber-500/10 text-amber-200',
  Alto: 'border-rose-500/40 bg-rose-500/10 text-rose-200',
};

const TIPO_FINANC_LABEL: Record<string, string> = {
  nao_reembolsavel: 'Não reembolsável',
  credito: 'Crédito',
  orcamento_proprio: 'Orçamento próprio',
  apoio_tecnico: 'Apoio técnico',
};

const NIVEL_STYLE: Record<
  RiskNivel,
  { ring: string; bg: string; text: string; dot: string; badge: string }
> = {
  VERDE: {
    ring: 'border-emerald-500/50',
    bg: 'bg-emerald-950/40',
    text: 'text-emerald-200',
    dot: 'bg-emerald-500',
    badge: 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200',
  },
  AMARELO: {
    ring: 'border-yellow-500/50',
    bg: 'bg-yellow-950/30',
    text: 'text-yellow-200',
    dot: 'bg-yellow-500',
    badge: 'border-yellow-500/40 bg-yellow-500/15 text-yellow-200',
  },
  LARANJA: {
    ring: 'border-orange-500/50',
    bg: 'bg-orange-950/35',
    text: 'text-orange-200',
    dot: 'bg-orange-500 animate-pulse',
    badge: 'border-orange-500/40 bg-orange-500/15 text-orange-200',
  },
  VERMELHO: {
    ring: 'border-red-500/50',
    bg: 'bg-red-950/40',
    text: 'text-red-200',
    dot: 'bg-red-500 animate-pulse',
    badge: 'border-red-500/40 bg-red-500/15 text-red-200',
  },
};

const FATOR_LABEL: Record<string, string> = {
  renda: 'Renda',
  densidade: 'Densidade',
  s2id: 'S2ID',
  impermeabilizacao: 'Impermeab.',
  hidrografia: 'Hidrografia',
  adaptacao: 'Adaptação',
  exposicao: 'Exposição',
};

function formatValor(comp: RiskPanelResponse['componentes']['score']): string {
  if (comp.id === 'alerta') return comp.label;
  if (comp.valor == null) return '—';
  if (comp.escala === '0–100') return String(Math.round(Number(comp.valor)));
  return Number(comp.valor).toFixed(2);
}

function formatFatorValor(valor: number | string | null | undefined, unidade: string): string {
  if (valor == null || valor === '') return '—';
  if (typeof valor === 'number') {
    if (unidade === 'R$/mês') return `R$ ${Math.round(valor).toLocaleString('pt-BR')}`;
    if (unidade === '%') return `${valor}%`;
    if (unidade === 'hab/km²') return `${Math.round(valor).toLocaleString('pt-BR')}`;
    return String(valor);
  }
  return String(valor);
}

function BairroRow({ b }: { b: RiskPanelBairro }) {
  const [open, setOpen] = useState(false);
  const bs = NIVEL_STYLE[b.nivel] ?? NIVEL_STYLE.VERDE;
  const principais = b.fatores_principais ?? [];
  const fatores = b.fatores ?? [];
  const expo = b.exposicao;

  return (
    <div className="rounded-md border border-zinc-800/60 bg-zinc-950/40">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-2.5 py-1.5 text-left text-[11px] hover:bg-zinc-900/50"
      >
        <span className="flex min-w-0 items-center gap-1.5">
          {open ? <ChevronDown size={12} className="shrink-0 text-zinc-500" /> : <ChevronRight size={12} className="shrink-0 text-zinc-500" />}
          <span className="truncate font-semibold text-zinc-200">{b.bairro}</span>
        </span>
        <span className="flex shrink-0 items-center gap-2 text-zinc-400">
          <span className="font-mono text-[10px]">Score {b.score_sinidu}</span>
          <span className={`rounded border px-1.5 py-0.5 text-[8px] font-bold uppercase ${bs.badge}`}>
            {b.label}
          </span>
        </span>
      </button>

      {principais.length > 0 && (
        <div className="flex flex-wrap gap-1 px-2.5 pb-1.5">
          {principais.map((id) => (
            <span
              key={id}
              className="rounded border border-zinc-700 bg-zinc-900/80 px-1.5 py-0.5 text-[8px] font-bold uppercase text-zinc-400"
            >
              {FATOR_LABEL[id] || id}
            </span>
          ))}
        </div>
      )}

      {open && (
        <div className="space-y-2 border-t border-zinc-800/80 px-2.5 py-2">
          {fatores.length > 0 && (
            <div>
              <p className="mb-1 text-[9px] font-bold uppercase tracking-wider text-zinc-500">
                Por que este bairro está no ranking
              </p>
              <div className="flex flex-col gap-1">
                {fatores.slice(0, 5).map((f) => (
                  <div key={f.id} className="flex items-start justify-between gap-2 text-[10px]">
                    <span className="min-w-0">
                      <span className="font-semibold text-zinc-300">{f.nome}</span>
                      <span className="ml-1 text-zinc-500">
                        {formatFatorValor(f.valor, f.unidade)}
                        {f.unidade && f.unidade !== 'score' && f.unidade !== 'capacidade 0–1' ? ` ${f.unidade}` : ''}
                      </span>
                    </span>
                    <span className="shrink-0 font-mono text-zinc-500">+{f.contribuicao.toFixed(1)} pts</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {expo && (
            <div className="grid grid-cols-2 gap-1.5 text-[10px] text-zinc-400 sm:grid-cols-4">
              <div className="min-w-0 rounded border border-zinc-800/60 bg-zinc-950/40 px-1.5 py-1">
                <p className="flex items-center gap-1 truncate">
                  <Users size={11} className="shrink-0 text-sky-400" />
                  <span className="truncate">{(expo.populacao || 0).toLocaleString('pt-BR')} hab</span>
                </p>
              </div>
              <div className="min-w-0 rounded border border-zinc-800/60 bg-zinc-950/40 px-1.5 py-1">
                <p className="flex items-center gap-1 truncate">
                  <School size={11} className="shrink-0 text-indigo-400" />
                  <span className="truncate">{expo.escolas?.n ?? 0} escolas</span>
                </p>
              </div>
              <div className="min-w-0 rounded border border-zinc-800/60 bg-zinc-950/40 px-1.5 py-1">
                <p className="flex items-center gap-1 truncate">
                  <Stethoscope size={11} className="shrink-0 text-rose-400" />
                  <span className="truncate">{expo.saude?.n ?? 0} saúde</span>
                </p>
              </div>
              <div className="min-w-0 rounded border border-zinc-800/60 bg-zinc-950/40 px-1.5 py-1">
                <p className="truncate text-zinc-500">TE: {expo.territorios_especiais?.n ?? 0}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function RiskTrafficLightPanel({
  codigoIbge,
}: {
  codigoIbge?: string;
}) {
  const [panel, setPanel] = useState<RiskPanelResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldPdfLoading, setFieldPdfLoading] = useState(false);
  const setActiveLayers = useAppStore((s) => s.setActiveLayers);

  const handleFieldReport = async () => {
    if (!codigoIbge) return;
    setFieldPdfLoading(true);
    try {
      const blob = await api.downloadFieldReportPdf(codigoIbge);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ficha_campo_${codigoIbge}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Falha ao gerar ficha de campo');
    } finally {
      setFieldPdfLoading(false);
    }
  };

  useEffect(() => {
    if (!codigoIbge) {
      setPanel(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getRiskPanel(codigoIbge, 8)
      .then((data) => {
        if (!cancelled) setPanel(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setPanel(null);
          setError(err instanceof Error ? err.message : 'Falha ao carregar semáforo de risco');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [codigoIbge]);

  if (!codigoIbge) return null;

  if (loading && !panel) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-950/60 px-4 py-5 text-[11px] text-zinc-400">
        <Loader2 size={14} className="animate-spin text-indigo-400" />
        Calculando painel de risco…
      </div>
    );
  }

  if (error && !panel) {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-950/20 px-4 py-3 text-[11px] text-rose-200">
        {error}
      </div>
    );
  }

  if (!panel) return null;

  const style = NIVEL_STYLE[panel.status] ?? NIVEL_STYLE.VERDE;
  const comps = [
    panel.componentes.score,
    panel.componentes.ivc,
    panel.componentes.iri,
    panel.componentes.vm,
    panel.componentes.alerta,
  ];
  const resumo = panel.exposicao_resumo;

  return (
    <div className={`rounded-xl border ${style.ring} ${style.bg} p-4 shadow-lg`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wider text-zinc-400">
            <Shield size={12} className="text-indigo-400" />
            Painel de risco · Ver → Identificar → Agir
          </p>
          <div className="mt-2 flex items-center gap-3">
            <span className={`h-4 w-4 shrink-0 rounded-full ${style.dot}`} />
            <div>
              <p className={`text-xl font-black uppercase tracking-wide ${style.text}`}>
                {panel.status_label}
              </p>
              <p className="text-[11px] leading-snug text-zinc-400">{panel.acao_sugerida}</p>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5 text-right text-[10px] text-zinc-500">
          <div>
            <p className="font-bold text-zinc-300">
              {panel.nome} — {panel.uf}
            </p>
            <p className="font-mono">IBGE {panel.codigo_ibge}</p>
          </div>
          <div className="flex flex-col items-stretch gap-1">
            <button
              type="button"
              onClick={() => setActiveLayers([...RISK_MAP_PRESETS.riscoConsolidado])}
              className="inline-flex items-center justify-center gap-1 rounded-md border border-indigo-500/40 bg-indigo-500/15 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-indigo-200 transition hover:bg-indigo-500/25"
              title="Mapa síntese Score Sinidu × alerta vivo"
            >
              <MapPin size={11} />
              Ver no mapa
            </button>
            <button
              type="button"
              onClick={() => void handleFieldReport()}
              disabled={fieldPdfLoading}
              className="inline-flex items-center justify-center gap-1 rounded-md border border-zinc-600 bg-zinc-900/60 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-50"
              title="PDF imprimível para uso em campo (offline)"
            >
              {fieldPdfLoading ? <Loader2 size={11} className="animate-spin" /> : <FileDown size={11} />}
              Ficha campo
            </button>
          </div>
        </div>
      </div>

      {panel.modo_baixa_maturidade.ativo && (
        <div className="mt-3 rounded-lg border border-amber-500/40 bg-amber-950/40 px-3 py-2.5">
          <p className="flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wider text-amber-200">
            <AlertTriangle size={12} />
            Modo baixa maturidade (bootstrap nacional)
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-amber-100/90">
            {panel.modo_baixa_maturidade.aviso}
          </p>
          {panel.modo_baixa_maturidade.motivos.length > 0 && (
            <ul className="mt-1.5 list-inside list-disc text-[10px] text-amber-200/80">
              {panel.modo_baixa_maturidade.motivos.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {panel.validacao_adapta_brasil && (
        <div
          className={`mt-3 rounded-lg border px-3 py-2.5 ${
            panel.validacao_adapta_brasil.acordo === 'alta'
              ? 'border-emerald-500/35 bg-emerald-950/25'
              : panel.validacao_adapta_brasil.acordo === 'media'
                ? 'border-amber-500/35 bg-amber-950/25'
                : panel.validacao_adapta_brasil.acordo === 'baixa'
                  ? 'border-rose-500/35 bg-rose-950/25'
                  : 'border-zinc-700 bg-zinc-900/40'
          }`}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-zinc-300">
              Validação cruzada · AdaptaBrasil
            </p>
            <span className="rounded border border-zinc-600 px-1.5 py-0.5 text-[8px] font-bold uppercase text-zinc-400">
              acordo {panel.validacao_adapta_brasil.acordo || 'insuficiente'}
            </span>
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-zinc-400">
            {panel.validacao_adapta_brasil.narrativa}
          </p>
          {panel.validacao_adapta_brasil.limitacao && (
            <p className="mt-1 text-[9px] leading-relaxed text-zinc-500">
              {panel.validacao_adapta_brasil.limitacao}
            </p>
          )}
        </div>
      )}

      <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-5">
        {comps.map((c) => {
          const cs = NIVEL_STYLE[c.nivel] ?? NIVEL_STYLE.VERDE;
          return (
            <div
              key={c.id}
              title={c.detalhe}
              className="min-w-0 rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-2.5 py-2"
            >
              <p className="truncate text-[9px] font-bold uppercase tracking-wider text-zinc-500">
                {c.id === 'score' ? (
                  <TermTooltip term="Score" label={c.nome} />
                ) : c.id === 'ivc' ? (
                  <TermTooltip term="IVC" label={c.nome} />
                ) : c.id === 'iri' ? (
                  <TermTooltip term="IRI" label={c.nome} />
                ) : c.id === 'alerta' ? (
                  <TermTooltip term="CEMADEN" label={c.nome} />
                ) : (
                  c.nome
                )}
              </p>
              <p className="mt-0.5 truncate text-sm font-black text-zinc-100">{formatValor(c)}</p>
              <span className={`mt-1 inline-block rounded border px-1.5 py-0.5 text-[8px] font-bold uppercase ${cs.badge}`}>
                {c.label}
              </span>
            </div>
          );
        })}
      </div>

      {(panel.hotspots_recorrentes?.hotspots?.length ?? 0) > 0 && (
        <div className="mt-3 rounded-lg border border-violet-500/30 bg-violet-950/25 px-3 py-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-violet-300">
              Hotspots recorrentes ({panel.hotspots_recorrentes!.total})
            </p>
            <button
              type="button"
              onClick={() => setActiveLayers([...RISK_MAP_PRESETS.desastresInundacao])}
              className="inline-flex items-center gap-1 rounded border border-violet-500/40 bg-violet-500/15 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-violet-200 hover:bg-violet-500/25"
            >
              <MapPin size={10} />
              Ver no mapa
            </button>
          </div>
          <p className="mt-1 text-[10px] leading-snug text-violet-100/70">
            Histórico S2ID (≥2 eventos) + IRI elevado ou mancha simulada 120 mm
          </p>
          <ul className="mt-2 flex flex-col gap-1">
            {panel.hotspots_recorrentes!.hotspots.slice(0, 5).map((h) => (
              <li
                key={h.bairro_id ?? h.bairro}
                className="flex flex-wrap items-baseline justify-between gap-2 rounded border border-violet-500/15 bg-zinc-950/40 px-2 py-1.5 text-[11px]"
              >
                <span className="font-semibold text-zinc-100">{h.bairro}</span>
                <span className="text-[10px] text-zinc-400">
                  {h.eventos_s2id} evt · IRI {h.iri.toFixed(2)}
                  {h.na_mancha_sim_120mm ? ' · sim' : ''}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {resumo && (resumo.bairros_criticos ?? 0) > 0 && (
        <div className="mt-3 rounded-lg border border-sky-500/25 bg-sky-950/20 px-3 py-2.5">
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-sky-300">
            Exposição em áreas críticas (score ≥ {resumo.limiar_score ?? 45})
          </p>
          <div className="mt-2 grid grid-cols-2 gap-2 lg:grid-cols-4">
            <div className="min-w-0 rounded-md border border-sky-500/15 bg-zinc-950/50 px-2.5 py-2">
              <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                <Users size={12} className="shrink-0 text-sky-400" />
                População
              </p>
              <p className="mt-0.5 truncate text-[13px] font-bold text-zinc-100">
                {(resumo.populacao || 0).toLocaleString('pt-BR')}{' '}
                <span className="text-[10px] font-semibold text-zinc-400">hab</span>
              </p>
            </div>
            <div className="min-w-0 rounded-md border border-sky-500/15 bg-zinc-950/50 px-2.5 py-2">
              <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                <School size={12} className="shrink-0 text-indigo-400" />
                Escolas
              </p>
              <p className="mt-0.5 truncate text-[13px] font-bold text-zinc-100">
                {resumo.escolas?.n ?? 0}
              </p>
              {(resumo.escolas?.matriculas ?? 0) > 0 && (
                <p className="mt-0.5 truncate text-[10px] text-zinc-500">
                  {resumo.escolas.matriculas.toLocaleString('pt-BR')} matrículas
                </p>
              )}
            </div>
            <div className="min-w-0 rounded-md border border-sky-500/15 bg-zinc-950/50 px-2.5 py-2">
              <p className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                <Stethoscope size={12} className="shrink-0 text-rose-400" />
                Saúde
              </p>
              <p className="mt-0.5 truncate text-[13px] font-bold text-zinc-100">
                {resumo.saude?.n ?? 0}{' '}
                <span className="text-[10px] font-semibold text-zinc-400">unidades</span>
              </p>
              {(resumo.saude?.ubs ?? 0) > 0 && (
                <p className="mt-0.5 truncate text-[10px] text-zinc-500">{resumo.saude.ubs} UBS</p>
              )}
            </div>
            <div className="min-w-0 rounded-md border border-sky-500/15 bg-zinc-950/50 px-2.5 py-2">
              <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                Território
              </p>
              <p className="mt-0.5 truncate text-[13px] font-bold text-zinc-100">
                {resumo.bairros_criticos}{' '}
                <span className="text-[10px] font-semibold text-zinc-400">bairro(s)</span>
              </p>
              <p className="mt-0.5 truncate text-[10px] text-zinc-500">
                TE: {resumo.territorios_especiais?.n ?? 0}
              </p>
            </div>
          </div>
        </div>
      )}

      {panel.bairros.length > 0 && (
        <div className="mt-3 border-t border-zinc-800/80 pt-3">
          <p className="mb-1.5 flex items-center gap-1 text-[10px] font-extrabold uppercase tracking-wider text-zinc-400">
            <MapPin size={11} />
            Áreas críticas — fatores e exposição ({panel.bairros.length} de {panel.bairros_total})
          </p>
          <div className="flex flex-col gap-1">
            {panel.bairros.map((b) => (
              <BairroRow key={b.bairro_id ?? b.bairro} b={b} />
            ))}
          </div>
        </div>
      )}

      {panel.perfil && (
        <div className="mt-3 border-t border-zinc-800/80 pt-3">
          <p className="mb-1.5 flex items-center gap-1 text-[10px] font-extrabold uppercase tracking-wider text-zinc-400">
            <Landmark size={11} />
            Perfil do município — condiciona o que dá para fazer
          </p>
          <div className="flex flex-wrap gap-1.5 text-[10px]">
            <span className="rounded border border-zinc-700 bg-zinc-900/60 px-2 py-1 font-semibold text-zinc-200">
              Porte {panel.perfil.porte_label}
            </span>
            <span className="rounded border border-zinc-700 bg-zinc-900/60 px-2 py-1 font-semibold text-zinc-200">
              CAPAG {panel.perfil.capag.nota ?? '—'}
            </span>
            <span className="rounded border border-zinc-700 bg-zinc-900/60 px-2 py-1 text-zinc-300">
              Plano Diretor {panel.perfil.plano_diretor.status}
            </span>
            <span className="rounded border border-zinc-700 bg-zinc-900/60 px-2 py-1 text-zinc-300">
              Defesa Civil {panel.perfil.defesa_civil.sinal}
            </span>
          </div>
          {panel.perfil.restricoes.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-[10px] text-zinc-400">
              {panel.perfil.restricoes.slice(0, 3).map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(panel.medidas_recomendadas?.length ?? 0) > 0 && (
        <div className="mt-3 border-t border-zinc-800/80 pt-3">
          <p className="mb-1.5 flex items-center gap-1 text-[10px] font-extrabold uppercase tracking-wider text-zinc-400">
            <Wrench size={11} />
            Agir — medidas com fonte de recurso (porte + CAPAG)
          </p>
          <div className="flex flex-col gap-1.5">
            {panel.medidas_recomendadas!.map((m: RiskPanelMedida) => (
              <div
                key={m.id}
                className="rounded-md border border-zinc-800/70 bg-zinc-950/50 px-2.5 py-2"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="text-[11px] font-semibold text-zinc-100">{m.titulo}</p>
                  <div className="flex shrink-0 gap-1">
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[8px] font-bold uppercase ${
                        CUSTO_STYLE[m.custo] ?? 'border-zinc-600 text-zinc-300'
                      }`}
                    >
                      {m.custo}
                    </span>
                    <span className="rounded border border-zinc-700 px-1.5 py-0.5 text-[8px] font-bold uppercase text-zinc-400">
                      {m.horizonte}
                    </span>
                  </div>
                </div>
                <p className="mt-0.5 text-[10px] leading-snug text-zinc-400">{m.descricao}</p>
                <p className="mt-1 text-[9px] text-zinc-500">
                  {m.orgao}
                  {m.motivo ? ` · ${m.motivo}` : ''}
                </p>
                {(m.fontes_financiamento?.length ?? 0) > 0 && (
                  <div className="mt-1.5 rounded border border-sky-500/20 bg-sky-950/20 px-2 py-1.5">
                    <p className="mb-1 flex items-center gap-1 text-[8px] font-extrabold uppercase tracking-wider text-sky-300">
                      <Banknote size={10} />
                      Fontes de recurso
                    </p>
                    <ul className="flex flex-col gap-1">
                      {m.fontes_financiamento!.slice(0, 3).map((f) => (
                        <li key={f.id} className="text-[9px] leading-snug text-zinc-300">
                          <span className="font-semibold text-sky-100">{f.nome}</span>
                          <span className="text-zinc-500">
                            {' '}
                            · {TIPO_FINANC_LABEL[f.tipo] ?? f.tipo}
                          </span>
                          {f.motivo ? (
                            <span className="block text-[8px] text-zinc-500">{f.motivo}</span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
