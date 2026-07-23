'use client';

import { useEffect, useMemo, useState } from 'react';
import { Bookmark, MapPin, Navigation, Trash2 } from 'lucide-react';
import { api } from '@/utils/api';
import {
  SCENARIO_PRESETS,
  bairrosFromGeoJSON,
  loadBookmarks,
  makeBookmark,
  normalizeInBounds,
  saveBookmarks,
  type BairroNavItem,
  type CameraBookmark,
} from '@/utils/mapNavAssist';

type MapLibreMap = any;

type Props = {
  map: MapLibreMap | null;
  mapReady: boolean;
  selectedMunicipio: string;
  mapFocus: [number, number];
  bearing: number;
  className?: string;
};

export default function Map3DNavAssist({
  map,
  mapReady,
  selectedMunicipio,
  mapFocus,
  bearing,
  className = '',
}: Props) {
  const [bairros, setBairros] = useState<BairroNavItem[]>([]);
  const [bairroSel, setBairroSel] = useState('');
  const [bookmarks, setBookmarks] = useState<CameraBookmark[]>([]);
  const [bookmarkName, setBookmarkName] = useState('');
  const [loadingBairros, setLoadingBairros] = useState(false);
  const [camPos, setCamPos] = useState<{ lng: number; lat: number }>({
    lng: mapFocus[1],
    lat: mapFocus[0],
  });

  const cityBounds = useMemo((): [[number, number], [number, number]] | null => {
    if (!bairros.length) {
      const [lat, lng] = mapFocus;
      return [
        [lng - 0.08, lat - 0.08],
        [lng + 0.08, lat + 0.08],
      ];
    }
    let minLng = Infinity;
    let minLat = Infinity;
    let maxLng = -Infinity;
    let maxLat = -Infinity;
    for (const b of bairros) {
      if (!b.bounds) continue;
      minLng = Math.min(minLng, b.bounds[0][0]);
      minLat = Math.min(minLat, b.bounds[0][1]);
      maxLng = Math.max(maxLng, b.bounds[1][0]);
      maxLat = Math.max(maxLat, b.bounds[1][1]);
    }
    if (!Number.isFinite(minLng)) return null;
    return [
      [minLng, minLat],
      [maxLng, maxLat],
    ];
  }, [bairros, mapFocus]);

  useEffect(() => {
    setBookmarks(loadBookmarks(selectedMunicipio));
    setBairroSel('');
  }, [selectedMunicipio]);

  useEffect(() => {
    if (!selectedMunicipio) return;
    let cancelled = false;
    setLoadingBairros(true);
    api
      .getLayerGeoJSON('bairros', selectedMunicipio)
      .then((fc) => {
        if (cancelled) return;
        const items = bairrosFromGeoJSON(fc);
        setBairros(items);
        if (items[0]) setBairroSel(items[0].nome);
      })
      .catch(() => {
        if (!cancelled) setBairros([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingBairros(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedMunicipio]);

  useEffect(() => {
    if (!map || !mapReady) return;
    const sync = () => {
      const c = map.getCenter();
      setCamPos({ lng: c.lng, lat: c.lat });
    };
    sync();
    map.on('move', sync);
    return () => {
      map.off('move', sync);
    };
  }, [map, mapReady]);

  const flyToBairro = () => {
    if (!map || !bairroSel) return;
    const item = bairros.find((b) => b.nome === bairroSel);
    if (!item) return;
    if (item.bounds) {
      map.fitBounds(item.bounds, {
        padding: { top: 80, bottom: 100, left: 280, right: 240 },
        maxZoom: 15.2,
        pitch: 62,
        bearing: map.getBearing(),
        duration: 1600,
      });
    } else {
      map.flyTo({
        center: item.center,
        zoom: 14.5,
        pitch: 62,
        duration: 1600,
      });
    }
  };

  const applyPreset = (presetId: string) => {
    if (!map) return;
    const preset = SCENARIO_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    const c = map.getCenter();
    map.easeTo({
      center: [c.lng, c.lat],
      zoom: preset.zoom,
      pitch: preset.pitch,
      bearing: preset.bearing,
      duration: 1400,
    });
  };

  const saveCurrentBookmark = () => {
    if (!map) return;
    const c = map.getCenter();
    const bm = makeBookmark(bookmarkName || `Cena ${bookmarks.length + 1}`, {
      center: [c.lng, c.lat],
      zoom: map.getZoom(),
      pitch: map.getPitch(),
      bearing: map.getBearing(),
    });
    const next = [bm, ...bookmarks].slice(0, 20);
    setBookmarks(next);
    saveBookmarks(selectedMunicipio, next);
    setBookmarkName('');
  };

  const restoreBookmark = (bm: CameraBookmark) => {
    if (!map) return;
    map.flyTo({
      center: bm.center,
      zoom: bm.zoom,
      pitch: bm.pitch,
      bearing: bm.bearing,
      duration: 1400,
    });
  };

  const removeBookmark = (id: string) => {
    const next = bookmarks.filter((b) => b.id !== id);
    setBookmarks(next);
    saveBookmarks(selectedMunicipio, next);
  };

  const mini = cityBounds
    ? normalizeInBounds(camPos.lng, camPos.lat, cityBounds)
    : { x: 0.5, y: 0.5 };

  return (
    <div
      className={`map-ui-chrome rounded-xl border border-indigo-500/30 bg-zinc-950/95 p-3 shadow-2xl backdrop-blur-md ${className}`}
    >
      <p className="mb-2 flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wider text-indigo-300">
        <Navigation size={12} />
        Navegação
      </p>

      <div className="mb-3 flex gap-2">
        <div
          className="relative h-20 w-20 shrink-0 overflow-hidden rounded-lg border border-zinc-700 bg-zinc-900"
          title="Minimapa — posição da câmera"
        >
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,#1e293b_0%,#09090b_70%)]" />
          <div className="absolute inset-1 rounded border border-dashed border-zinc-600/60" />
          <div
            className="absolute h-0 w-0"
            style={{
              left: `${mini.x * 100}%`,
              top: `${mini.y * 100}%`,
              transform: `translate(-50%, -50%) rotate(${bearing}deg)`,
            }}
          >
            <div
              className="h-0 w-0 border-l-[5px] border-r-[5px] border-b-[10px] border-l-transparent border-r-transparent border-b-rose-400 drop-shadow"
              style={{ marginLeft: -5, marginTop: -8 }}
            />
          </div>
          <span className="absolute bottom-0.5 left-0.5 text-[7px] font-bold uppercase text-zinc-500">
            N
          </span>
        </div>

        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-[9px] font-bold uppercase text-zinc-500">Cena rápida</p>
          <div className="flex flex-col gap-1">
            {SCENARIO_PRESETS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => applyPreset(p.id)}
                className="rounded-md bg-zinc-800 px-2 py-1 text-left text-[9px] font-bold uppercase text-zinc-300 hover:bg-zinc-700 hover:text-white"
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <label className="mb-1 block text-[9px] font-bold uppercase text-zinc-500">
        Voar até o bairro
      </label>
      <div className="mb-3 flex gap-1">
        <select
          value={bairroSel}
          onChange={(e) => setBairroSel(e.target.value)}
          disabled={loadingBairros || bairros.length === 0}
          className="min-w-0 flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-1.5 py-1.5 text-[10px] text-zinc-200"
        >
          {bairros.length === 0 ? (
            <option value="">{loadingBairros ? 'Carregando…' : 'Sem bairros'}</option>
          ) : (
            bairros.map((b) => (
              <option key={b.nome} value={b.nome}>
                {b.nome}
              </option>
            ))
          )}
        </select>
        <button
          type="button"
          onClick={flyToBairro}
          disabled={!bairroSel || !map}
          className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-1.5 text-[9px] font-extrabold uppercase text-white hover:bg-indigo-500 disabled:opacity-40"
          title="Voar até o bairro"
        >
          <MapPin size={12} />
          Ir
        </button>
      </div>

      <label className="mb-1 flex items-center gap-1 text-[9px] font-bold uppercase text-zinc-500">
        <Bookmark size={10} />
        Bookmarks de câmera
      </label>
      <div className="mb-2 flex gap-1">
        <input
          value={bookmarkName}
          onChange={(e) => setBookmarkName(e.target.value)}
          placeholder="Nome da cena"
          className="min-w-0 flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-1.5 py-1.5 text-[10px] text-zinc-200 placeholder:text-zinc-600"
        />
        <button
          type="button"
          onClick={saveCurrentBookmark}
          disabled={!map}
          className="rounded-md bg-zinc-700 px-2 py-1.5 text-[9px] font-extrabold uppercase text-zinc-100 hover:bg-zinc-600 disabled:opacity-40"
        >
          Salvar
        </button>
      </div>
      <ul className="max-h-24 space-y-1 overflow-y-auto pr-0.5">
        {bookmarks.length === 0 && (
          <li className="text-[9px] italic text-zinc-600">Nenhum bookmark ainda</li>
        )}
        {bookmarks.map((bm) => (
          <li
            key={bm.id}
            className="flex items-center gap-1 rounded-md border border-zinc-800 bg-zinc-900/80 px-1.5 py-1"
          >
            <button
              type="button"
              onClick={() => restoreBookmark(bm)}
              className="min-w-0 flex-1 truncate text-left text-[10px] font-semibold text-zinc-200 hover:text-indigo-200"
              title="Restaurar câmera"
            >
              {bm.name}
            </button>
            <button
              type="button"
              onClick={() => removeBookmark(bm.id)}
              className="rounded p-0.5 text-zinc-500 hover:text-rose-300"
              title="Remover"
            >
              <Trash2 size={11} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
