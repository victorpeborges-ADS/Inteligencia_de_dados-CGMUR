export type LayerStyle = {
  fillColor: string;
  fillOpacity: number;
  color: string;
  weight: number;
  radius?: number;
};

export function scoreColor(value: number, palette: [string, string, string]): string {
  if (value >= 0.66) return palette[0];
  if (value >= 0.33) return palette[1];
  return palette[2];
}

export function getLayerStyle(layerName: string, feature: any): LayerStyle {
  const props = feature?.properties || {};

  if (layerName === 'municipio') {
    return { fillColor: 'transparent', fillOpacity: 0, color: '#38bdf8', weight: 3 };
  }

  if (layerName === 'cobertura') {
    const cls = props.classe_uso;
    if (cls === 'Vegetação / Floresta') {
      return { fillColor: '#10b981', fillOpacity: 0.45, color: '#047857', weight: 1 };
    }
    if (cls === "Corpo d'água") {
      return { fillColor: '#0ea5e9', fillOpacity: 0.55, color: '#0369a1', weight: 1 };
    }
    return { fillColor: '#71717a', fillOpacity: 0.35, color: '#3f3f46', weight: 1 };
  }

  if (layerName === 'alertas') {
    const lvl = props.nivel_alerta;
    if (lvl === 'MUITO_ALTO') {
      return { fillColor: '#f43f5e', fillOpacity: 0.45, color: '#e11d48', weight: 2 };
    }
    if (lvl === 'ALTO') {
      return { fillColor: '#f97316', fillOpacity: 0.42, color: '#ea580c', weight: 2 };
    }
    return { fillColor: '#eab308', fillOpacity: 0.38, color: '#ca8a04', weight: 1.5 };
  }

  if (layerName === 'vulnerabilidade') {
    const value = Number(props.indice_vulnerabilidade || 0);
    return { fillColor: scoreColor(value, ['#7f1d1d', '#f97316', '#fde047']), fillOpacity: 0.45, color: '#fecaca', weight: 1.3 };
  }

  if (layerName === 'inundacao') {
    const value = Number(props.indice_risco_inundacao || 0);
    return { fillColor: scoreColor(value, ['#075985', '#0284c7', '#7dd3fc']), fillOpacity: 0.42, color: '#bae6fd', weight: 1.3 };
  }

  if (layerName === 'socioeconomico') {
    const value = props.classe_renda === 'ALTA' ? 0.8 : props.classe_renda === 'MEDIA' ? 0.5 : 0.2;
    return { fillColor: scoreColor(value, ['#22c55e', '#eab308', '#f97316']), fillOpacity: 0.34, color: '#fef3c7', weight: 0.8 };
  }

  if (layerName === 'adaptacao_climatica') {
    const value = Number(props.capacidade_adaptacao || 0);
    return { fillColor: scoreColor(value, ['#16a34a', '#facc15', '#f97316']), fillOpacity: 0.38, color: '#dcfce7', weight: 1.1 };
  }

  if (layerName === 'prioridade_planejamento') {
    const value = Number(props.prioridade_planejamento || 0);
    return { fillColor: scoreColor(value, ['#be123c', '#9333ea', '#c4b5fd']), fillOpacity: 0.42, color: '#f5d0fe', weight: 1.2 };
  }

  if (layerName === 'saneamento_drenagem') {
    const value = Number(props.risco_drenagem || 0);
    return { fillColor: scoreColor(value, ['#0e7490', '#06b6d4', '#a5f3fc']), fillOpacity: 0.4, color: '#cffafe', weight: 1.2 };
  }

  if (layerName === 'lacunas_dados') {
    const value = Number(props.maturidade_dados || 0) / 100;
    return { fillColor: scoreColor(value, ['#16a34a', '#f59e0b', '#e11d48']), fillOpacity: 0.5, color: '#fef3c7', weight: 2 };
  }

  if (layerName === 'desastres') {
    return { fillColor: '#ef4444', fillOpacity: 0.7, color: '#fecaca', weight: 2, radius: 7 };
  }

  if (layerName === 'infraestrutura') {
    return { fillColor: '#a78bfa', fillOpacity: 0.55, color: '#ddd6fe', weight: 1.5, radius: 5 };
  }

  if (layerName === 'saude_risco') {
    const cls = props.cobertura_classe;
    const color = cls === 'ADEQUADA' ? '#16a34a' : cls === 'ATENCAO' ? '#eab308' : '#ef4444';
    return { fillColor: color, fillOpacity: 0.85, color: '#fafafa', weight: 2, radius: 7 };
  }

  if (layerName === 'seguranca_publica') {
    const value = Number(props.intensidade_seguranca || 0);
    return { fillColor: scoreColor(value, ['#fde68a', '#f97316', '#7f1d1d']), fillOpacity: 0.48, color: '#fecaca', weight: 1.2 };
  }

  if (layerName === 'vulnerabilidade_multidimensional') {
    const value = Number(props.indice_vm || 0);
    const flagged = props.vulnerabilidade_multidimensional;
    return {
      fillColor: flagged ? '#581c87' : scoreColor(value, ['#e9d5ff', '#a855f7', '#581c87']),
      fillOpacity: flagged ? 0.62 : 0.45,
      color: flagged ? '#f5d0fe' : '#ddd6fe',
      weight: flagged ? 2.5 : 1.2,
    };
  }

  return {
    fillColor: '#312e81',
    fillOpacity: 0.18,
    color: '#4f46e5',
    weight: 1.5,
  };
}

