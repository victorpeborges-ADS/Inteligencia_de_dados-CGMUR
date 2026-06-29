'use client';

import { useEffect, useState } from 'react';
import { MapContainer as LeafletMap, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import { api } from '@/utils/api';
import { getLayerStyle, getSimulationFeatureStyle } from './layerStyles';

// Fix Leaflet marker asset paths
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface MapProps {
  activeLayers: string[];
  mapFocus: [number, number];
  zoom: number;
  simGeoJSON: any;
  simContours?: any;
  simFlowPaths?: any;
  selectedMunicipio: string;
}

type LegendItem = {
  color: string;
  label: string;
};

const layerTitles: Record<string, string> = {
  municipio: 'Limite Municipal',
  bairros: 'Bairros',
  infraestrutura: 'Equipamentos e Redes',
  socioeconomico: 'Socioeconômico',
  cobertura: 'Uso do Solo',
  vulnerabilidade: 'Vulnerabilidade',
  inundacao: 'Risco de Inundação',
  alertas: 'Alertas',
  desastres: 'Desastres',
  saneamento_drenagem: 'Saneamento e Drenagem',
  adaptacao_climatica: 'Adaptação Climática',
  prioridade_planejamento: 'Prioridade de Planejamento',
  lacunas_dados: 'Lacunas de Dados',
  saude_risco: 'Saúde × Risco',
  seguranca_publica: 'Segurança Pública',
  vulnerabilidade_multidimensional: 'Vulnerabilidade Multidimensional',
};

const legendByLayer: Record<string, LegendItem[]> = {
  municipio: [{ color: '#38bdf8', label: 'Limite municipal' }],
  bairros: [{ color: '#6366f1', label: 'Malha de bairros' }],
  infraestrutura: [{ color: '#a78bfa', label: 'Equipamentos e redes' }],
  socioeconomico: [
    { color: '#22c55e', label: 'Renda alta' },
    { color: '#eab308', label: 'Renda média' },
    { color: '#f97316', label: 'Renda baixa' }
  ],
  cobertura: [
    { color: '#10b981', label: 'Vegetação / parque' },
    { color: '#0ea5e9', label: 'Corpo d\'água' },
    { color: '#71717a', label: 'Área construída/outros' }
  ],
  vulnerabilidade: [
    { color: '#7f1d1d', label: 'IVC alto' },
    { color: '#f97316', label: 'IVC médio' },
    { color: '#fde047', label: 'IVC baixo' }
  ],
  inundacao: [
    { color: '#075985', label: 'Risco alto' },
    { color: '#0284c7', label: 'Risco médio' },
    { color: '#7dd3fc', label: 'Risco baixo' }
  ],
  alertas: [
    { color: '#f43f5e', label: 'Muito alto' },
    { color: '#f97316', label: 'Alto' },
    { color: '#eab308', label: 'Moderado/baixo' }
  ],
  desastres: [{ color: '#ef4444', label: 'Evento S2ID' }],
  saneamento_drenagem: [
    { color: '#0e7490', label: 'Drenagem crítica' },
    { color: '#06b6d4', label: 'Atenção' },
    { color: '#a5f3fc', label: 'Monitoramento' }
  ],
  adaptacao_climatica: [
    { color: '#16a34a', label: 'Capacidade alta' },
    { color: '#facc15', label: 'Capacidade média' },
    { color: '#f97316', label: 'Capacidade baixa' }
  ],
  prioridade_planejamento: [
    { color: '#be123c', label: 'Prioridade alta' },
    { color: '#9333ea', label: 'Prioridade média' },
    { color: '#c4b5fd', label: 'Prioridade baixa' }
  ],
  lacunas_dados: [
    { color: '#16a34a', label: 'Maturidade alta' },
    { color: '#f59e0b', label: 'Maturidade média' },
    { color: '#e11d48', label: 'Maturidade baixa' }
  ],
  saude_risco: [
    { color: '#16a34a', label: 'Cobertura adequada' },
    { color: '#eab308', label: 'Atenção' },
    { color: '#ef4444', label: 'Crítica em área de risco' }
  ],
  seguranca_publica: [
    { color: '#7f1d1d', label: 'Alta incidência / 100k hab' },
    { color: '#f97316', label: 'Média' },
    { color: '#fde68a', label: 'Baixa' }
  ],
  vulnerabilidade_multidimensional: [
    { color: '#581c87', label: 'VM crítica + flag multidimensional' },
    { color: '#a855f7', label: 'VM alta' },
    { color: '#e9d5ff', label: 'VM moderada/baixa' }
  ]
};

// Controller to dynamically update map view coordinates and zoom
function MapController({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom, { animate: true, duration: 1.0 });
  }, [center, zoom, map]);
  return null;
}

