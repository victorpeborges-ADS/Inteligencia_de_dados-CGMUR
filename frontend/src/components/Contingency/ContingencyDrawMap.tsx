'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMapEvents, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { MAP_BASEMAPS } from '@/config/theme';
import { useAppStore } from '@/stores/useAppStore';

interface Props {
  mapFocus: [number, number];
  zonas: any[];
  rotas: any[];
  pontosApoio: any[];
  onZonasChange: (zones: any[]) => void;
  onPontosChange: (points: any[]) => void;
  drawMode: 'zone' | 'support' | 'view';
}

function DrawHandler({
  drawMode,
  onZone,
  onPoint,
}: {
  drawMode: 'zone' | 'support' | 'view';
  onZone: (geom: any) => void;
  onPoint: (lat: number, lng: number) => void;
}) {
  useMapEvents({
    click(e) {
      if (drawMode === 'support') {
        onPoint(e.latlng.lat, e.latlng.lng);
      }
    },
  });
  return null;
}

export default function ContingencyDrawMap({
  mapFocus,
  zonas,
  rotas,
  pontosApoio,
  onZonasChange,
  onPontosChange,
  drawMode,
}: Props) {
  const colorMode = useAppStore((s) => s.colorMode);
  const mapRef = useRef<L.Map | null>(null);
  const [drawReady, setDrawReady] = useState(
    () => typeof window !== 'undefined' && Boolean((window as any).L?.Draw || (L as any).Draw),
  );
  const zonasRef = useRef(zonas);
  zonasRef.current = zonas;

  useEffect(() => {
    if (drawReady || drawMode !== 'zone') return;
    if ((L as any).Draw || (window as any).L?.Draw) {
      setDrawReady(true);
      return;
    }
    if (!document.querySelector('link[data-leaflet-draw-css]')) {
      const css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css';
      css.setAttribute('data-leaflet-draw-css', '1');
      document.head.appendChild(css);
    }

    const existing = document.querySelector('script[data-leaflet-draw-js]') as HTMLScriptElement | null;
    if (existing) {
      if ((L as any).Draw) setDrawReady(true);
      else existing.addEventListener('load', () => setDrawReady(true), { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js';
    script.setAttribute('data-leaflet-draw-js', '1');
    script.onload = () => setDrawReady(true);
    document.head.appendChild(script);
  }, [drawMode, drawReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !drawReady || drawMode !== 'zone') return;
    if (!(L as any).Control?.Draw && !(L as any).Draw) return;

    const drawn = new (L as any).FeatureGroup();
    map.addLayer(drawn);

    const drawControl = new (L as any).Control.Draw({
      draw: {
        polygon: { allowIntersection: false, showArea: true },
        polyline: false,
        rectangle: false,
        circle: false,
        marker: false,
        circlemarker: false,
      },
      edit: { featureGroup: drawn },
    });
    map.addControl(drawControl);

    const onCreated = (e: any) => {
      const layer = e.layer;
      drawn.addLayer(layer);
      const geo = layer.toGeoJSON();
      const current = zonasRef.current;
      onZonasChange([
        ...current,
        {
          nome: `Zona ${current.length + 1}`,
          capacidade: 300,
          prioridade: current.length + 1,
          geometry: geo.geometry,
        },
      ]);
    };

    map.on((L as any).Draw.Event.CREATED, onCreated);

    return () => {
      map.off((L as any).Draw.Event.CREATED, onCreated);
      map.removeControl(drawControl);
      map.removeLayer(drawn);
    };
  }, [drawMode, drawReady, onZonasChange]);

  const handlePoint = useCallback(
    (lat: number, lng: number) => {
      onPontosChange([
        ...pontosApoio,
        {
          nome: `Ponto ${pontosApoio.length + 1}`,
          tipo: 'abrigo',
          fonte: 'manual',
          coordinates: [lng, lat],
          geometry: { type: 'Point', coordinates: [lng, lat] },
        },
      ]);
    },
    [pontosApoio, onPontosChange],
  );

  const zonesGeoJSON = {
    type: 'FeatureCollection',
    features: zonas.map((z, i) => ({
      type: 'Feature',
      properties: { nome: z.nome },
      geometry: z.geometry,
    })),
  };

  const routesGeoJSON = {
    type: 'FeatureCollection',
    features: rotas
      .filter((r) => r.geojson?.geometry)
      .map((r) => ({
        type: 'Feature',
        properties: {
          nome: r.nome,
          aproximada: Boolean(r.aproximada || r.fonte_rota === 'fallback' || r.malha_viaria === false),
        },
        geometry: r.geojson.geometry,
      })),
  };

  return (
    <div className="h-[280px] w-full overflow-hidden rounded-xl border border-zinc-700">
      <MapContainer
        center={mapFocus}
        zoom={12}
        className="h-full w-full"
        ref={mapRef}
      >
        <TileLayer url={MAP_BASEMAPS[colorMode]} />
        <DrawHandler drawMode={drawMode} onZone={() => {}} onPoint={handlePoint} />
        {zonas.length > 0 && (
          <GeoJSON
            data={zonesGeoJSON as any}
            style={{ color: '#f97316', fillColor: '#fb923c', fillOpacity: 0.35, weight: 2 }}
          />
        )}
        {rotas.length > 0 && (
          <GeoJSON
            data={routesGeoJSON as any}
            style={(feature) => {
              const approx = feature?.properties?.aproximada;
              return {
                color: approx ? '#fbbf24' : '#38bdf8',
                weight: approx ? 3 : 4,
                dashArray: approx ? '8 6' : undefined,
              };
            }}
          />
        )}
        {pontosApoio.map((p, i) => (
          <Marker key={i} position={[p.coordinates[1], p.coordinates[0]]}>
            <Popup>{p.nome}</Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