export function enrichGeoJSON(layerName: string, geojson: any): { type: 'FeatureCollection'; features: any[] } {
  const features = (geojson?.features || []).map((feature: any) => {
    const style = getLayerStyle(layerName, feature);
    return {
      ...feature,
      properties: {
        ...feature.properties,
        _fill: style.fillColor,
        _fillOpacity: style.fillOpacity,
        _stroke: style.color,
        _strokeWidth: style.weight,
        _radius: style.radius ?? 6,
      },
    };
  });
  return { type: 'FeatureCollection', features };
}

export function getSimulationFeatureStyle(feature: any) {
  const props = feature?.properties || {};
  if (props.temp_increase_celsius) {
    return { fillColor: '#ef4444', fillOpacity: 0.55, color: '#b91c1c', weight: 2 };
  }
  if (props.layer_type === 'landslide') {
    return { fillColor: '#dc2626', fillOpacity: 0.55, color: '#991b1b', weight: 2 };
  }
  if (props.depth_band === 'superficial') {
    return { fillColor: '#38bdf8', fillOpacity: 0.42, color: '#0ea5e9', weight: 1.5 };
  }
  if (props.depth_band === 'moderada') {
    return { fillColor: '#0284c7', fillOpacity: 0.58, color: '#0369a1', weight: 1.5 };
  }
  if (props.depth_band === 'critica') {
    return { fillColor: '#1e3a8a', fillOpacity: 0.72, color: '#172554', weight: 2 };
  }
  return {
    fillColor: props.fill_color || '#0284c7',
    fillOpacity: 0.6,
    color: '#0369a1',
    weight: 2,
    dashArray: '2,4',
  };
}

export function enrichSimulationGeoJSON(geojson: any): { type: 'FeatureCollection'; features: any[] } {
  const features = (geojson?.features || []).map((feature: any) => {
    const props = feature?.properties || {};
    const isHeat = Boolean(props.temp_increase_celsius);
    const style = getSimulationFeatureStyle(feature);
    return {
      ...feature,
      properties: {
        ...props,
        _fill: style.fillColor,
        _fillOpacity: style.fillOpacity,
        _stroke: style.color,
        _strokeWidth: style.weight ?? 2,
      },
    };
  });
  return { type: 'FeatureCollection', features };
}

export function enrichContourGeoJSON(geojson: any): { type: 'FeatureCollection'; features: any[] } {
  const features = (geojson?.features || []).map((feature: any) => ({
    ...feature,
    properties: {
      ...feature?.properties,
      _stroke: '#a3e635',
      _strokeWidth: 1.2,
      _fillOpacity: 0,
    },
  }));
  return { type: 'FeatureCollection', features };
}

export function enrichFlowPathGeoJSON(geojson: any): { type: 'FeatureCollection'; features: any[] } {
  const features = (geojson?.features || []).map((feature: any) => ({
    ...feature,
    properties: {
      ...feature?.properties,
      _stroke: '#22d3ee',
      _strokeWidth: 2,
      _fillOpacity: 0,
    },
  }));
  return { type: 'FeatureCollection', features };
}