export default function MapContainer({
  activeLayers,
  mapFocus,
  zoom,
  simGeoJSON,
  simContours,
  simFlowPaths,
  selectedMunicipio,
}: MapProps) {
  const [layerData, setLayerData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);

  // Fetch all selected data layers so they can be overlaid on the same map.
  useEffect(() => {
    setLayerData({});

    if (activeLayers.length === 0) {
      return;
    }
    
    const loadLayers = async () => {
      setLoading(true);
      try {
        const entries = await Promise.all(
          activeLayers.map(async (layerName) => {
            const data = await api.getLayerGeoJSON(layerName, selectedMunicipio);
            return [layerName, data] as const;
          })
        );
        setLayerData(Object.fromEntries(entries));
      } catch (err) {
        console.error('Error loading layers:', err);
      } finally {
        setLoading(false);
      }
    };
    
    loadLayers();
  }, [activeLayers, selectedMunicipio]);

  // Color functions for thematic vector layers
  const getLayerStyleForFeature = (layerName: string, feature: any) => getLayerStyle(layerName, feature);

  // Popup contents depending on layer properties
  const onEachFeature = (layerName: string) => (feature: any, layer: any) => {
    const props = feature.properties || {};
    let popupContent = '<div class="p-1 font-sans text-xs min-w-[180px]">';
    popupContent += `<p class="mb-1 text-[10px] font-bold uppercase tracking-wide text-indigo-300">${layerTitles[layerName] || layerName}</p>`;
    
    if (props.nome) {
      popupContent += `<h4 class="font-bold text-sm text-zinc-100 border-b border-zinc-700 pb-1 mb-1">${props.nome}</h4>`;
    }
    
    if (props.tipo) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Tipo:</span> <span class="capitalize">${props.tipo}</span></p>`;
      if (props.subgrupo) popupContent += `<p class="mb-1"><span class="text-zinc-400">Subgrupo:</span> <span class="capitalize text-zinc-300">${props.subgrupo.replace('_', ' ')}</span></p>`;
    }
    
    if (props.codigo_bairro) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Código Bairro:</span> ${props.codigo_bairro}</p>`;
    }
    
    if (props.populacao) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">População:</span> ${props.populacao.toLocaleString()}</p>`;
    }
    
    if (props.renda_media) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Renda Média:</span> R$ ${props.renda_media.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>`;
    }

    if (props.densidade_demografica) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Densidade:</span> ${props.densidade_demografica.toLocaleString()} hab/km²</p>`;
    }
    
    if (props.nivel_alerta) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Nível do Alerta:</span> <span class="font-bold text-red-400">${props.nivel_alerta}</span></p>`;
      if (props.descricao) popupContent += `<p class="mt-2 text-zinc-300 italic border-l-2 border-amber-500 pl-2 text-[10px]">${props.descricao}</p>`;
    }
    
    if (props.classe_uso) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Uso do Solo (MapBiomas):</span> <span class="font-semibold text-zinc-300">${props.classe_uso}</span></p>`;
    }

    if (props.indice_vulnerabilidade !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">IVC:</span> <span class="font-bold text-rose-300">${props.indice_vulnerabilidade}</span></p>`;
    }

    if (props.indice_risco_inundacao !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">IRI:</span> <span class="font-bold text-sky-300">${props.indice_risco_inundacao}</span></p>`;
    }

    if (props.capacidade_adaptacao !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Adaptação:</span> <span class="font-bold text-emerald-300">${props.capacidade_adaptacao}</span></p>`;
    }

    if (props.prioridade_planejamento !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Prioridade:</span> <span class="font-bold text-fuchsia-300">${props.prioridade_planejamento}</span></p>`;
    }

    if (props.risco_drenagem !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Risco drenagem:</span> <span class="font-bold text-cyan-300">${props.risco_drenagem}</span></p>`;
    }

    if (props.maturidade_dados !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Maturidade dos dados:</span> <span class="font-bold text-indigo-300">${props.maturidade_dados}%</span></p>`;
      if (props.lacunas_prioritarias) {
        popupContent += `<p class="mb-1"><span class="text-zinc-400">Lacunas:</span> <span class="text-zinc-300">${props.lacunas_prioritarias}</span></p>`;
      }
    }

    if (props.leitos_sus !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Leitos SUS:</span> ${props.leitos_sus}</p>`;
    }
    if (props.bairro) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Bairro:</span> ${props.bairro}</p>`;
    }
    if (props.cobertura_classe) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Cobertura:</span> <span class="font-bold">${props.cobertura_classe}</span></p>`;
    }
    if (props.distancia_maior_risco_km !== undefined && props.distancia_maior_risco_km !== null) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Dist. maior risco:</span> ${props.distancia_maior_risco_km} km</p>`;
    }
    if (props.taxa_violenta_100k !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Ocorrências violentas / 100k:</span> ${props.taxa_violenta_100k}</p>`;
    }
    if (props.indice_vm !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Índice VM:</span> <span class="font-bold text-purple-300">${props.indice_vm}</span></p>`;
    }
    if (props.vulnerabilidade_multidimensional) {
      popupContent += `<p class="mb-1 font-bold text-fuchsia-300">⚠ Vulnerabilidade multidimensional</p>`;
    }

    if (props.score_componentes) {
      popupContent += `
        <div class="mt-2 rounded-md border border-fuchsia-500/30 bg-fuchsia-950/30 p-2">
          <p class="mb-1 text-[10px] font-bold uppercase text-fuchsia-200">Por que este score?</p>
          <p class="text-[10px] text-zinc-300">Vulnerabilidade: +${props.score_componentes.vulnerabilidade_pct} pts</p>
          <p class="text-[10px] text-zinc-300">Inundação: +${props.score_componentes.inundacao_pct} pts</p>
          <p class="text-[10px] text-zinc-300">Déficit de adaptação: +${props.score_componentes.deficit_adaptacao_pct} pts</p>
          ${props.score_explicacao ? `<p class="mt-1 text-[9px] text-zinc-500">${props.score_explicacao}</p>` : ''}
        </div>
      `;
    }

    if (props.qualidade_dado) {
      const qualityColor = props.qualidade_dado === 'Oficial' ? 'text-emerald-300 border-emerald-500/40 bg-emerald-950/30' : props.qualidade_dado === 'Estimado' ? 'text-amber-300 border-amber-500/40 bg-amber-950/30' : 'text-sky-300 border-sky-500/40 bg-sky-950/30';
      popupContent += `<p class="mt-2"><span class="rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase ${qualityColor}">${props.qualidade_dado}</span></p>`;
    }

    if (props.fonte_referencia) {
      popupContent += `<p class="mt-2 border-t border-zinc-800 pt-1 text-[10px] text-zinc-500">${props.fonte_referencia}</p>`;
    }

    popupContent += '</div>';
    layer.bindPopup(popupContent);
  };

  const pointToLayer = (layerName: string) => (feature: any, latlng: L.LatLngExpression) => {
    if (layerName === 'saude_risco') {
      const cls = feature?.properties?.cobertura_classe;
      const color = cls === 'ADEQUADA' ? '#16a34a' : cls === 'ATENCAO' ? '#eab308' : '#ef4444';
      return L.circleMarker(latlng, { radius: 8, fillColor: color, color: '#fff', weight: 2, fillOpacity: 0.9 });
    }
    const color = layerName === 'desastres' ? '#ef4444' : '#a78bfa';
    return L.circleMarker(latlng, {
      radius: layerName === 'desastres' ? 7 : 5,
      fillColor: color,
      color: '#f8fafc',
      weight: 1.5,
      opacity: 1,
      fillOpacity: 0.85
    });
  };

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden border border-border bg-zinc-950">
      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 bg-background/60 backdrop-blur-sm z-[1000] flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
            <span className="text-zinc-300 text-sm font-medium">Carregando dados espaciais...</span>
          </div>
        </div>
      )}

      <LeafletMap
        center={mapFocus}
        zoom={zoom}
        className="w-full h-full"
        zoomControl={false}
      >
        <MapController center={mapFocus} zoom={zoom} />
        
        {/* Custom Dark-Themed Basemap */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {/* Dynamic PostGIS geospatial layers, rendered in selection order for overlays */}
        {activeLayers.map((layerName) => (
          layerData[layerName] && (
            <GeoJSON
              key={`${layerName}-${layerData[layerName].features?.length || 0}`}
              data={layerData[layerName]}
              style={(feature) => getLayerStyleForFeature(layerName, feature)}
              pointToLayer={pointToLayer(layerName)}
              onEachFeature={onEachFeature(layerName)}
            />
          )
        ))}

        {/* Manchas de simulação por profundidade */}
        {simGeoJSON && (
          <GeoJSON
            key={`sim-${JSON.stringify(simGeoJSON).slice(0, 80)}`}
            data={simGeoJSON}
            style={(feature) => getSimulationFeatureStyle(feature)}
            onEachFeature={(feature, layer) => {
              const props = feature.properties || {};
              let content = `<div class="p-2 font-sans text-xs">
                <h4 class="font-bold text-sm text-zinc-100 mb-1 border-b border-zinc-700 pb-1">${props.name || 'Mancha Simulada'}</h4>`;
              if (props.temp_increase_celsius) {
                content += `<p class="text-red-400 font-semibold">Aumento de Temp: +${props.temp_increase_celsius}°C</p>`;
              }
              if (props.precipitation_mm) {
                content += `<p class="text-sky-400 font-semibold">Chuva: ${props.precipitation_mm} mm</p>`;
              }
              if (props.water_level_m) {
                content += `<p class="text-sky-300">Cota simulada: ${props.water_level_m} m</p>`;
              }
              if (props.depth_band) {
                content += `<p class="text-blue-300">Faixa: ${props.depth_band}</p>`;
              }
              if (props.intensity_pct) {
                content += `<p class="text-sky-400 font-semibold">Impermeabilização: +${props.intensity_pct}%</p>`;
              }
              if (props.description) content += `<p class="mt-1 text-zinc-400 text-[10px]">${props.description}</p>`;
              content += '</div>';
              layer.bindPopup(content);
            }}
          />
        )}

        {/* Curvas de nível (DEM SRTM) */}
        {simContours?.features?.length > 0 && (
          <GeoJSON
            key={`contours-${simContours.features.length}`}
            data={simContours}
            style={() => ({
              fillOpacity: 0,
              color: '#a3e635',
              weight: 1.2,
              opacity: 0.85,
            })}
            onEachFeature={(feature, layer) => {
              const elev = feature.properties?.elevation_m;
              if (elev != null) {
                layer.bindTooltip(`Cota ${elev} m`, { sticky: true, className: 'text-[10px]' });
              }
            }}
          />
        )}

        {/* Linhas de escoamento */}
        {simFlowPaths?.features?.length > 0 && (
          <GeoJSON
            key={`flow-${simFlowPaths.features.length}`}
            data={simFlowPaths}
            style={() => ({
              fillOpacity: 0,
              color: '#22d3ee',
              weight: 2,
              opacity: 0.9,
              dashArray: '6,4',
            })}
          />
        )}

      </LeafletMap>

      {/* Legenda territorial — município é selecionado no header global */}
      <div className="absolute right-4 top-24 bottom-4 z-[1100] flex w-72 flex-col overflow-hidden rounded-xl border border-zinc-700/80 bg-zinc-950/95 text-[11px] text-zinc-200 shadow-2xl shadow-black/50 backdrop-blur-md pointer-events-auto">
        <div className="shrink-0 border-b border-zinc-800 bg-zinc-950/95 px-4 py-3">
          <h5 className="text-sm font-extrabold text-zinc-50">Legenda Territorial</h5>
          <p className="mt-0.5 text-[10px] text-zinc-500">Camadas do município selecionado no header.</p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 pr-5">
          {activeLayers.length === 0 && !simGeoJSON && (
            <span className="text-zinc-500 italic">Nenhuma camada ativada no momento.</span>
          )}
          {activeLayers.map((layerName) => (
            <div key={layerName} className="mb-3 last:mb-0">
              <p className="mb-1.5 text-[10px] font-extrabold uppercase tracking-wider text-indigo-300">
                {layerTitles[layerName] || layerName}
              </p>
              <div className="grid grid-cols-1 gap-1.5">
                {(legendByLayer[layerName] || []).map((item) => (
                  <div key={`${layerName}-${item.label}`} className="flex items-center gap-2">
                    <span
                      className="h-3.5 w-3.5 shrink-0 rounded-sm border border-white/30 shadow"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="leading-tight text-zinc-300">{item.label}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {simGeoJSON && (
            <div className="mt-3 border-t border-zinc-800 pt-3 flex flex-col gap-2">
              <p className="mb-1 text-[10px] font-extrabold uppercase tracking-wider text-indigo-300">Simulação hidrológica</p>
              <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm border border-sky-900 bg-sky-400/50" />Alagamento superficial</div>
              <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm border border-sky-800 bg-sky-600/60" />Alagamento moderado</div>
              <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm border border-indigo-950 bg-indigo-900/70" />Alagamento crítico</div>
              <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm border border-red-900 bg-red-600/55" />Deslizamento / ilha de calor</div>
              {simContours?.features?.length > 0 && (
                <div className="flex items-center gap-2"><span className="h-0.5 w-4 bg-lime-400" />Curvas de nível (DEM)</div>
              )}
              {simFlowPaths?.features?.length > 0 && (
                <div className="flex items-center gap-2"><span className="h-0.5 w-4 border-t-2 border-dashed border-cyan-400" />Escoamento superficial</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
