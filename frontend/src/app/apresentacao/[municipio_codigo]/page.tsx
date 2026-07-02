'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';

import { api, getApiBaseUrl, type PresentationPayload } from '@/utils/api';

const TOTAL_SLIDES = 8;

function scoreColor(severidade: string, score: number): string {
  if (severidade === 'Crítica' || score >= 66) return '#ef4444';
  if (severidade === 'Alta' || score >= 33) return '#f97316';
  return '#6366f1';
}

function fmtCurrency(value: number | null | undefined): string {
  if (value == null) return '—';
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
}

function fmtNum(value: number | null | undefined): string {
  if (value == null) return '—';
  return value.toLocaleString('pt-BR');
}

export default function ApresentacaoPage() {
  const params = useParams();
  const router = useRouter();
  const codigo = String(params.municipio_codigo || '').replace(/\D/g, '').padStart(7, '0').slice(-7);

  const [data, setData] = useState<PresentationPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [slide, setSlide] = useState(0);
  const [touchStart, setTouchStart] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const payload = await api.getPresentationData(codigo);
        if (!cancelled) setData(payload);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Falha ao carregar apresentação.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [codigo]);

  const goNext = useCallback(() => setSlide((s) => Math.min(TOTAL_SLIDES - 1, s + 1)), []);
  const goPrev = useCallback(() => setSlide((s) => Math.max(0, s - 1)), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault();
        goNext();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        goPrev();
      } else if (e.key === 'Escape') {
        router.back();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [goNext, goPrev, router]);

  const onTouchStart = (e: React.TouchEvent) => setTouchStart(e.touches[0].clientX);
  const onTouchEnd = (e: React.TouchEvent) => {
    if (touchStart == null) return;
    const delta = e.changedTouches[0].clientX - touchStart;
    if (delta > 60) goPrev();
    else if (delta < -60) goNext();
    setTouchStart(null);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-300">
        Carregando apresentação…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-950 px-6 text-center text-zinc-300">
        <p>{error || 'Dados indisponíveis.'}</p>
        <p className="text-sm text-zinc-500">Gere um diagnóstico executivo na Central da Oficina antes de apresentar.</p>
        <button
          type="button"
          onClick={() => router.push('/painel')}
          className="rounded-lg border border-teal-600/40 bg-teal-950/30 px-4 py-2 text-sm text-teal-200"
        >
          Voltar ao painel
        </button>
      </div>
    );
  }

  const { municipio, score, severidade, narrativa, mapa, bairros_prioritarios, historico_desastres, saude_fiscal, plano_acao, pdf } = data;
  const scoreClr = scoreColor(severidade, score);
  const pdfUrl = pdf.download_url ? `${getApiBaseUrl()}${pdf.download_url}` : undefined;
  const qrUrl = pdfUrl
    ? `https://api.qrserver.com/v1/create-qr-code/?size=140x140&data=${encodeURIComponent(pdfUrl)}`
    : undefined;

  const renderActions = (items: { titulo: string }[]) =>
    items.length ? (
      <ul className="mt-3 space-y-2 text-left text-sm text-zinc-300">
        {items.map((a) => (
          <li key={a.titulo} className="flex gap-2">
            <span className="text-teal-400">•</span>
            <span>{a.titulo}</span>
          </li>
        ))}
      </ul>
    ) : (
      <p className="mt-2 text-sm text-zinc-500">Nenhuma ação cadastrada.</p>
    );

  const slides = [
    /* SLIDE 1 — CAPA */
    (
      <div key="capa" className="flex h-full flex-col items-center justify-center text-center">
        <img src="/logo-sinidu-clima.png" alt="Sinidu+Clima" className="mb-8 h-20 w-auto opacity-90" />
        <h1 className="text-4xl font-extrabold tracking-tight text-zinc-100">
          {municipio.nome} — {municipio.uf}
        </h1>
        <p className="mt-4 text-lg text-teal-300">Diagnóstico Territorial Integrado · {data.data_apresentacao}</p>
        <p className="mt-8 text-sm uppercase tracking-widest text-zinc-500">Apresentado por CGMUR/DDUM/SNDUM/MCID</p>
      </div>
    ),
    /* SLIDE 2 — RESUMO */
    (
      <div key="resumo" className="grid h-full grid-cols-[1fr_auto] items-center gap-10 px-4">
        <div>
          <h2 className="mb-4 text-2xl font-bold text-teal-300">Resumo Executivo</h2>
          <p className="text-lg leading-relaxed text-zinc-200">{narrativa.contexto || narrativa.texto_completo?.split('\n\n')[0]}</p>
        </div>
        <div className="flex flex-col items-center">
          <div
            className="flex h-44 w-44 flex-col items-center justify-center rounded-full border-4 shadow-2xl"
            style={{ borderColor: scoreClr, boxShadow: `0 0 40px ${scoreClr}44` }}
          >
            <span className="text-5xl font-black" style={{ color: scoreClr }}>{score}</span>
            <span className="mt-1 text-xs uppercase tracking-wider text-zinc-400">Score Sinidu</span>
            <span className="mt-2 text-sm font-semibold text-zinc-300">{severidade}</span>
          </div>
        </div>
      </div>
    ),
    /* SLIDE 3 — MAPA */
    (
      <div key="mapa" className="grid h-full grid-cols-[1fr_220px] gap-6 items-center">
        <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900">
          {mapa.png_base64 ? (
            <img
              src={`data:image/png;base64,${mapa.png_base64}`}
              alt="Mapa de vulnerabilidade"
              className="h-full max-h-[62vh] w-full object-contain"
            />
          ) : (
            <div className="flex h-64 items-center justify-center text-zinc-500">Mapa indisponível</div>
          )}
        </div>
        <div className="space-y-3">
          <h2 className="text-lg font-bold text-zinc-200">Legenda</h2>
          {mapa.legenda.map((item) => (
            <div key={item.label} className="flex items-center gap-2 text-sm text-zinc-300">
              <span className="h-4 w-4 rounded" style={{ background: item.cor }} />
              {item.label}
            </div>
          ))}
        </div>
      </div>
    ),
    /* SLIDE 4 — BAIRROS */
    (
      <div key="bairros" className="flex h-full flex-col gap-6">
        <h2 className="text-2xl font-bold text-teal-300">Bairros Prioritários</h2>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-700 text-zinc-400">
              <th className="py-2 pr-4">Bairro</th>
              <th className="py-2 pr-4">Score</th>
              <th className="py-2 pr-4">População</th>
              <th className="py-2">Risco principal</th>
            </tr>
          </thead>
          <tbody>
            {bairros_prioritarios.map((b) => (
              <tr key={b.bairro} className="border-b border-zinc-800 text-zinc-200">
                <td className="py-2 pr-4 font-medium">{b.bairro}</td>
                <td className="py-2 pr-4">{b.score}</td>
                <td className="py-2 pr-4">{fmtNum(b.populacao)}</td>
                <td className="py-2">{b.risco_principal}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-base leading-relaxed text-zinc-300">{narrativa.prioridades}</p>
      </div>
    ),
    /* SLIDE 5 — DESASTRES */
    (
      <div key="desastres" className="flex h-full flex-col gap-4">
        <h2 className="text-2xl font-bold text-teal-300">Histórico de Desastres (S2ID)</h2>
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={historico_desastres.por_ano}>
              <XAxis dataKey="ano" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #3f3f46' }} />
              <Bar dataKey="eventos" fill="#14b8a6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-zinc-300">
          Total: <strong>{historico_desastres.total_10_anos}</strong> eventos · Maior dano:{' '}
          <strong>{fmtCurrency(historico_desastres.maior_dano)}</strong>
          {historico_desastres.data_maior_dano ? ` em ${historico_desastres.data_maior_dano}` : ''}
        </p>
      </div>
    ),
    /* SLIDE 6 — FISCAL */
    (
      <div key="fiscal" className="flex h-full flex-col items-start justify-center gap-6">
        <div className="flex items-end gap-6">
          <div>
            <p className="text-sm uppercase tracking-wider text-zinc-500">CAPAG</p>
            <p className="text-7xl font-black text-amber-400">{saude_fiscal.capag || '—'}</p>
          </div>
          <div>
            <p className="text-lg text-zinc-300">
              Capacidade de financiamento: <strong>{saude_fiscal.capacidade_financiamento}</strong>
            </p>
            <p className="mt-2 text-zinc-400">
              Receita Corrente Líquida: <strong className="text-zinc-200">{fmtCurrency(saude_fiscal.receita_corrente_liquida)}</strong>
            </p>
          </div>
        </div>
        <div>
          <p className="mb-2 text-sm font-bold uppercase text-teal-400">Programas federais elegíveis</p>
          <ul className="space-y-1 text-zinc-300">
            {(saude_fiscal.programas_elegiveis.slice(0, 3) || []).map((p) => (
              <li key={p.nome || p.programa}>{p.nome || p.programa}</li>
            ))}
          </ul>
        </div>
      </div>
    ),
    /* SLIDE 7 — PLANO */
    (
      <div key="plano" className="flex h-full flex-col gap-4">
        <h2 className="text-2xl font-bold text-teal-300">Plano de Ação</h2>
        <div className="grid flex-1 grid-cols-3 gap-4">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <p className="text-xs font-bold uppercase text-emerald-400">Curto prazo ({plano_acao.curto_prazo.total})</p>
            {renderActions(plano_acao.curto_prazo.acoes)}
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <p className="text-xs font-bold uppercase text-amber-400">Médio prazo ({plano_acao.medio_prazo.total})</p>
            {renderActions(plano_acao.medio_prazo.acoes)}
          </div>
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
            <p className="text-xs font-bold uppercase text-indigo-400">Longo prazo ({plano_acao.longo_prazo.total})</p>
            {renderActions(plano_acao.longo_prazo.acoes)}
          </div>
        </div>
        <p className="text-base leading-relaxed text-zinc-300">{narrativa.proximos_passos}</p>
      </div>
    ),
    /* SLIDE 8 — ENCERRAMENTO */
    (
      <div key="fim" className="flex h-full flex-col items-center justify-center text-center gap-6">
        <p className="text-2xl font-bold text-zinc-100">Dados gerados por Sinidu+Clima</p>
        <p className="text-zinc-400">MCID/CGMUR · {data.data_apresentacao}</p>
        {qrUrl && (
          <div className="rounded-xl border border-zinc-700 bg-white p-3">
            <img src={qrUrl} alt="QR Code relatório PDF" width={120} height={120} />
            <p className="mt-2 text-xs text-zinc-600">Relatório PDF</p>
          </div>
        )}
        <p className="max-w-lg text-sm text-zinc-500">
          Este diagnóstico é para uso interno. Não substitui estudos técnicos oficiais.
        </p>
      </div>
    ),
  ];

  return (
    <div
      className="relative flex min-h-screen flex-col bg-zinc-950 text-zinc-100"
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
    >
      {/* Progress bar */}
      <div className="flex items-center gap-2 px-6 py-4">
        {Array.from({ length: TOTAL_SLIDES }).map((_, i) => (
          <button
            key={i}
            type="button"
            onClick={() => setSlide(i)}
            className={`h-2 flex-1 rounded-full transition ${i === slide ? 'bg-teal-400' : i < slide ? 'bg-teal-800' : 'bg-zinc-800'}`}
            aria-label={`Slide ${i + 1}`}
          />
        ))}
        <span className="ml-4 shrink-0 text-xs text-zinc-500">
          {slide + 1} / {TOTAL_SLIDES}
        </span>
        <button
          type="button"
          onClick={() => router.back()}
          className="ml-2 rounded-lg p-2 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
          aria-label="Sair (ESC)"
        >
          <X size={18} />
        </button>
      </div>

      {/* Slide content */}
      <div className="relative mx-auto w-full max-w-6xl flex-1 px-8 pb-24 pt-4">{slides[slide]}</div>

      {/* Navigation arrows */}
      <button
        type="button"
        onClick={goPrev}
        disabled={slide === 0}
        className="absolute left-4 top-1/2 -translate-y-1/2 rounded-full border border-zinc-700 bg-zinc-900/80 p-3 text-zinc-300 disabled:opacity-30"
        aria-label="Anterior"
      >
        <ChevronLeft size={24} />
      </button>
      <button
        type="button"
        onClick={goNext}
        disabled={slide === TOTAL_SLIDES - 1}
        className="absolute right-4 top-1/2 -translate-y-1/2 rounded-full border border-zinc-700 bg-zinc-900/80 p-3 text-zinc-300 disabled:opacity-30"
        aria-label="Próximo"
      >
        <ChevronRight size={24} />
      </button>
    </div>
  );
}
