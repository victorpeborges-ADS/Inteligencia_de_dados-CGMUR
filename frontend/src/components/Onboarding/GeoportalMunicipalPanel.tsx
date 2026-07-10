'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type GeoportalStatus } from '@/utils/api';
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Globe2,
  Loader2,
  Upload,
  Link2,
  Play,
} from 'lucide-react';

type Props = {
  codigoIbge?: string;
};

export default function GeoportalMunicipalPanel({ codigoIbge }: Props) {
  const [status, setStatus] = useState<GeoportalStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [apiUrl, setApiUrl] = useState('');
  const [apiTipo, setApiTipo] = useState<'geojson_url' | 'arcgis_rest' | 'geoserver_wfs'>('geojson_url');
  const [geoserverTypeName, setGeoserverTypeName] = useState('Limites_Municipais:bairros_2023');
  const fileRef = useRef<HTMLInputElement>(null);

  const loadStatus = useCallback(async () => {
    if (!codigoIbge || codigoIbge.length !== 7) {
      setStatus(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.getGeoportalStatus(codigoIbge);
      setStatus(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao carregar geoportal');
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [codigoIbge]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleUpload = async (file: File) => {
    if (!codigoIbge) return;
    setBusy('upload');
    setError(null);
    setMessage(null);
    try {
      const res = await api.uploadGeoportalMesh(codigoIbge, file);
      setMessage(`${res.feature_count} feições recebidas — clique em Importar para publicar.`);
      await loadStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha no upload');
    } finally {
      setBusy(null);
    }
  };

  const handleRegisterApi = async () => {
    if (!codigoIbge || !apiUrl.trim()) return;
    setBusy('register');
    setError(null);
    setMessage(null);
    try {
      await api.registerGeoportalApi(codigoIbge, {
        tipo: apiTipo,
        url: apiUrl.trim(),
        ...(apiTipo === 'geoserver_wfs'
          ? { geoserver_type_name: geoserverTypeName.trim() }
          : {}),
      });
      setMessage('API municipal registrada.');
      setApiUrl('');
      await loadStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao registrar API');
    } finally {
      setBusy(null);
    }
  };

  const handleImport = async () => {
    if (!codigoIbge) return;
    setBusy('import');
    setError(null);
    setMessage(null);
    try {
      const res = await api.importGeoportalMesh(codigoIbge);
      setMessage(`Malha importada — ${res.bairros ?? 0} bairros publicados.`);
      await loadStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha na importação');
    } finally {
      setBusy(null);
    }
  };

  const handleSyncRegistry = async () => {
    if (!codigoIbge) return;
    setBusy('sync');
    setError(null);
    setMessage(null);
    try {
      const res = await api.syncGeoportalCtmRegistry(codigoIbge, true);
      if (res.error) throw new Error(res.error);
      setMessage(`CTM nacional sincronizado — ${res.bairros ?? 0} bairros.`);
      await loadStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha na sincronização CTM');
    } finally {
      setBusy(null);
    }
  };

  if (!codigoIbge || codigoIbge.length !== 7) {
    return (
      <p className="text-[10px] text-zinc-500 italic">
        Selecione ou valide um município para publicar malha CTM no geoportal Sinidu.
      </p>
    );
  }

  return (
    <div className="rounded-xl border border-teal-900/40 bg-teal-950/10 p-3 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h4 className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-teal-200">
            <Globe2 size={13} />
            Geoportal municipal — CTM
          </h4>
          <p className="mt-1 text-[10px] leading-relaxed text-zinc-400">
            Publique malha de bairros da prefeitura (GeoJSON, shapefile ZIP, ArcGIS REST ou GeoServer WFS).
            Complementa o onboarding sem duplicar o catálogo nacional GeoReDUS.
          </p>
        </div>
        {loading && <Loader2 size={14} className="animate-spin text-teal-400 shrink-0" />}
      </div>

      {status && (
        <div className="grid grid-cols-2 gap-2 text-[10px]">
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 px-2 py-1.5">
            <span className="text-zinc-500">Bairros no mapa</span>
            <p className="font-bold text-zinc-100">{status.bairros_count}</p>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 px-2 py-1.5">
            <span className="text-zinc-500">Fonte malha</span>
            <p className="font-bold text-zinc-100 truncate">{status.malha_fonte || '—'}</p>
          </div>
        </div>
      )}

      {status?.publicacao_ativa && (
        <div className="rounded-lg border border-teal-800/40 bg-teal-950/20 px-2 py-1.5 text-[10px] text-teal-100">
          <span className="font-bold uppercase">{status.publicacao_ativa.status}</span>
          {' · '}
          {status.publicacao_ativa.tipo}
          {status.publicacao_ativa.feature_count != null && ` · ${status.publicacao_ativa.feature_count} feições`}
          {status.publicacao_ativa.mensagem && (
            <p className="mt-0.5 text-zinc-400">{status.publicacao_ativa.mensagem}</p>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <input
          ref={fileRef}
          type="file"
          accept=".geojson,.json,.zip"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleUpload(file);
            e.target.value = '';
          }}
        />
        <button
          type="button"
          disabled={!!busy}
          onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-1 rounded-lg border border-teal-700/50 bg-teal-950/30 px-2.5 py-1.5 text-[10px] font-bold uppercase text-teal-100 hover:bg-teal-900/30 disabled:opacity-50"
        >
          {busy === 'upload' ? <Loader2 size={11} className="animate-spin" /> : <Upload size={11} />}
          Enviar arquivo
        </button>
        <button
          type="button"
          disabled={!!busy || !status?.publicacao_ativa}
          onClick={handleImport}
          className="inline-flex items-center gap-1 rounded-lg bg-teal-700 px-2.5 py-1.5 text-[10px] font-bold uppercase text-white hover:bg-teal-600 disabled:opacity-50"
        >
          {busy === 'import' ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
          Importar
        </button>
        {status?.ctm_registry?.disponivel && (
          <button
            type="button"
            disabled={!!busy}
            onClick={handleSyncRegistry}
            className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 px-2.5 py-1.5 text-[10px] font-bold uppercase text-zinc-300 hover:border-zinc-500 disabled:opacity-50"
          >
            {busy === 'sync' ? <Loader2 size={11} className="animate-spin" /> : <ExternalLink size={11} />}
            CTM catálogo
          </button>
        )}
      </div>

      <div className="space-y-1.5 border-t border-zinc-800/80 pt-2">
        <p className="text-[9px] font-bold uppercase tracking-wider text-zinc-500">API municipal</p>
        <div className="flex flex-wrap gap-1.5">
          <select
            value={apiTipo}
            onChange={(e) => setApiTipo(e.target.value as 'geojson_url' | 'arcgis_rest' | 'geoserver_wfs')}
            className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-[10px] text-zinc-200"
          >
            <option value="geojson_url">GeoJSON URL</option>
            <option value="arcgis_rest">ArcGIS REST</option>
            <option value="geoserver_wfs">GeoServer WFS</option>
          </select>
          <input
            type="url"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            placeholder={
              apiTipo === 'geoserver_wfs'
                ? 'https://fazenda.aracaju.se.gov.br/geoserver/wfs'
                : 'https://geoportal.prefeitura.gov.br/...'
            }
            className="min-w-0 flex-1 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-[10px] text-zinc-200"
          />
          {apiTipo === 'geoserver_wfs' && (
            <input
              type="text"
              value={geoserverTypeName}
              onChange={(e) => setGeoserverTypeName(e.target.value)}
              placeholder="Limites_Municipais:bairros_2023"
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-[10px] text-zinc-200"
            />
          )}
          <button
            type="button"
            disabled={!!busy || !apiUrl.trim() || (apiTipo === 'geoserver_wfs' && !geoserverTypeName.trim())}
            onClick={handleRegisterApi}
            className="inline-flex items-center gap-1 rounded border border-zinc-600 px-2 py-1 text-[10px] font-bold uppercase text-zinc-300"
          >
            {busy === 'register' ? <Loader2 size={11} className="animate-spin" /> : <Link2 size={11} />}
            Registrar
          </button>
        </div>
      </div>

      {status?.acoes_sugeridas?.length ? (
        <ul className="space-y-0.5 text-[9px] text-zinc-500">
          {status.acoes_sugeridas.map((a) => (
            <li key={a}>· {a}</li>
          ))}
        </ul>
      ) : null}

      {message && (
        <p className="flex items-center gap-1 text-[10px] text-emerald-300">
          <CheckCircle2 size={11} /> {message}
        </p>
      )}
      {error && (
        <p className="flex items-center gap-1 text-[10px] text-rose-400">
          <AlertTriangle size={11} /> {error}
        </p>
      )}
    </div>
  );
}
