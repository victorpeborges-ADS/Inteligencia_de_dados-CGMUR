'use client';

import { useEffect, useRef, useState } from 'react';
import { api, type MunicipalityOption } from '@/utils/api';

const API_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || '';
const MAP_ID = process.env.NEXT_PUBLIC_GOOGLE_MAP_ID || 'DEMO_MAP_ID';

type ViewMode = 'earth' | 'street';

interface Props {
  selectedMunicipio: string;
  municipalities: MunicipalityOption[];
  onMunicipioChange: (codigoIbge: string) => void;
  mapFocus: [number, number];
}

declare global {
  interface Window {
    google?: any;
    __gmapsLoading?: Promise<void>;
  }
  // eslint-disable-next-line no-var
  var google: any;
}

function loadGoogleMaps(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('SSR'));
  if (window.google?.maps) return Promise.resolve();
  if (window.__gmapsLoading) return window.__gmapsLoading;

  if (!API_KEY) return Promise.reject(new Error('NO_KEY'));

  window.__gmapsLoading = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${API_KEY}&v=weekly&libraries=maps,marker`;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Falha ao carregar Google Maps'));
    document.head.appendChild(script);
  });
  return window.__gmapsLoading;
}

export default function Map3DGoogleContainer({
  selectedMunicipio,
  municipalities,
  onMunicipioChange,
  mapFocus,
}: Props) {
  const mapDivRef = useRef<HTMLDivElement>(null);
  const streetDivRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const panoramaRef = useRef<any>(null);
  const dataLayerRef = useRef<any>(null);

  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('earth');
  const [tilt, setTilt] = useState(55);

  useEffect(() => {
    loadGoogleMaps()
      .then(() => setReady(true))
      .catch((e) => setError(e.message === 'NO_KEY' ? 'NO_KEY' : e.message));
  }, []);

  useEffect(() => {
    if (!ready || !mapDivRef.current || !window.google?.maps) return;

    const center = { lat: mapFocus[0], lng: mapFocus[1] };

    if (!mapRef.current) {
      mapRef.current = new google.maps.Map(mapDivRef.current, {
        center,
        zoom: 14,
        mapId: MAP_ID,
        mapTypeId: 'satellite',
        tilt,
        heading: 25,
        disableDefaultUI: false,
        gestureHandling: 'greedy',
        zoomControl: true,
        mapTypeControl: true,
        streetViewControl: false,
        fullscreenControl: true,
        rotateControl: true,
      });

      dataLayerRef.current = new google.maps.Data({ map: mapRef.current });
      dataLayerRef.current.setStyle({
        fillColor: '#6366f1',
        fillOpacity: 0.15,
        strokeColor: '#818cf8',
        strokeWeight: 1.5,
      });
    }

    mapRef.current.setCenter(center);
    mapRef.current.setTilt(viewMode === 'earth' ? tilt : 0);
    mapRef.current.setZoom(14);
  }, [ready, mapFocus, viewMode, tilt]);

  useEffect(() => {
    if (!ready || !mapRef.current || !dataLayerRef.current) return;
    api.getLayerGeoJSON('bairros', selectedMunicipio)
      .then((geojson) => {
        const layer = dataLayerRef.current!;
        const map = mapRef.current;
        layer.forEach((f: any) => layer.remove(f));
        layer.addGeoJson(geojson);

        if (map && geojson?.features?.length) {
          const bounds = new google.maps.LatLngBounds();
          layer.forEach((feature: any) => {
            feature.getGeometry()?.forEachLatLng((latLng: any) => bounds.extend(latLng));
          });
          if (!bounds.isEmpty()) {
            map.fitBounds(bounds, { top: 48, right: 320, bottom: 48, left: 48 });
            window.setTimeout(() => {
              const z = map.getZoom();
              if (typeof z === 'number' && z > 15) map.setZoom(15);
              map.setTilt(viewMode === 'earth' ? tilt : 0);
            }, 400);
          }
        }
      })
      .catch(() => {
        dataLayerRef.current?.forEach((f: any) => dataLayerRef.current!.remove(f));
      });
  }, [ready, selectedMunicipio, viewMode, tilt]);

  useEffect(() => {
    if (!ready || viewMode !== 'street' || !streetDivRef.current || !window.google?.maps) return;

    const position = { lat: mapFocus[0], lng: mapFocus[1] };
    if (!panoramaRef.current) {
      panoramaRef.current = new google.maps.StreetViewPanorama(streetDivRef.current, {
        position,
        pov: { heading: 180, pitch: 0 },
        zoom: 1,
        addressControl: true,
        linksControl: true,
        panControl: true,
        enableCloseButton: false,
      });
    } else {
      panoramaRef.current.setPosition(position);
    }

    const svc = new google.maps.StreetViewService();
    svc.getPanorama({ location: position, radius: 800 }, (data: any, status: string) => {
      if (status === 'OK' && data?.location?.latLng) {
        panoramaRef.current?.setPosition(data.location.latLng);
      }
    });
  }, [ready, viewMode, mapFocus]);

  if (error === 'NO_KEY') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-zinc-950 p-8 text-center">
        <p className="text-lg font-bold text-zinc-100">Google Maps 3D</p>
        <p className="max-w-md text-sm text-zinc-400">
          Configure <code className="text-teal-300">NEXT_PUBLIC_GOOGLE_MAPS_API_KEY</code> no{' '}
          <code className="text-zinc-500">docker-compose.yml</code> para vista satélite 3D e Street View
          (Recife, SP e demais cidades com cobertura Google).
        </p>
        <a
          href="https://console.cloud.google.com/google/maps-apis/credentials"
          target="_blank"
          rel="noreferrer"
          className="rounded-lg bg-teal-600 px-4 py-2 text-xs font-bold uppercase text-white hover:bg-teal-500"
        >
          Criar API key
        </a>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center bg-zinc-950 p-6 text-sm text-rose-200">
        Erro Google Maps: {error}
      </div>
    );
  }

  return (
    <div className="relative h-full w-full min-h-[400px]">
      <div
        ref={mapDivRef}
        className={`absolute inset-0 ${viewMode === 'street' ? 'hidden' : 'block'}`}
      />
      <div
        ref={streetDivRef}
        className={`absolute inset-0 ${viewMode === 'street' ? 'block' : 'hidden'}`}
      />

      {!ready && (
        <div className="absolute inset-0 flex items-center justify-center bg-zinc-950 text-sm text-zinc-400">
          Carregando Google Maps…
        </div>
      )}

      <div className="absolute right-4 top-24 z-10 w-72 space-y-2 rounded-xl border border-teal-500/30 bg-zinc-950/95 p-3 shadow-2xl backdrop-blur-md">
        <label className="block text-[10px] font-extrabold uppercase text-teal-300">Município</label>
        <select
          value={selectedMunicipio}
          onChange={(e) => onMunicipioChange(e.target.value)}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-bold text-zinc-100"
        >
          {municipalities.map((m) => (
            <option key={m.codigo_ibge} value={m.codigo_ibge}>
              {m.nome} - {m.uf}
            </option>
          ))}
        </select>

        <div className="flex gap-1 pt-1">
          <button
            type="button"
            onClick={() => setViewMode('earth')}
            className={`flex-1 rounded-lg py-2 text-[10px] font-bold uppercase ${
              viewMode === 'earth'
                ? 'bg-teal-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Satélite 3D
          </button>
          <button
            type="button"
            onClick={() => setViewMode('street')}
            className={`flex-1 rounded-lg py-2 text-[10px] font-bold uppercase ${
              viewMode === 'street'
                ? 'bg-teal-600 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Street View
          </button>
        </div>

        {viewMode === 'earth' && (
          <>
            <label className="block text-[10px] font-extrabold uppercase text-zinc-500">
              Inclinação: {tilt}°
            </label>
            <input
              type="range"
              min={0}
              max={67}
              step={1}
              value={tilt}
              onChange={(e) => {
                const v = Number(e.target.value);
                setTilt(v);
                mapRef.current?.setTilt(v);
              }}
              className="w-full accent-teal-500"
            />
          </>
        )}

        <p className="text-[9px] leading-snug text-zinc-600">
          Google Maps · arraste para rotacionar · malha de bairros sobreposta
        </p>
      </div>
    </div>
  );
}
