'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  api,
  type CaseAdaptationResult,
  type CaseFilterOptions,
  type SuccessCase,
} from '@/utils/api';
import { useAppStore } from '@/stores/useAppStore';
import {
  Award,
  BookOpen,
  ExternalLink,
  MapPin,
  Search,
  Sparkles,
  X,
  Filter,
} from 'lucide-react';

const FAIXA_LABELS: Record<string, string> = {
  pequeno: 'Até 100 mil hab.',
  medio: '100–500 mil',
  grande: '500 mil–1M',
  metropole: 'Metrópole (+1M)',
};

function formatCusto(val?: number | null): string {
  if (!val) return '—';
  if (val >= 1_000_000) return `R$ ${(val / 1_000_000).toFixed(1)}M`;
  return `R$ ${(val / 1_000).toFixed(0)}k`;
}

function CaseCard({ c, onClick }: { c: SuccessCase; onClick: () => void }) {
  const resumo = (c.problema_original || c.problema || '').slice(0, 140);
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-left bg-card/45 border border-border p-4 rounded-xl hover:border-indigo-500/40 transition-all flex flex-col gap-2 h-full"
    >
      {c.imagem_url ? (
        <div
          className="h-24 rounded-lg bg-cover bg-center border border-zinc-800"
          style={{ backgroundImage: `url(${c.imagem_url})` }}
        />
      ) : (
        <div className="h-16 rounded-lg bg-gradient-to-br from-indigo-950/40 to-zinc-900 border border-zinc-800 flex items-center justify-center">
          <BookOpen size={20} className="text-indigo-400/60" />
        </div>
      )}
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1 text-[10px] font-bold text-zinc-100">
          <MapPin size={12} className="text-indigo-400 shrink-0" />
          {c.municipio_nome || c.municipio}/{c.municipio_uf || c.uf}
        </span>
        {c.tipo_intervencao && (
          <span className="text-[8px] uppercase font-bold px-1.5 py-0.5 rounded-full bg-indigo-950/50 text-indigo-300 border border-indigo-800/40">
            {c.tipo_intervencao}
          </span>
        )}
      </div>
      <h4 className="text-[11px] font-bold text-zinc-100 leading-snug line-clamp-2">
        {c.titulo || resumo}
      </h4>
      <p className="text-[9px] text-zinc-400 line-clamp-2">{resumo}…</p>
      {(c.resultado_mensuravel || c.resultado) && (
        <p className="text-[9px] text-emerald-400/90 line-clamp-1 flex items-center gap-1">
          <Award size={10} /> {(c.resultado_mensuravel || c.resultado)?.slice(0, 80)}
        </p>
      )}
      <div className="flex flex-wrap gap-1 mt-auto pt-1">
        {c.programa_financiador && (
          <span className="text-[8px] text-zinc-500 border border-zinc-800 rounded px-1.5 py-0.5">
            {c.programa_financiador.slice(0, 35)}
          </span>
        )}
        {c.similarity != null && c.similarity > 0 && (
          <span className="text-[8px] text-indigo-400 ml-auto">
            {Math.round(c.similarity * 100)}% match
          </span>
        )}
      </div>
    </button>
  );
}

