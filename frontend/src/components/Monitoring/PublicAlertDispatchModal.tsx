'use client';

import { useEffect, useState } from 'react';
import { Megaphone, X, Loader2, ExternalLink, CheckCircle2 } from 'lucide-react';
import {
  api,
  type PublicAlertDraft,
  type PublicAlertDispatchResult,
} from '@/utils/api';

type Props = {
  open: boolean;
  onClose: () => void;
  codigoIbge: string;
  onDone?: (result: PublicAlertDispatchResult) => void;
};

const NIVEL_OPTS = ['AMARELO', 'LARANJA', 'VERMELHO'] as const;

export default function PublicAlertDispatchModal({ open, onClose, codigoIbge, onDone }: Props) {
  const [draft, setDraft] = useState<PublicAlertDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PublicAlertDispatchResult | null>(null);
  const [nivel, setNivel] = useState('LARANJA');
  const [mensagem, setMensagem] = useState('');
  const [selected, setSelected] = useState<string[]>(['checklist_dc', 'whatsapp_dc', 'gotify']);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setResult(null);
    api
      .getPublicAlertDraft(codigoIbge)
      .then((d) => {
        if (cancelled) return;
        setDraft(d);
        setNivel(d.nivel_sugerido || 'LARANJA');
        setMensagem(d.mensagem || '');
        const defaults = (d.canais || [])
          .filter((c) => c.disponivel && c.id !== 'sms')
          .map((c) => c.id);
        setSelected(defaults.length ? defaults : ['checklist_dc']);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Falha ao carregar prévia');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, codigoIbge]);

  const toggleCanal = (id: string) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const handleSend = async () => {
    if (!selected.length) {
      setError('Selecione ao menos um canal.');
      return;
    }
    setSending(true);
    setError(null);
    try {
      const res = await api.dispatchPublicAlert(codigoIbge, {
        nivel,
        mensagem,
        canais: selected,
        confirm: true,
      });
      setResult(res);
      onDone?.(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Falha na disseminação');
    } finally {
      setSending(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[2100] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-rose-500/30 bg-zinc-950 shadow-2xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-zinc-800 bg-zinc-950/95 px-4 py-3">
          <div className="flex items-center gap-2">
            <Megaphone size={16} className="text-rose-300" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-rose-100">
              Disseminar alerta
            </h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-3 p-4">
          {loading && (
            <p className="flex items-center gap-2 text-xs text-zinc-400">
              <Loader2 size={14} className="animate-spin" /> Montando mensagem e canais…
            </p>
          )}
          {error && (
            <p className="rounded-lg border border-rose-800 bg-rose-950/40 px-3 py-2 text-xs text-rose-200">
              {error}
            </p>
          )}

          {result ? (
            <div className="space-y-3">
              <div className="flex items-start gap-2 rounded-lg border border-emerald-500/35 bg-emerald-950/25 px-3 py-2.5">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-300" />
                <div>
                  <p className="text-[10px] font-extrabold uppercase tracking-wide text-emerald-200">
                    Disseminação registrada #{result.id}
                  </p>
                  <p className="mt-0.5 text-[11px] text-zinc-300">
                    Nível {result.nivel} · {result.canais.join(', ')}
                  </p>
                </div>
              </div>
              <ul className="space-y-1 text-[10px] text-zinc-400">
                {Object.entries(result.status_por_canal || {}).map(([canal, st]) => (
                  <li key={canal} className="flex justify-between gap-2 rounded border border-zinc-800 px-2 py-1.5">
                    <span className="font-bold uppercase text-zinc-300">{canal}</span>
                    <span>{typeof st === 'object' && st && 'status' in st ? String(st.status) : '—'}</span>
                  </li>
                ))}
              </ul>
              {(result.destinos?.length ?? 0) > 0 && (
                <div className="space-y-1">
                  <p className="text-[9px] font-bold uppercase text-zinc-500">Abrir WhatsApp</p>
                  {result.destinos!.map((d) => (
                    <a
                      key={`${d.telefone}-${d.url}`}
                      href={d.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center justify-between gap-2 rounded-lg border border-emerald-500/30 bg-emerald-950/20 px-3 py-2 text-[11px] text-emerald-100 hover:bg-emerald-900/30"
                    >
                      <span>
                        {d.nome}
                        {d.cargo ? ` · ${d.cargo}` : ''}
                      </span>
                      <ExternalLink size={12} />
                    </a>
                  ))}
                </div>
              )}
              <button
                type="button"
                onClick={onClose}
                className="w-full rounded-lg border border-zinc-600 bg-zinc-900 px-3 py-2 text-xs font-semibold text-zinc-200 hover:bg-zinc-800"
              >
                Fechar
              </button>
            </div>
          ) : (
            !loading &&
            draft && (
              <>
                <p className="text-[10px] text-zinc-500">
                  {draft.nome}/{draft.uf} · alerta vivo {draft.alerta_vivo?.nivel_alerta || '—'}
                  {draft.alerta_vivo?.vivo ? ' (ativo)' : ''}
                </p>

                <div>
                  <label className="mb-1 block text-[10px] uppercase text-zinc-500">Nível</label>
                  <select
                    value={nivel}
                    onChange={(e) => setNivel(e.target.value)}
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-2 text-sm text-zinc-100"
                  >
                    {NIVEL_OPTS.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-[10px] uppercase text-zinc-500">Mensagem</label>
                  <textarea
                    value={mensagem}
                    onChange={(e) => setMensagem(e.target.value)}
                    rows={5}
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-2 text-xs text-zinc-100"
                  />
                </div>

                <div>
                  <p className="mb-1.5 text-[10px] font-bold uppercase text-zinc-500">Canais</p>
                  <div className="space-y-1.5">
                    {(draft.canais || []).map((c) => (
                      <label
                        key={c.id}
                        className={`flex cursor-pointer items-start gap-2 rounded-lg border px-2.5 py-2 ${
                          selected.includes(c.id)
                            ? 'border-rose-500/40 bg-rose-950/20'
                            : 'border-zinc-800 bg-zinc-900/40'
                        } ${!c.disponivel && c.id !== 'sms' ? 'opacity-60' : ''}`}
                      >
                        <input
                          type="checkbox"
                          checked={selected.includes(c.id)}
                          onChange={() => toggleCanal(c.id)}
                          className="mt-0.5"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block text-[11px] font-semibold text-zinc-200">{c.label}</span>
                          <span className="block text-[9px] text-zinc-500">{c.nota}</span>
                          {!c.disponivel && (
                            <span className="mt-0.5 inline-block text-[8px] font-bold uppercase text-amber-400">
                              {c.status_default}
                            </span>
                          )}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                {draft.nota && <p className="text-[9px] leading-relaxed text-zinc-500">{draft.nota}</p>}

                <button
                  type="button"
                  onClick={() => void handleSend()}
                  disabled={sending}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-rose-500/40 bg-rose-950/40 px-3 py-2.5 text-xs font-bold uppercase tracking-wide text-rose-100 hover:bg-rose-900/50 disabled:opacity-50"
                >
                  {sending ? <Loader2 size={14} className="animate-spin" /> : <Megaphone size={14} />}
                  Registrar e acionar
                </button>
              </>
            )
          )}
        </div>
      </div>
    </div>
  );
}
