'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { api, AIProviderOption, ChatMessage, MunicipalAssistantContext, MunicipalDataSource, RagSource } from '@/utils/api';
import { Send, Bot, User, FileText, X, Clock, Cpu, Cloud, Key, Link2, CheckCircle2, AlertCircle, ExternalLink, Sparkles } from 'lucide-react';
import GeoReDusReferenceCard from '@/components/DataCatalog/GeoReDusReferenceCard';
import { useAppStore } from '@/stores/useAppStore';

interface AssistantProps {
  onToggleLayer: (layerName: string) => void;
  onApplyLayers?: (layers: string[]) => void;
  onFocusMap: (coords: [number, number], zoom: number) => void;
  codigoIbge?: string;
}

type ConnectionStatus = 'idle' | 'testing' | 'connected' | 'error';

const DEFAULT_GREETING = (ctx?: MunicipalAssistantContext | null): ChatMessage => ({
  role: 'assistant',
  content: ctx
    ? `Olá! Sou o **Agente Sinidu · Modo Normativo** para **${ctx.municipio.nome}/${ctx.municipio.uf}**. Tenho acesso a perfil IBGE, CAPAG, **Plano Diretor**, score territorial, diagnóstico executivo e documentos normativos. Priorizações e recomendações consideram a legislação urbanística do município. Para alertas e simulações em tempo real, use o modo **Operacional** (botão flutuante). Como posso apoiar a gestão hoje?`
    : 'Olá! Sou o **Agente Sinidu · Modo Normativo**, especializado em gestão de risco urbano e climático. Selecione um município para respostas contextualizadas.',
});

function storageKey(codigoIbge?: string) {
  return `sinidu_assistant_${codigoIbge || 'default'}`;
}

function providerStorageKey() {
  return 'sinidu_ai_provider_prefs';
}

function apiKeysStorageKey() {
  return 'sinidu_ai_api_keys';
}

function loadApiKeys(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(apiKeysStorageKey()) || '{}');
  } catch {
    return {};
  }
}

function saveApiKey(providerId: string, key: string) {
  const keys = loadApiKeys();
  keys[providerId] = key;
  localStorage.setItem(apiKeysStorageKey(), JSON.stringify(keys));
}

function shortSourceLabel(label: string) {
  if (label.includes('12.608')) return 'Lei 12.608';
  if (label.includes('14.026')) return 'Lei 14.026';
  if (label.includes('CONAMA 369')) return 'CONAMA 369';
  if (label.includes('CONAMA 303')) return 'CONAMA 303';
  if (label.includes('1.012')) return 'Portaria MCID 1.012';
  if (label.toLowerCase().includes('georedus')) return 'GeoReDUS';
  if (label.toLowerCase().includes('sinidu')) return 'Sinidu+Clima';
  if (label.toLowerCase().includes('adapta')) return 'AdaptaBrasil';
  if (label.toLowerCase().includes('sedec')) return 'Manual SEDEC';
  return label.length > 28 ? `${label.slice(0, 25)}…` : label;
}