function CaseDetailModal({
  caso,
  municipioCodigo,
  municipioNome,
  onClose,
}: {
  caso: SuccessCase;
  municipioCodigo?: string;
  municipioNome?: string;
  onClose: () => void;
}) {
  const [adaptacao, setAdaptacao] = useState<CaseAdaptationResult | null>(null);
  const [loadingAdapt, setLoadingAdapt] = useState(false);
  const setAgenteAberto = useAppStore((s) => s.setAgenteAberto);
  const addAgenteMensagem = useAppStore((s) => s.addAgenteMensagem);

  useEffect(() => {
    if (!municipioCodigo) return;
    setLoadingAdapt(true);
    api
      .adaptCaseForMunicipio(caso.id, municipioCodigo)
      .then(setAdaptacao)
      .catch(() => setAdaptacao(null))
      .finally(() => setLoadingAdapt(false));
  }, [caso.id, municipioCodigo]);

  const abrirAgente = () => {
    const pergunta =
      adaptacao?.pergunta_sugerida ||
      `Como adaptar a solução de ${caso.municipio_nome || caso.municipio} para ${municipioNome || 'meu município'}?`;
    addAgenteMensagem({ role: 'user', content: pergunta });
    if (adaptacao?.adaptacao_ia) {
      addAgenteMensagem({ role: 'assistant', content: adaptacao.adaptacao_ia });
    }
    setAgenteAberto(true);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="relative w-full max-w-lg max-h-[90vh] overflow-y-auto bg-zinc-950 border border-border rounded-2xl shadow-2xl">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-3 right-3 p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400"
        >
          <X size={16} />
        </button>
        <div className="p-5 space-y-4">
          <header>
            <p className="text-[9px] uppercase font-bold text-indigo-400 mb-1">
              {caso.tipo_intervencao} · {caso.ano_implementacao || '—'}
            </p>
            <h3 className="text-sm font-extrabold text-zinc-100 pr-8">
              {caso.titulo || `${caso.municipio_nome}/${caso.municipio_uf}`}
            </h3>
            <p className="text-[10px] text-zinc-400 mt-1">
              {caso.municipio_nome}/{caso.municipio_uf}
              {caso.populacao_aprox ? ` · ~${(caso.populacao_aprox / 1000).toFixed(0)}k hab.` : ''}
              {caso.regiao ? ` · ${caso.regiao}` : ''}
            </p>
          </header>

          <section className="space-y-2 text-[10px]">
            <div>
              <span className="text-[9px] uppercase font-bold text-zinc-500">Problema</span>
              <p className="text-zinc-300 leading-relaxed mt-0.5">
                {caso.problema_original || caso.problema}
              </p>
            </div>
            <div>
              <span className="text-[9px] uppercase font-bold text-zinc-500">Solução</span>
              <p className="text-emerald-400 leading-relaxed mt-0.5">
                {caso.solucao_implementada || caso.solucao}
              </p>
            </div>
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-2.5">
              <span className="text-[9px] uppercase font-bold text-zinc-500 flex items-center gap-1">
                <Award size={10} className="text-yellow-500" /> Resultado
              </span>
              <p className="text-zinc-300 italic mt-0.5">
                {caso.resultado_mensuravel || caso.resultado}
              </p>
            </div>
          </section>

          <div className="grid grid-cols-2 gap-2 text-[9px]">
            <div className="rounded-lg border border-zinc-800 p-2">
              <span className="text-zinc-500 block">Custo estimado</span>
              <span className="font-bold text-zinc-200">{formatCusto(caso.custo_estimado_reais)}</span>
            </div>
            <div className="rounded-lg border border-zinc-800 p-2">
              <span className="text-zinc-500 block">Programa</span>
              <span className="font-bold text-zinc-200 line-clamp-2">
                {caso.programa_financiador || '—'}
              </span>
            </div>
          </div>

          {caso.fonte_referencia && (
            <a
              href={caso.fonte_referencia}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[10px] text-sky-400 hover:text-sky-300"
            >
              <ExternalLink size={12} /> Fonte de referência
            </a>
          )}

          {municipioCodigo && (
            <section className="rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-3 space-y-2">
              <h4 className="text-[10px] font-bold text-indigo-200 flex items-center gap-1">
                <Sparkles size={12} /> Adaptação para {municipioNome || 'seu município'}
              </h4>
              {loadingAdapt ? (
                <p className="text-[9px] text-zinc-500 animate-pulse">Analisando com IA…</p>
              ) : adaptacao ? (
                <p className="text-[10px] text-zinc-300 leading-relaxed whitespace-pre-wrap">
                  {adaptacao.adaptacao_ia}
                </p>
              ) : (
                <p className="text-[9px] text-zinc-500">Adaptação indisponível no momento.</p>
              )}
              <button
                type="button"
                onClick={abrirAgente}
                className="w-full text-[10px] font-bold py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition"
              >
                {adaptacao?.pergunta_sugerida || 'Perguntar ao agente'}
              </button>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CaseStudiesPanel({
  municipioNome,
  municipioCodigo,
}: {
  municipioNome?: string;
  municipioCodigo?: string;
}) {
  const [query, setQuery] = useState('');
  const [cases, setCases] = useState<SuccessCase[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<SuccessCase | null>(null);
  const [filters, setFilters] = useState<CaseFilterOptions | null>(null);
  const [regiao, setRegiao] = useState('');
  const [tipo, setTipo] = useState('');
  const [faixa, setFaixa] = useState('');
  const [programa, setPrograma] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    api.getCaseFilters().then(setFilters).catch(() => null);
  }, []);

  const runSearch = useCallback(
    async (q: string) => {
      if (!q.trim() || q.trim().length < 2) return;
      setLoading(true);
      try {
        const res = await api.searchCasesSemantic({
          query: q.trim(),
          municipio_codigo: municipioCodigo,
          top_k: 12,
          regiao: regiao || undefined,
          tipo_intervencao: tipo || undefined,
          faixa_populacao: faixa || undefined,
          programa_financiador: programa || undefined,
        });
        setCases(res.items);
      } catch (err) {
        console.error('Error searching cases:', err);
        setCases([]);
      } finally {
        setLoading(false);
      }
    },
    [municipioCodigo, regiao, tipo, faixa, programa],
  );

  useEffect(() => {
    runSearch(municipioNome ? `casos similares ${municipioNome} drenagem encosta` : 'drenagem urbana adaptação climática');
  }, [municipioNome, runSearch]);

  const handleSimilarToMunicipio = () => {
    const q = municipioNome
      ? `intervenções de adaptação climática similares a ${municipioNome}`
      : 'casos de sucesso drenagem encosta habitação';
    setQuery(q);
    runSearch(q);
  };

  return (
    <div className="flex flex-col gap-4 overflow-y-auto max-h-[85vh] pr-2">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') runSearch(query);
            }}
            placeholder="Buscar casos por problema, solução, município…"
            className="w-full bg-zinc-950 border border-border rounded-lg pl-8 pr-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500/50"
          />
          <Search size={14} className="absolute left-2.5 top-3 text-zinc-500" />
        </div>
        <button
          type="button"
          onClick={() => runSearch(query || 'drenagem')}
          className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-3 py-2 text-xs font-bold"
        >
          Pesquisar
        </button>
        <button
          type="button"
          onClick={() => setShowFilters((v) => !v)}
          className="border border-border rounded-lg px-2 py-2 text-zinc-400 hover:text-zinc-200"
          title="Filtros"
        >
          <Filter size={14} />
        </button>
      </div>

      {showFilters && filters && (
        <div className="grid grid-cols-2 gap-2 p-3 rounded-xl border border-border bg-zinc-950/50 text-[10px]">
          <label className="flex flex-col gap-1">
            <span className="text-zinc-500 font-bold uppercase text-[8px]">Região</span>
            <select
              value={regiao}
              onChange={(e) => setRegiao(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-zinc-200"
            >
              <option value="">Todas</option>
              {filters.regioes.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-zinc-500 font-bold uppercase text-[8px]">Tipo</span>
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-zinc-200"
            >
              <option value="">Todos</option>
              {filters.tipos_intervencao.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-zinc-500 font-bold uppercase text-[8px]">População</span>
            <select
              value={faixa}
              onChange={(e) => setFaixa(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-zinc-200"
            >
              <option value="">Qualquer</option>
              {filters.faixas_populacao.map((f) => (
                <option key={f} value={f}>{FAIXA_LABELS[f] || f}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-zinc-500 font-bold uppercase text-[8px]">Programa</span>
            <select
              value={programa}
              onChange={(e) => setPrograma(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-zinc-200"
            >
              <option value="">Todos</option>
              {filters.programas_financiadores.map((p) => (
                <option key={p} value={p}>{p.slice(0, 40)}</option>
              ))}
            </select>
          </label>
        </div>
      )}

      {municipioNome && (
        <button
          type="button"
          onClick={handleSimilarToMunicipio}
          className="text-[10px] font-bold text-left px-3 py-2 rounded-lg border border-indigo-500/30 bg-indigo-950/20 text-indigo-200 hover:bg-indigo-950/40 transition"
        >
          Casos similares ao {municipioNome}
        </button>
      )}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 animate-pulse">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-44 bg-zinc-900 rounded-xl border border-zinc-800" />
          ))}
        </div>
      ) : cases.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 text-zinc-500 text-xs gap-2">
          <BookOpen size={24} className="text-zinc-600" />
          <span>Nenhum caso encontrado.</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {cases.map((c) => (
            <CaseCard key={c.id} c={c} onClick={() => setSelected(c)} />
          ))}
        </div>
      )}

      {selected && (
        <CaseDetailModal
          caso={selected}
          municipioCodigo={municipioCodigo}
          municipioNome={municipioNome}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
