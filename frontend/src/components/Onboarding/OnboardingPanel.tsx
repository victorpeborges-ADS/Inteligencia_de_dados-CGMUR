'use client';

import { useCallback, useEffect, useState } from 'react';
import { api, type OnboardingStatus, type OnboardingValidateResult } from '@/utils/api';
import { CheckCircle2, Loader2, MapPin, Play, RefreshCw, Search, AlertTriangle } from 'lucide-react';
import GeoportalMunicipalPanel from './GeoportalMunicipalPanel';

const STATUS_COLOR: Record<string, string> = {
  concluido: 'text-emerald-400 bg-emerald-950/50 border-emerald-800',
  parcial: 'text-amber-300 bg-amber-950/40 border-amber-800',
  em_progresso: 'text-sky-300 bg-sky-950/40 border-sky-800',
  falha: 'text-rose-300 bg-rose-950/40 border-rose-800',
  pendente: 'text-zinc-400 bg-zinc-900/60 border-zinc-700',
};

const TIER_COLOR: Record<string, string> = {
  Platina: 'text-slate-200',
  Ouro: 'text-amber-300',
  Prata: 'text-zinc-300',
  Bronze: 'text-orange-300',
};

const STEP_LABEL: Record<string, string> = {
  ibge_validacao: 'Validação IBGE',
  geometria: 'Geometria municipal',
  ibge_indicadores: 'Indicadores IBGE',
  siconfi: 'SICONFI / Tesouro',
  capag: 'CAPAG',
  camadas_territoriais: 'Camadas territoriais',
  s2id: 'Histórico S2ID',
};

interface Props {
  onMunicipioOnboarded?: (codigoIbge: string) => void;
  selectedCodigoIbge?: string;
  onSelectMunicipio?: (codigoIbge: string) => void;
}