export default function AssistantPanel({ onToggleLayer, onApplyLayers, onFocusMap, codigoIbge }: AssistantProps) {
  const setAgenteModo = useAppStore((s) => s.setAgenteModo);
  const setAgenteAberto = useAppStore((s) => s.setAgenteAberto);
  const [messages, setMessages] = useState<ChatMessage[]>([DEFAULT_GREETING()]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [municipalContext, setMunicipalContext] = useState<MunicipalAssistantContext | null>(null);
  const [sourceModal, setSourceModal] = useState<RagSource | null>(null);
  const [municipalSourceModal, setMunicipalSourceModal] = useState<MunicipalDataSource | null>(null);
  const [providers, setProviders] = useState<AIProviderOption[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('mistral');
  const [selectedModel, setSelectedModel] = useState('');
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('idle');
  const [connectionMessage, setConnectionMessage] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeProvider = providers.find((p) => p.id === selectedProvider);
  const storedApiKey = loadApiKeys()[selectedProvider] || '';

  const refreshProvidersWithKeys = useCallback(async (keys: Record<string, string>) => {
    try {
      const res = await api.getAIProvidersStatus(keys);
      setProviders(res.providers);
    } catch {
      /* mantém lista anterior */
    }
  }, []);

  const runConnectionTest = useCallback(
    async (providerId: string, apiKey: string, model?: string, silent = false) => {
      if (!silent) {
        setConnectionStatus('testing');
        setConnectionMessage('Testando conexão…');
      }
      try {
        const result = await api.testAIProvider(providerId, apiKey, model);
        if (result.ok) {
          if (apiKey) saveApiKey(providerId, apiKey);
          setConnectionStatus('connected');
          setConnectionMessage(
            `${result.message}${result.response_time_ms ? ` (${(result.response_time_ms / 1000).toFixed(1)}s)` : ''}`
          );
          await refreshProvidersWithKeys(loadApiKeys());
          return true;
        }
        setConnectionStatus('error');
        setConnectionMessage(result.message);
        return false;
      } catch (err) {
        setConnectionStatus('error');
        setConnectionMessage(err instanceof Error ? err.message : 'Falha ao testar conexão');
        return false;
      }
    },
    [refreshProvidersWithKeys]
  );

  useEffect(() => {
    const keys = loadApiKeys();
    api.getAIProviders().then(async (res) => {
      if (Object.keys(keys).length > 0) {
        try {
          const statusRes = await api.getAIProvidersStatus(keys);
          setProviders(statusRes.providers);
        } catch {
          setProviders(res.providers);
        }
      } else {
        setProviders(res.providers);
      }

      let providerId = res.default_provider;
      let model = '';
      try {
        const prefs = JSON.parse(localStorage.getItem(providerStorageKey()) || '{}');
        if (prefs.providerId) providerId = prefs.providerId;
        model = prefs.model || '';
      } catch {
        /* ignore */
      }

      const provider = res.providers.find((p) => p.id === providerId) || res.providers[0];
      if (provider) {
        setSelectedProvider(provider.id);
        setSelectedModel(model || provider.default_model);
        setApiKeyInput(keys[provider.id] || '');

        if (provider.is_local) {
          runConnectionTest(provider.id, '', model || provider.default_model, true);
        } else if (keys[provider.id]) {
          runConnectionTest(provider.id, keys[provider.id], model || provider.default_model, true);
        }
      }
    }).catch(() => {
      setProviders([{
        id: 'mistral',
        label: 'Mistral AI',
        description: 'Modelos Mistral via API oficial.',
        available: false,
        is_local: false,
        requires_api_key: true,
        default_model: 'mistral-small-latest',
        models: ['mistral-small-latest', 'mistral-large-latest'],
        privacy_note: 'O contexto RAG e dados municipais são enviados ao provedor externo.',
      }]);
    });
  }, [runConnectionTest]);

  useEffect(() => {
    if (!activeProvider) return;
    if (!activeProvider.models.includes(selectedModel)) {
      setSelectedModel(activeProvider.default_model);
    }
    const keys = loadApiKeys();
    setApiKeyInput(keys[selectedProvider] || '');
    setConnectionStatus('idle');
    setConnectionMessage('');

    if (activeProvider.is_local) {
      runConnectionTest(selectedProvider, '', selectedModel, true);
    } else if (keys[selectedProvider]) {
      runConnectionTest(selectedProvider, keys[selectedProvider], selectedModel, true);
    }
  }, [selectedProvider, activeProvider, selectedModel, runConnectionTest]);

  useEffect(() => {
    localStorage.setItem(
      providerStorageKey(),
      JSON.stringify({ providerId: selectedProvider, model: selectedModel })
    );
  }, [selectedProvider, selectedModel]);

  useEffect(() => {
    if (!codigoIbge) {
      setMunicipalContext(null);
      return;
    }
    api.getMunicipalAssistantContext(codigoIbge)
      .then(setMunicipalContext)
      .catch(() => setMunicipalContext(null));
  }, [codigoIbge]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey(codigoIbge));
      if (raw) {
        const parsed = JSON.parse(raw) as ChatMessage[];
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMessages(parsed);
          return;
        }
      }
      setMessages([DEFAULT_GREETING(municipalContext)]);
    } catch {
      setMessages([DEFAULT_GREETING(municipalContext)]);
    }
  }, [codigoIbge, municipalContext?.codigo_ibge]);

  useEffect(() => {
    try {
      localStorage.setItem(storageKey(codigoIbge), JSON.stringify(messages));
    } catch {
      /* ignore */
    }
  }, [messages, codigoIbge]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const resolveApiKey = () => {
    if (activeProvider?.is_local) return undefined;
    return (apiKeyInput || storedApiKey || '').trim() || undefined;
  };

  const handleConnect = () => {
    if (activeProvider?.is_local) {
      runConnectionTest(selectedProvider, '', selectedModel);
      return;
    }
    if (!apiKeyInput.trim()) {
      setConnectionStatus('error');
      setConnectionMessage('Cole sua API key antes de conectar.');
      return;
    }
    runConnectionTest(selectedProvider, apiKeyInput.trim(), selectedModel);
  };

  const handleSend = useCallback(
    async (text: string) => {
      if (!text.trim()) return;

      if (activeProvider?.requires_api_key && connectionStatus !== 'connected' && !activeProvider.available) {
        setMessages((prev) => [
          ...prev,
          { role: 'user', content: text },
          {
            role: 'assistant',
            content: 'Conecte-se ao provedor de IA com sua **API key** (botão **Conectar** acima) antes de enviar mensagens.',
          },
        ]);
        return;
      }

      const userMsg: ChatMessage = { role: 'user', content: text };
      const historyForApi = messages.filter((m) => m.role === 'user' || m.role === 'assistant');
      setMessages((prev) => [...prev, userMsg]);
      setInput('');
      setLoading(true);

      try {
        const res = await api.chatAssistant(
          text,
          historyForApi,
          codigoIbge,
          selectedProvider,
          selectedModel || undefined,
          resolveApiKey(),
        );

        const extras: ChatMessage[] = [];
        if (res.crosswalk_rationale && res.recommended_layers?.length) {
          extras.push({
            role: 'assistant',
            content: `**Cruzamento no mapa:** ${res.recommended_layers.join(' · ')}\n\n_${res.crosswalk_rationale}_`,
          });
        }
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: res.response,
            sourceUrl: res.source_url,
            ragSources: res.rag_sources,
            municipalSources: res.municipal_sources,
            responseTimeMs: res.response_time_ms,
            aiProvider: res.ai_provider,
            aiModel: res.ai_model,
          },
          ...extras,
        ]);

        if (res.recommended_layers?.length) {
          if (onApplyLayers) onApplyLayers(res.recommended_layers);
          else res.recommended_layers.forEach((layer) => onToggleLayer(layer));
        } else if (res.suggested_layer) {
          onToggleLayer(res.suggested_layer);
        }
        if (res.coordinates) onFocusMap(res.coordinates, res.zoom || 13);
      } catch (err) {
        console.error('Error sending message:', err);
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: 'Ops, encontrei um erro de comunicação. Verifique se o backend está online.' },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [
      messages,
      codigoIbge,
      selectedProvider,
      selectedModel,
      apiKeyInput,
      storedApiKey,
      activeProvider,
      connectionStatus,
      onToggleLayer,
      onApplyLayers,
      onFocusMap,
    ]
  );

  const uniqueRagLabels = (sources?: RagSource[]) => {
    if (!sources?.length) return [];
    const seen = new Set<string>();
    return sources.filter((s) => {
      if (seen.has(s.source_label)) return false;
      seen.add(s.source_label);
      return true;
    });
  };

  const providerLabel = (id?: string) => providers.find((p) => p.id === id)?.label || id;

  const quickQuestions = municipalContext?.suggested_questions?.length
    ? municipalContext.suggested_questions
    : [
        'Quais bairros possuem maior risco?',
        'O que diz a Lei 12.608 sobre defesa civil?',
        'Qual a nota CAPAG deste município?',
        'Histórico de desastres',
      ];

  const showApiKeyField = activeProvider && !activeProvider.is_local;

  return (
    <div className="relative flex flex-col h-[75vh] bg-zinc-950/40 border border-border rounded-xl overflow-hidden">
      <div className="px-3 py-2 border-b border-teal-900/40 bg-teal-950/15 flex items-center justify-between gap-2 flex-wrap">
        <div className="min-w-0">
          <p className="text-[10px] font-extrabold uppercase tracking-wide text-teal-300">
            Agente Sinidu · Modo Normativo
          </p>
          <p className="text-[9px] text-zinc-400 leading-snug">
            Legislação e RAG. Dados vivos do município: modo Operacional (FAB).
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setAgenteModo('operacional');
            setAgenteAberto(true);
          }}
          className="inline-flex items-center gap-1.5 rounded-md border border-teal-700/50 bg-teal-900/30 px-2.5 py-1 text-[10px] font-semibold text-teal-100 hover:bg-teal-900/50"
        >
          <Sparkles size={12} />
          Abrir Operacional
        </button>
      </div>
      {municipalContext && (
        <div className="px-3 py-2 border-b border-indigo-900/40 bg-indigo-950/20 flex flex-col gap-1">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-[10px] font-extrabold uppercase tracking-wide text-indigo-200">
              {municipalContext.municipio.nome}/{municipalContext.municipio.uf}
            </span>
            <div className="flex flex-wrap gap-1">
              {municipalContext.score_sinidu != null && (
                <span className="rounded-full border border-indigo-700/50 bg-indigo-900/30 px-2 py-0.5 text-[9px] text-indigo-200">
                  Score {municipalContext.score_sinidu}
                </span>
              )}
              {municipalContext.nota_capag && (
                <span className="rounded-full border border-emerald-700/50 bg-emerald-900/20 px-2 py-0.5 text-[9px] text-emerald-200">
                  CAPAG {municipalContext.nota_capag}
                </span>
              )}
              {municipalContext.maturidade && (
                <span className="rounded-full border border-amber-700/50 bg-amber-900/20 px-2 py-0.5 text-[9px] text-amber-200">
                  {municipalContext.maturidade} {municipalContext.maturidade_score ?? ''}/100
                </span>
              )}
            </div>
          </div>
          <p className="text-[9px] leading-snug text-zinc-400 line-clamp-2">{municipalContext.headline}</p>
          <p className="text-[8px] text-zinc-500">
            {municipalContext.sources.length} fontes integradas
            {municipalContext.tem_diagnostico ? ' · diagnóstico salvo' : ''}
            {municipalContext.tem_relatorio ? ' · relatório PDF' : ''}
          </p>
          {municipalContext.georedus_url && (
            <GeoReDusReferenceCard
              codigoIbge={municipalContext.codigo_ibge}
              municipioNome={municipalContext.municipio.nome}
            />
          )}
        </div>
      )}
      <div className="px-3 py-2 border-b border-zinc-900 bg-zinc-950/90 flex flex-col gap-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[9px] uppercase font-bold text-zinc-500 tracking-wider shrink-0">Motor IA</span>
          <select
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            className="flex-1 min-w-[130px] bg-zinc-900 border border-zinc-800 rounded-md px-2 py-1 text-[10px] text-zinc-200 focus:outline-none focus:border-indigo-600"
          >
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.is_local ? '🖥 ' : '☁ '}
                {p.label}
              </option>
            ))}
          </select>
          {activeProvider && activeProvider.models.length > 0 && (
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="flex-1 min-w-[110px] bg-zinc-900 border border-zinc-800 rounded-md px-2 py-1 text-[10px] text-zinc-300 focus:outline-none focus:border-indigo-600"
            >
              {activeProvider.models.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          )}
        </div>

        {showApiKeyField && (
          <div className="flex gap-1.5 items-center">
            <div className="relative flex-1">
              <Key size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="password"
                value={apiKeyInput}
                onChange={(e) => {
                  setApiKeyInput(e.target.value);
                  setConnectionStatus('idle');
                }}
                onKeyDown={(e) => { if (e.key === 'Enter') handleConnect(); }}
                placeholder={`API key ${activeProvider.label}…`}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-md pl-7 pr-2 py-1.5 text-[10px] text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-indigo-600"
                autoComplete="off"
              />
            </div>
            <button
              type="button"
              onClick={handleConnect}
              disabled={connectionStatus === 'testing'}
              className="shrink-0 inline-flex items-center gap-1 bg-indigo-700 hover:bg-indigo-600 disabled:opacity-50 text-white text-[10px] font-bold px-2.5 py-1.5 rounded-md transition-colors"
            >
              <Link2 size={11} />
              {connectionStatus === 'testing' ? '…' : 'Conectar'}
            </button>
          </div>
        )}

        {!showApiKeyField && activeProvider?.is_local && (
          <button
            type="button"
            onClick={handleConnect}
            disabled={connectionStatus === 'testing'}
            className="self-start inline-flex items-center gap-1 text-[9px] text-zinc-400 hover:text-zinc-200"
          >
            <Link2 size={10} />
            {connectionStatus === 'testing' ? 'Verificando Ollama…' : 'Verificar Ollama local'}
          </button>
        )}

        {connectionStatus === 'connected' && (
          <p className="text-[9px] text-emerald-400 flex items-center gap-1">
            <CheckCircle2 size={10} />
            {connectionMessage || 'Conectado'}
          </p>
        )}
        {connectionStatus === 'error' && (
          <p className="text-[9px] text-red-400 flex items-start gap-1">
            <AlertCircle size={10} className="mt-0.5 shrink-0" />
            {connectionMessage}
          </p>
        )}

        {activeProvider && connectionStatus !== 'connected' && connectionStatus !== 'error' && (
          <p className="text-[9px] text-zinc-500 leading-snug flex items-start gap-1">
            {activeProvider.is_local ? (
              <Cpu size={10} className="mt-0.5 shrink-0" />
            ) : (
              <Cloud size={10} className="mt-0.5 shrink-0" />
            )}
            {activeProvider.is_local
              ? activeProvider.privacy_note
              : 'A chave fica no seu navegador e é usada só para gerar respostas. Embeddings RAG permanecem locais.'}
          </p>
        )}
      </div>

      <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4 text-xs">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`flex gap-2 max-w-[85%] ${m.role === 'user' ? 'self-end flex-row-reverse' : 'self-start'}`}
          >
            <div className={`p-2 rounded-full border h-8 w-8 flex items-center justify-center shrink-0 ${
              m.role === 'user' ? 'bg-zinc-800 border-zinc-700 text-zinc-300' : 'bg-indigo-950/60 border-indigo-800 text-indigo-400'
            }`}>
              {m.role === 'user' ? <User size={14} /> : <Bot size={14} />}
            </div>
            <div className={`p-3 rounded-xl border leading-relaxed ${
              m.role === 'user' ? 'bg-zinc-900 border-zinc-800 text-zinc-200 rounded-tr-none' : 'bg-card border-zinc-800/80 text-zinc-300 rounded-tl-none'
            }`}>
              <div
                className="prose prose-invert max-w-none text-[11px] flex flex-col gap-2"
                dangerouslySetInnerHTML={{
                  __html: m.content
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/### (.*?)\n/g, '<h4 class="font-extrabold text-sm text-indigo-400 mt-1">$1</h4>')
                    .replace(/#### (.*?)\n/g, '<h5 class="font-bold text-xs text-zinc-200 mt-1">$1</h5>')
                    .replace(/\* (.*?)\n/g, '<li class="ml-3 list-disc text-zinc-300">$1</li>'),
                }}
              />
              {m.role === 'assistant' && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {m.aiProvider && (
                    <span className="text-[9px] text-violet-400/90 font-medium">
                      {providerLabel(m.aiProvider)}
                      {m.aiModel ? ` · ${m.aiModel.split('/').pop()}` : ''}
                    </span>
                  )}
                  {m.responseTimeMs != null && (
                    <span className="inline-flex items-center gap-1 text-[9px] text-zinc-500">
                      <Clock size={10} />
                      {(m.responseTimeMs / 1000).toFixed(1)}s
                    </span>
                  )}
                  {uniqueRagLabels(m.ragSources).map((src) => (
                    <button
                      key={`${src.source}-${src.chunk_idx}`}
                      type="button"
                      onClick={() => setSourceModal(src)}
                      className="inline-flex items-center gap-1 text-[9px] font-bold bg-emerald-950/50 border border-emerald-800/60 text-emerald-300 hover:bg-emerald-900/40 px-2 py-0.5 rounded-full"
                    >
                      RAG: {shortSourceLabel(src.source_label)}
                    </button>
                  ))}
                  {(m.municipalSources || []).map((src) => (
                    <button
                      key={src.id}
                      type="button"
                      onClick={() => setMunicipalSourceModal(src)}
                      className="inline-flex items-center gap-1 text-[9px] font-bold bg-sky-950/50 border border-sky-800/60 text-sky-300 hover:bg-sky-900/40 px-2 py-0.5 rounded-full"
                    >
                      {src.tipo === 'OFICIAL' ? 'Oficial' : 'Derivado'}: {shortSourceLabel(src.label)}
                    </button>
                  ))}
                  {m.sourceUrl && (
                    <a
                      href={m.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-[9px] font-bold text-sky-300 hover:text-sky-200"
                    >
                      <ExternalLink size={10} />
                      {m.sourceUrl.includes('redus.org.br') ? 'GeoReDUS ↗' : 'Siconfi.IA ↗'}
                    </a>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-2 self-start max-w-[85%]">
            <div className="p-2 rounded-full bg-indigo-950/60 border border-indigo-800 text-indigo-400 h-8 w-8 flex items-center justify-center animate-pulse">
              <Bot size={14} />
            </div>
            <div className="p-2.5 rounded-xl border border-zinc-800 bg-card/50 text-zinc-400 italic rounded-tl-none animate-pulse">
              Consultando dados municipais + RAG + {activeProvider?.label || 'LLM'}…
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {messages.length === 1 && (
        <div className="px-4 py-2 border-t border-zinc-900 flex flex-col gap-1.5 bg-zinc-950/80">
          <span className="text-[9px] uppercase font-bold text-zinc-500 tracking-wider">Sugestões</span>
          <div className="flex flex-wrap gap-1.5">
            {quickQuestions.map((q) => (
              <button key={q} type="button" onClick={() => handleSend(q)} className="text-[9px] bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-400 hover:text-zinc-200 py-1 px-2 rounded-full">
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="p-3 border-t border-zinc-900 bg-card/60 backdrop-blur-md flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSend(input); }}
          placeholder="Pergunte ao Assistente Municipal…"
          className="flex-1 bg-zinc-950 border border-border rounded-lg px-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500/50"
        />
        <button type="button" onClick={() => handleSend(input)} disabled={loading} className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg p-2 text-xs font-bold shrink-0 shadow-md">
          <Send size={14} />
        </button>
      </div>

      {municipalSourceModal && (
        <div className="absolute inset-0 z-20 bg-black/70 flex items-end sm:items-center justify-center p-3">
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl w-full max-w-lg max-h-[70%] flex flex-col shadow-2xl">
            <div className="flex items-center justify-between p-3 border-b border-zinc-800">
              <div className="flex items-center gap-2 text-sky-300">
                <FileText size={14} />
                <span className="text-xs font-bold">{municipalSourceModal.label}</span>
              </div>
              <button type="button" onClick={() => setMunicipalSourceModal(null)} className="text-zinc-500 hover:text-zinc-200">
                <X size={16} />
              </button>
            </div>
            <div className="p-3 overflow-y-auto text-[11px] text-zinc-300 leading-relaxed whitespace-pre-wrap">
              {municipalSourceModal.snippet}
            </div>
            <div className="p-3 border-t border-zinc-800 text-[9px] text-zinc-500 flex items-center justify-between gap-2">
              <span>{municipalSourceModal.tipo} · Sinidu+Clima</span>
              {municipalSourceModal.url && (
                <a href={municipalSourceModal.url} target="_blank" rel="noreferrer" className="text-sky-400 hover:text-sky-300">
                  Fonte externa ↗
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      {sourceModal && (
        <div className="absolute inset-0 z-20 bg-black/70 flex items-end sm:items-center justify-center p-3">
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl w-full max-w-lg max-h-[70%] flex flex-col shadow-2xl">
            <div className="flex items-center justify-between p-3 border-b border-zinc-800">
              <div className="flex items-center gap-2 text-emerald-300">
                <FileText size={14} />
                <span className="text-xs font-bold">{sourceModal.source_label}</span>
              </div>
              <button type="button" onClick={() => setSourceModal(null)} className="text-zinc-500 hover:text-zinc-200">
                <X size={16} />
              </button>
            </div>
            <div className="p-3 overflow-y-auto text-[11px] text-zinc-300 leading-relaxed whitespace-pre-wrap">
              {sourceModal.content}
            </div>
            <div className="p-3 border-t border-zinc-800 text-[9px] text-zinc-500">
              Trecho #{sourceModal.chunk_idx + 1} · similaridade {(sourceModal.similarity * 100).toFixed(0)}%
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
