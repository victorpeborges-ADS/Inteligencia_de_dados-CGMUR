'use client';

import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import { api, type MonitoringMapItem } from '@/utils/api';
import { MAP_BASEMAPS } from '@/config/theme';
import { useAppStore } from '@/stores/useAppStore';

const NIVEL_HEX: Record<string, string> = {
  VERDE: '#22c55e',
  AMARELO: '#eab308',
  LARANJA: '#f97316',
  VERMELHO: '#ef4444',
};

function FitBrazil({ items }: { items: MonitoringMapItem[] }) {
  const map = useMap();
  useEffect(() => {
    const withCoords = items.filter((i) => i.lat != null && i.lng != null);
    if (withCoords.length === 0) return;
    const lats = withCoords.map((i) => i.lat!);
    const lngs = withCoords.map((i) => i.lng!);
    map.fitBounds(
      [
        [Math.min(...lats), Math.min(...lngs)],
        [Math.max(...lats), Math.max(...lngs)],
      ],
      { padding: [24, 24], maxZoom: 6 },
    );
  }, [items, map]);
  return null;
}

interface Props {
  highlightIbge?: string;
  onSelect?: (item: MonitoringMapItem) => void;
}

export default function MonitoringMiniMap({ highlightIbge, onSelect }: Props) {
  const colorMode = useAppStore((s) => s.colorMode);
  const [items, setItems] = useState<MonitoringMapItem[]>([]);
  const [stats, setStats] = useState({ total: 0, comGeometria: 0, comCoordenadas: 0 });

  const load = () => {
    api
      .getMonitoringMapOverview()
      .then((overview) => {
        setItems(overview.municipios);
        setStats({
          total: overview.total_municipios,
          comGeometria: overview.com_geometria,
          comCoordenadas: overview.com_coordenadas,
        });
      })
      .catch(console.error);
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  const center: [number, number] = [-8.5, -38.5];

  return (
    <div>
      <div className="h-[200px] w-full overflow-hidden rounded-xl border border-zinc-700">
        <MapContainer center={center} zoom={5} className="h-full w-full" scrollWheelZoom={false}>
          <TileLayer url={MAP_BASEMAPS[colorMode]} />
          <FitBrazil items={items} />
          {items.map((m) => {
            if (m.lat == null || m.lng == null) return null;
            const color = NIVEL_HEX[m.nivel] || NIVEL_HEX.VERDE;
            const radius = m.codigo_ibge === highlightIbge ? 10 : 6;
            return (
              <CircleMarker
                key={m.codigo_ibge}
                center={[m.lat, m.lng]}
                radius={radius}
                pathOptions={{
                  color: m.codigo_ibge === highlightIbge ? '#fff' : color,
                  fillColor: color,
                  fillOpacity: 0.85,
                  weight: m.codigo_ibge === highlightIbge ? 3 : 1,
                }}
                eventHandlers={{ click: () => onSelect?.(m) }}
              >
                <Popup>
                  <strong>
                    {m.nome} — {m.uf}
                  </strong>
                  <br />
                  Nível: {m.nivel}
                  <br />
                  Risco: {(m.risk_probability * 100).toFixed(0)}%
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>
      <p className="mt-1 text-[9px] text-zinc-600">
        {stats.comCoordenadas} de {stats.total} municípios no mapa
        {stats.comGeometria < stats.total && ` · ${stats.comGeometria} com geometria IBGE`}
        {' · '}
        Verde · Amarelo · Laranja · Vermelho
      </p>
    </div>
  );
}
