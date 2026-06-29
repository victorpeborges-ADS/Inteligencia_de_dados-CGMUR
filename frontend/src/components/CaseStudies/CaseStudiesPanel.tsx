'use client';

import { useState, useEffect } from 'react';
import { api, SuccessCase } from '@/utils/api';
import { Search, MapPin, Award, BookOpen } from 'lucide-react';

export default function CaseStudiesPanel({ municipioNome }: { municipioNome?: string }) {
  const [query, setQuery] = useState('');
  const [cases, setCases] = useState<SuccessCase[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await api.searchCases(query);
      setCases(data);
    } catch (err) {
      console.error('Error searching cases:', err);
    } finally {
      setLoading(false);
    }
  };

  // Seed default cases for the selected municipality.
  useEffect(() => {
    const loadDefaultCases = async () => {
      setLoading(true);
      try {
        const data = await api.searchCases(municipioNome || 'drenagem');
        setCases(data);
      } catch (err) {
        console.error('Error loading default cases:', err);
      } finally {
        setLoading(false);
      }
    };
    loadDefaultCases();
  }, [municipioNome]);

  return (
    <div className="flex flex-col gap-4 overflow-y-auto max-h-[85vh] pr-2">
      {/* Search Input */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(); }}
            placeholder="Buscar casos (ex: encostas, drenagem)..."
            className="w-full bg-zinc-950 border border-border rounded-lg pl-8 pr-3 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500/50"
          />
          <Search size={14} className="absolute left-2.5 top-3 text-zinc-500" />
        </div>
        <button
          onClick={handleSearch}
          className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-3 py-2 text-xs font-bold transition-all shadow-md"
        >
          Pesquisar
        </button>
      </div>

      {/* Cases List */}
      {loading ? (
        <div className="flex flex-col gap-3 animate-pulse">
          {[1, 2].map((i) => (
            <div key={i} className="h-44 bg-zinc-900 rounded-xl border border-zinc-800"></div>
          ))}
        </div>
      ) : cases.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 text-zinc-500 text-xs gap-2">
          <BookOpen size={24} className="text-zinc-600" />
          <span>Nenhum caso encontrado para a pesquisa.</span>
        </div>
      ) : (
        <div className="flex flex-col gap-3 text-xs">
          {cases.map((c) => (
            <div
              key={c.id}
              className="bg-card/45 border border-border p-4 rounded-xl hover:border-zinc-700/80 transition-all flex flex-col gap-3"
            >
              {/* Header */}
              <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                <div className="flex items-center gap-1.5 font-extrabold text-zinc-100">
                  <MapPin size={14} className="text-indigo-400" />
                  <span>{c.municipio} - {c.uf}</span>
                </div>
                {c.relevance_score !== undefined && c.relevance_score > 0 && (
                  <span className="text-[9px] bg-indigo-950/60 border border-indigo-800/80 text-indigo-400 py-0.5 px-2 rounded-full font-bold">
                    Relevância: {c.relevance_score}
                  </span>
                )}
              </div>

              {/* Contents */}
              <div className="flex flex-col gap-2.5">
                <div>
                  <span className="text-[9px] text-zinc-500 uppercase font-bold block mb-0.5">Problema Territorial</span>
                  <p className="text-[10px] text-zinc-300 leading-relaxed">{c.problema}</p>
                </div>
                
                <div>
                  <span className="text-[9px] text-zinc-500 uppercase font-bold block mb-0.5">Solução Adotada</span>
                  <p className="text-[10px] text-emerald-400 leading-relaxed font-medium">{c.solucao}</p>
                </div>

                <div className="bg-zinc-950/40 p-2 rounded border border-zinc-800/60">
                  <span className="text-[9px] text-zinc-500 uppercase font-bold block mb-0.5 flex items-center gap-1">
                    <Award size={10} className="text-yellow-500" /> Impacto e Resultado obtido
                  </span>
                  <p className="text-[10px] text-zinc-300 leading-relaxed italic">{c.resultado}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