export default function OnboardingPanel({ onMunicipioOnboarded, selectedCodigoIbge, onSelectMunicipio }: Props) {
  const [codigoInput, setCodigoInput] = useState(selectedCodigoIbge || '');
  const [nameQuery, setNameQuery] = useState('');
  const [seeds, setSeeds] = useState<Array<{ codigo_ibge: string; nome: string; uf: string }>>([]);
  const [validated, setValidated] = useState<OnboardingValidateResult | null>(null);
  const [items, setItems] = useState<OnboardingStatus[]>([]);
  const [result, setResult] = useState<OnboardingStatus | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [validating, setValidating] = useState(false);
  const [running, setRunning] = useState(false);
  const [activating, setActivating] = useState(false);
  const [showAdvancedGis, setShowAdvancedGis] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('todos');
  const [ufInput, setUfInput] = useState('PE');
  const [ufLimit, setUfLimit] = useState(10);
  const [ufPreview, setUfPreview] = useState<{
    uf: string;
    total_ibge: number;
    ja_carregados: number;
    pendentes: number;
    a_processar: number;
  } | null>(null);
  const [ufBootstrapping, setUfBootstrapping] = useState(false);
  const [ufJobId, setUfJobId] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    setLoadingList(true);
    try {
      const data = await api.listOnboardingStatus();
      setItems(data.items);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    api
      .getSeedMunicipalities()
      .then((list) => setSeeds(list.map((m) => ({ codigo_ibge: m.codigo_ibge, nome: m.nome, uf: m.uf }))))
      .catch(() => setSeeds([]));
  }, []);

  useEffect(() => {
    if (selectedCodigoIbge) {
      setCodigoInput(selectedCodigoIbge);
    }
  }, [selectedCodigoIbge]);

  const handleQuickActivate = async (code?: string) => {
    const ibge = (code || codigoInput).replace(/\D/g, '').padStart(7, '0').slice(-7);
    if (ibge.length !== 7) {
      setError('Informe um código IBGE com 7 dígitos ou escolha um município na busca.');
      return;
    }
    setActivating(true);
    setError(null);
    try {
      const ensured = await api.ensureMunicipality(ibge);
      setCodigoInput(ibge);
      setValidated({
        codigo_ibge: ensured.codigo_ibge,
        nome: ensured.nome,
        uf: ensured.uf,
        valido: true,
      });
      onSelectMunicipio?.(ibge);
      onMunicipioOnboarded?.(ibge);
      await loadList();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Falha ao ativar município');
    } finally {
      setActivating(false);
    }
  };

  const handleValidate = async () => {
    const code = codigoInput.replace(/\D/g, '').padStart(7, '0').slice(-7);
    if (code.length !== 7) {
      setError('Informe um código IBGE com 7 dígitos.');
      return;
    }
    setValidating(true);
    setError(null);
    setValidated(null);
    setResult(null);
    try {
      const v = await api.validateOnboarding(code);
      setValidated(v);
      setCodigoInput(code);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setValidating(false);
    }
  };

  const handleRun = async (code?: string, force = false) => {
    const ibge = (code || codigoInput).replace(/\D/g, '').padStart(7, '0').slice(-7);
    if (ibge.length !== 7) return;
    setRunning(true);
    setError(null);
    try {
      const status = await api.runOnboarding(ibge, force);
      setResult(status);
      setValidated({ codigo_ibge: status.codigo_ibge, nome: status.nome, uf: status.uf, valido: true });
      await loadList();
      onMunicipioOnboarded?.(ibge);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };

  const handleUfPreview = async () => {
    const uf = ufInput.trim().toUpperCase().slice(0, 2);
    if (uf.length !== 2) {
      setError('Informe a sigla da UF (ex.: PE).');
      return;
    }
    setError(null);
    try {
      const data = await api.previewUfBootstrap(uf, ufLimit);
      setUfPreview(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Falha na prévia da UF');
    }
  };

  const handleUfBootstrap = async () => {
    const uf = ufInput.trim().toUpperCase().slice(0, 2);
    if (uf.length !== 2) {
      setError('Informe a sigla da UF (ex.: PE).');
      return;
    }
    setUfBootstrapping(true);
    setError(null);
    try {
      const data = await api.bootstrapUf(uf, { limit: ufLimit, skip_existing: true, async_job: true });
      const jobId = typeof data.job_id === 'string' ? data.job_id : null;
      setUfJobId(jobId);
      await handleUfPreview();
      await loadList();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Falha ao iniciar bootstrap da UF');
    } finally {
      setUfBootstrapping(false);
    }
  };

  const filtered = items.filter((item) => {
    if (filter === 'todos') return true;
    return item.onboarding_status === filter;
  });

  const seedMatches = nameQuery.trim().length >= 2
    ? seeds
        .filter((s) => {
          const q = nameQuery.trim().toLowerCase();
          return (
            s.nome.toLowerCase().includes(q)
            || s.uf.toLowerCase() === q
            || s.codigo_ibge.includes(q.replace(/\D/g, ''))
          );
        })
        .slice(0, 8)
    : [];

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pr-1">
      <div>
        <h3 className="flex items-center gap-2 text-sm font-extrabold text-zinc-100">
          <MapPin size={16} className="text-indigo-400" />
          Onboarding municipal
        </h3>
        <p className="mt-1 text-xs text-zinc-500">
          Ative um município em poucos cliques — sem upload GIS. Depois aprofunde dados se quiser.
        </p>
      </div>

      <div className="rounded-xl border border-emerald-500/25 bg-emerald-950/15 p-3 space-y-2">
        <label className="text-[10px] font-bold uppercase tracking-wider text-emerald-300/80">
          Ativação rápida (sem GIS)
        </label>
        <input
          type="search"
          value={nameQuery}
          onChange={(e) => setNameQuery(e.target.value)}
          placeholder="Buscar por nome (ex.: Recife, Aracaju)…"
          className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600"
        />
        {seedMatches.length > 0 && (
          <ul className="max-h-36 space-y-1 overflow-y-auto">
            {seedMatches.map((s) => (
              <li key={s.codigo_ibge}>
                <button
                  type="button"
                  onClick={() => {
                    setCodigoInput(s.codigo_ibge);
                    setNameQuery(`${s.nome} — ${s.uf}`);
                    void handleQuickActivate(s.codigo_ibge);
                  }}
                  disabled={activating || running}
                  className="flex w-full items-center justify-between rounded-lg border border-zinc-800 bg-zinc-950/60 px-2.5 py-1.5 text-left text-xs hover:border-emerald-500/40"
                >
                  <span className="font-semibold text-zinc-100">{s.nome} — {s.uf}</span>
                  <span className="font-mono text-[10px] text-zinc-500">{s.codigo_ibge}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <button
          type="button"
          onClick={() => handleQuickActivate()}
          disabled={activating || running || codigoInput.replace(/\D/g, '').length < 7}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-[10px] font-bold uppercase text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {activating ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
          Ativar município
        </button>
        <p className="text-[9px] leading-snug text-zinc-500">
          Carrega malha IBGE e bases nacionais. Sem equipe GIS e sem upload de shapefile.
        </p>
      </div>

      <div className="rounded-xl border border-sky-500/25 bg-sky-950/15 p-3 space-y-2">
        <label className="text-[10px] font-bold uppercase tracking-wider text-sky-300/80">
          Bootstrap por UF (18c.1)
        </label>
        <p className="text-[9px] leading-snug text-zinc-500">
          Ativa vários municípios da UF com cobertura mínima (IBGE + S2ID + MapBiomas), sem GIS.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            maxLength={2}
            value={ufInput}
            onChange={(e) => setUfInput(e.target.value.replace(/[^a-zA-Z]/g, '').toUpperCase().slice(0, 2))}
            placeholder="PE"
            className="w-16 rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-2 text-center text-sm font-mono font-bold text-zinc-100"
          />
          <input
            type="number"
            min={1}
            max={100}
            value={ufLimit}
            onChange={(e) => setUfLimit(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
            title="Limite de municípios"
            className="w-20 rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-2 text-sm font-mono text-zinc-100"
          />
          <button
            type="button"
            onClick={() => void handleUfPreview()}
            disabled={ufBootstrapping}
            className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-zinc-600 px-2 py-2 text-[10px] font-bold uppercase text-zinc-300"
          >
            Prévia
          </button>
          <button
            type="button"
            onClick={() => void handleUfBootstrap()}
            disabled={ufBootstrapping || activating || running}
            className="flex flex-1 items-center justify-center gap-1 rounded-lg bg-sky-600 px-2 py-2 text-[10px] font-bold uppercase text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {ufBootstrapping ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            Iniciar
          </button>
        </div>
        {ufPreview && (
          <p className="text-[10px] text-sky-200/90">
            {ufPreview.uf}: {ufPreview.total_ibge} no IBGE · {ufPreview.ja_carregados} já no Sinidu ·{' '}
            {ufPreview.pendentes} pendentes · processará até {ufPreview.a_processar}
          </p>
        )}
        {ufJobId && (
          <p className="text-[9px] font-mono text-zinc-500">Job: {ufJobId}</p>
        )}
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-3 space-y-2">
        <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">
          Código IBGE · integração completa
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            inputMode="numeric"
            maxLength={7}
            value={codigoInput}
            onChange={(e) => setCodigoInput(e.target.value.replace(/\D/g, '').slice(0, 7))}
            placeholder="2611606"
            className="flex-1 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm font-mono text-zinc-100"
          />
          <button
            type="button"
            onClick={handleValidate}
            disabled={validating || running || activating}
            className="flex items-center gap-1 rounded-lg border border-zinc-600 px-3 py-2 text-[10px] font-bold uppercase text-zinc-300"
          >
            {validating ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
            Validar
          </button>
          <button
            type="button"
            onClick={() => handleRun()}
            disabled={running || validating || activating}
            className="flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-2 text-[10px] font-bold uppercase text-white"
          >
            {running ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            Aprofundar
          </button>
        </div>
        {validated && (
          <p className="text-xs text-emerald-300 flex items-center gap-1">
            <CheckCircle2 size={12} />
            {validated.nome} — {validated.uf} ({validated.codigo_ibge})
          </p>
        )}
        {error && (
          <p className="text-xs text-rose-400 flex items-center gap-1">
            <AlertTriangle size={12} /> {error}
          </p>
        )}
      </div>

      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40">
        <button
          type="button"
          onClick={() => setShowAdvancedGis((v) => !v)}
          className="flex w-full items-center justify-between px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-zinc-400 hover:text-zinc-200"
        >
          GIS municipal (opcional)
          <span className="text-zinc-600">{showAdvancedGis ? '−' : '+'}</span>
        </button>
        {showAdvancedGis && (
          <div className="border-t border-zinc-800 p-2">
            <GeoportalMunicipalPanel codigoIbge={codigoInput.length === 7 ? codigoInput : selectedCodigoIbge} />
          </div>
        )}
      </div>

      {result && (
        <div className="rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-3 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${STATUS_COLOR[result.onboarding_status] || STATUS_COLOR.pendente}`}>
              {result.onboarding_status}
            </span>
            {result.pronto_para_uso && (
              <span className="text-[10px] text-emerald-400 font-bold">Pronto para uso</span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <ScoreBox label="Completude" value={result.completeness_score} />
            <ScoreBox label="Maturidade" value={result.maturity_score} suffix="/100" />
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-2">
              <p className="text-[8px] uppercase text-zinc-600">Classificação</p>
              <p className={`text-sm font-extrabold ${TIER_COLOR[result.maturity_classificacao || ''] || 'text-zinc-400'}`}>
                {result.maturity_classificacao || '—'}
              </p>
            </div>
          </div>
          {result.nota_capag && (
            <p className="text-[10px] text-zinc-400">CAPAG: <strong className="text-zinc-200">{result.nota_capag}</strong></p>
          )}
          <ul className="space-y-1">
            {Object.entries(result.integration_steps || {}).map(([key, step]) => (
              <li key={key} className="flex justify-between text-[10px] text-zinc-400">
                <span>{STEP_LABEL[key] || key}</span>
                <span className={
                  step.status === 'ok' ? 'text-emerald-400' :
                  step.status === 'parcial' ? 'text-amber-400' :
                  step.status === 'falha' ? 'text-rose-400' : 'text-zinc-500'
                }>
                  {step.status}
                </span>
              </li>
            ))}
          </ul>
          {result.lacunas?.length > 0 && (
            <p className="text-[9px] text-zinc-600">Lacunas: {result.lacunas.join(', ')}</p>
          )}
        </div>
      )}

      <div className="flex items-center justify-between">
        <h4 className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Municípios ({filtered.length})</h4>
        <div className="flex gap-1">
          {['todos', 'pendente', 'parcial', 'concluido'].map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`rounded px-2 py-0.5 text-[9px] font-bold uppercase ${filter === f ? 'bg-zinc-700 text-zinc-100' : 'text-zinc-600'}`}
            >
              {f}
            </button>
          ))}
          <button type="button" onClick={loadList} className="ml-1 text-zinc-500 hover:text-zinc-300">
            <RefreshCw size={12} />
          </button>
        </div>
      </div>

      {loadingList ? (
        <p className="text-xs text-zinc-500">Carregando…</p>
      ) : (
        <ul className="max-h-64 space-y-1 overflow-y-auto">
          {filtered.map((item) => (
            <li key={item.codigo_ibge}>
              <button
                type="button"
                onClick={() => {
                  setCodigoInput(item.codigo_ibge);
                  onSelectMunicipio?.(item.codigo_ibge);
                }}
                className={`flex w-full items-center gap-2 rounded-lg border px-2 py-1.5 text-left text-xs transition-colors ${
                  selectedCodigoIbge === item.codigo_ibge
                    ? 'border-indigo-500/50 bg-indigo-950/40'
                    : 'border-zinc-800 bg-zinc-950/40 hover:border-zinc-700'
                }`}
              >
                <div className="min-w-0 flex-1">
                  <span className="font-bold text-zinc-200">{item.nome}</span>
                  <span className="text-zinc-600"> · {item.uf} · {item.codigo_ibge}</span>
                </div>
                <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[8px] font-bold uppercase ${STATUS_COLOR[item.onboarding_status] || STATUS_COLOR.pendente}`}>
                  {item.onboarding_status}
                </span>
                {item.completeness_score != null && (
                  <span className="text-[9px] text-zinc-500">{item.completeness_score.toFixed(0)}%</span>
                )}
                {item.maturity_classificacao && (
                  <span className={`text-[9px] font-bold ${TIER_COLOR[item.maturity_classificacao] || 'text-zinc-500'}`}>
                    {item.maturity_classificacao}
                  </span>
                )}
                {item.onboarding_status === 'pendente' && (
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRun(item.codigo_ibge);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.stopPropagation();
                        handleRun(item.codigo_ibge);
                      }
                    }}
                    className="text-[9px] font-bold text-indigo-400"
                  >
                    Rodar
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ScoreBox({ label, value, suffix }: { label: string; value: number | null | undefined; suffix?: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-2">
      <p className="text-[8px] uppercase text-zinc-600">{label}</p>
      <p className="text-sm font-extrabold text-zinc-100">
        {value != null ? `${value.toFixed(0)}${suffix || ''}` : '—'}
      </p>
    </div>
  );
}
