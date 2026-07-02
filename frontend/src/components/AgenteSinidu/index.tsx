'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Send, Sparkles, X } from 'lucide-react';

import { useAgenteContexto } from '@/hooks/useAgenteContexto';
import { useAppStore } from '@/stores/useAppStore';
import { api, type ChatMessage } from '@/utils/api';

function renderMarkdownLite(text: string) {
  return text.split('\n').map((line, lineIdx) => (
    <span key={lineIdx}>
      {lineIdx > 0 && <br />}
      {line.split(/(\*\*[^*]+\*\*)/g).map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return (
            <strong key={i} className="font-semibold text-zinc-100">
              {part.slice(2, -2)}
            </strong>
          );
        }
        return part;
      })}
    </span>
  ));
}

export default function AgenteSinidu() {
  const {
    pageContext,
    municipioCodigo,
    municipioNome,
    dadosPagina,
    perguntasContextuais,
  } = useAgenteContexto();

  const agenteAberto = useAppStore((s) => s.agenteAberto);
  const setAgenteAberto = useAppStore((s) => s.setAgenteAberto);
  const mensagens = useAppStore((s) => s.agenteMensagens);
  const addAgenteMensagem = useAppStore((s) => s.addAgenteMensagem);
  const agenteNaoLidas = useAppStore((s) => s.agenteNaoLidas);
  const agenteLoading = useAppStore((s) => s.agenteLoading);
  const setAgenteLoading = useAppStore((s) => s.setAgenteLoading);

  const [input, setInput] = useState('');
  const [streamingText, setStreamingText] = useState('');
  const [mounted, setMounted] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [mensagens, streamingText, agenteLoading]);

  useEffect(() => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = 'auto';
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
  }, [input]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || agenteLoading || !municipioCodigo) return;

      addAgenteMensagem({ role: 'user', content: trimmed });
      setInput('');
      setAgenteLoading(true);
      setStreamingText('');

      const historico: ChatMessage[] = mensagens.slice(-10).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      try {
        const full = await api.chatContextualAssistantStream(
          {
            message: trimmed,
            municipio_codigo: municipioCodigo,
            pagina_atual: pageContext.pagina,
            descricao_pagina: pageContext.descricao,
            dados_pagina: dadosPagina,
            historico,
          },
          (text) => {
            setStreamingText(text);
          },
        );
        addAgenteMensagem({ role: 'assistant', content: full || 'Sem resposta.' });
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Falha ao contactar o agente.';
        addAgenteMensagem({ role: 'assistant', content: msg });
      } finally {
        setStreamingText('');
        setAgenteLoading(false);
      }
    },
    [
      addAgenteMensagem,
      agenteLoading,
      dadosPagina,
      mensagens,
      municipioCodigo,
      pageContext.descricao,
      pageContext.pagina,
      setAgenteLoading,
    ],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  if (!mounted) return null;

  return createPortal(
    <>
      {!agenteAberto && (
        <button
          type="button"
          aria-label="Abrir Agente Sinidu"
          onClick={() => setAgenteAberto(true)}
          className="fixed bottom-6 right-6 z-[9999] flex h-[52px] w-[52px] items-center justify-center rounded-full bg-[#1D9E75] text-white shadow-xl shadow-teal-900/50 ring-2 ring-teal-400/30 transition hover:scale-105 hover:bg-[#178f68] animate-pulse"
          title="Agente Sinidu — IA contextual"
        >
          <Sparkles size={22} />
          {agenteNaoLidas > 0 && (
            <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold">
              {agenteNaoLidas > 9 ? '9+' : agenteNaoLidas}
            </span>
          )}
        </button>
      )}

      <aside
        className={`fixed bottom-0 right-0 top-0 z-[9998] flex w-[380px] flex-col border-l border-zinc-800 bg-zinc-950/95 shadow-2xl backdrop-blur-md transition-transform duration-300 ${
          agenteAberto ? 'translate-x-0' : 'translate-x-full pointer-events-none'
        }`}
        aria-hidden={!agenteAberto}
      >
        <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-teal-400">Agente Sinidu</p>
            <p className="text-sm font-medium text-zinc-100">{municipioNome}</p>
            <p className="text-[10px] text-zinc-500">{pageContext.pagina}</p>
          </div>
          <button
            type="button"
            aria-label="Fechar agente"
            onClick={() => setAgenteAberto(false)}
            className="rounded-lg border border-zinc-700 p-2 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
          >
            <X size={16} />
          </button>
        </header>

        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
          {mensagens.length === 0 && !streamingText && (
            <p className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs leading-relaxed text-zinc-400">
              Olá! Estou no módulo <strong className="text-zinc-200">{pageContext.pagina}</strong>.
              Posso explicar como usar a plataforma ou interpretar os dados de {municipioNome}.
            </p>
          )}

          {mensagens.map((msg) => (
            <div
              key={msg.id}
              className={`rounded-xl px-3 py-2 text-xs leading-relaxed ${
                msg.role === 'user'
                  ? 'ml-6 bg-indigo-500/15 text-indigo-100'
                  : msg.proactive
                    ? 'mr-2 border border-amber-500/30 bg-amber-950/20 text-amber-100'
                    : 'mr-6 border border-zinc-800 bg-zinc-900/80 text-zinc-200'
              }`}
            >
              {renderMarkdownLite(msg.content)}
            </div>
          ))}

          {streamingText && (
            <div className="mr-6 rounded-xl border border-zinc-800 bg-zinc-900/80 px-3 py-2 text-xs leading-relaxed text-zinc-200">
              {renderMarkdownLite(streamingText)}
              <span className="ml-1 inline-block h-3 w-1 animate-pulse bg-teal-400" />
            </div>
          )}

          {agenteLoading && !streamingText && (
            <p className="text-[11px] text-zinc-500">Consultando dados do município…</p>
          )}
        </div>

        <div className="border-t border-zinc-800 px-3 py-2">
          <div className="mb-2 flex flex-wrap gap-1.5">
            {perguntasContextuais.map((q) => (
              <button
                key={q}
                type="button"
                disabled={agenteLoading}
                onClick={() => sendMessage(q)}
                className="rounded-full border border-zinc-700 bg-zinc-900/80 px-2.5 py-1 text-[10px] text-zinc-300 hover:border-teal-500/40 hover:text-teal-200 disabled:opacity-50"
              >
                {q}
              </button>
            ))}
          </div>

          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Pergunte sobre dados ou como usar…"
              disabled={agenteLoading}
              className="max-h-[120px] min-h-[40px] flex-1 resize-none rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-100 placeholder:text-zinc-600 focus:border-teal-500/50 focus:outline-none"
            />
            <button
              type="button"
              disabled={agenteLoading || !input.trim()}
              onClick={() => sendMessage(input)}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#1D9E75] text-white hover:bg-[#178f68] disabled:opacity-40"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </aside>
    </>,
    document.body,
  );
}
