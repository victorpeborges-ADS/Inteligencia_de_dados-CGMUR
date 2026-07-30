'use client';

import { useState } from 'react';
import { api } from '@/utils/api';
import { MapPin, Save, Loader2 } from 'lucide-react';

type Props = {
  codigoIbge: string;
  onCreated?: () => void;
  onToast?: (title: string, message: string) => void;
};

/** Formulário mínimo de registro em campo (Defesa Civil) — Fase 21c.4. */
export default function FieldFloodEventForm({ codigoIbge, onCreated, onToast }: Props) {
  const [tipo, setTipo] = useState('Alagamento Urbano');
  const [fenomeno, setFenomeno] = useState<'pluvial' | 'fluvial' | 'misto'>('pluvial');
  const [severidade, setSeveridade] = useState('media');
  const [inicio, setInicio] = useState(() => new Date().toISOString().slice(0, 16));
  const [lat, setLat] = useState('-8.05');
  const [lng, setLng] = useState('-34.88');
  const [referencia, setReferencia] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    setSaving(true);
    try {
      await api.createObservedFloodEvent({
        codigoIbge,
        tipo,
        fenomeno,
        severidade,
        inicioEm: new Date(inicio).toISOString(),
        lat: Number(lat),
        lng: Number(lng),
        referencia: referencia || undefined,
      });
      onToast?.('Evento registrado', 'Ground truth oficial (Defesa Civil) gravado.');
      onCreated?.();
    } catch (e) {
      onToast?.('Falha ao registrar', e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card/40 p-3 flex flex-col gap-2">
      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-zinc-300">
        <MapPin size={12} className="text-teal-400" />
        Registro em campo (Defesa Civil)
      </div>
      <p className="text-[9px] text-zinc-500 leading-snug">
        Ponto com data/hora e severidade — entra como rótulo oficial no ML (fonte=defesa_civil).
      </p>
      <div className="grid grid-cols-2 gap-2 text-[10px]">
        <label className="flex flex-col gap-0.5">
          <span className="text-zinc-500">Tipo</span>
          <select
            className="rounded border border-border bg-zinc-950 px-1.5 py-1"
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
          >
            <option>Alagamento Urbano</option>
            <option>Inundação</option>
            <option>Enxurrada</option>
          </select>
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-zinc-500">Fenômeno</span>
          <select
            className="rounded border border-border bg-zinc-950 px-1.5 py-1"
            value={fenomeno}
            onChange={(e) => setFenomeno(e.target.value as typeof fenomeno)}
          >
            <option value="pluvial">Pluvial</option>
            <option value="fluvial">Fluvial</option>
            <option value="misto">Misto</option>
          </select>
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-zinc-500">Severidade</span>
          <select
            className="rounded border border-border bg-zinc-950 px-1.5 py-1"
            value={severidade}
            onChange={(e) => setSeveridade(e.target.value)}
          >
            <option value="baixa">Baixa</option>
            <option value="media">Média</option>
            <option value="alta">Alta</option>
            <option value="critica">Crítica</option>
          </select>
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-zinc-500">Início</span>
          <input
            type="datetime-local"
            className="rounded border border-border bg-zinc-950 px-1.5 py-1"
            value={inicio}
            onChange={(e) => setInicio(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-zinc-500">Latitude</span>
          <input
            className="rounded border border-border bg-zinc-950 px-1.5 py-1 font-mono"
            value={lat}
            onChange={(e) => setLat(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-zinc-500">Longitude</span>
          <input
            className="rounded border border-border bg-zinc-950 px-1.5 py-1 font-mono"
            value={lng}
            onChange={(e) => setLng(e.target.value)}
          />
        </label>
      </div>
      <label className="flex flex-col gap-0.5 text-[10px]">
        <span className="text-zinc-500">Referência / boletim</span>
        <input
          className="rounded border border-border bg-zinc-950 px-1.5 py-1"
          value={referencia}
          onChange={(e) => setReferencia(e.target.value)}
          placeholder="Ex.: Boletim DC 28/05"
        />
      </label>
      <button
        type="button"
        disabled={saving}
        onClick={submit}
        className="mt-1 flex items-center justify-center gap-1.5 rounded-lg border border-teal-500/40 bg-teal-500/15 px-2 py-1.5 text-[10px] font-bold uppercase text-teal-200 hover:bg-teal-500/25 disabled:opacity-60"
      >
        {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
        {saving ? 'Salvando…' : 'Registrar evento'}
      </button>
    </div>
  );
}
