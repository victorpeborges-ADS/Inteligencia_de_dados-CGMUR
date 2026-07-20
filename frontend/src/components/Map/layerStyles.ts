import type { SocioSubcamadaId } from '@/config/socioeconomicoSubcamadas';
import { getEducacaoEtapa, markerRadiusFromMatriculas, type EducacaoEtapaId } from '@/config/educacaoInep';
import { getTerritorioTipo, type TerritorioTipoId } from '@/config/territoriosEspeciais';

export type LayerStyle = {
  fillColor: string;
  fillOpacity: number;
  color: string;
  weight: number;
  radius?: number;
  opacity?: number;
};

function deficitColor(pct: number, thresholds: [number, number], palette: [string, string, string]): string {
  if (pct >= thresholds[1]) return palette[0];
  if (pct >= thresholds[0]) return palette[1];
  return palette[2];
}

export function scoreColor(value: number, palette: [string, string, string]): string {
  if (value >= 0.66) return palette[0];
  if (value >= 0.33) return palette[1];
  return palette[2];
}

export function getLayerStyle(
  layerName: string,
  feature: any,
  options?: { socioSubcamada?: SocioSubcamadaId; educacaoEtapa?: EducacaoEtapaId; territorioTipo?: TerritorioTipoId },
): LayerStyle {
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
    if (cls === 'Área Urbana') {
      return { fillColor: '#71717a', fillOpacity: 0.5, color: '#52525b', weight: 1 };
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
    const cls = props.classe_vulnerabilidade;
    if (cls === 'ALTA' || value >= 0.66) {
      return { fillColor: '#7f1d1d', fillOpacity: 0.52, color: '#fecaca', weight: 1.3 };
    }
    if (cls === 'MEDIA' || value >= 0.33) {
      return { fillColor: '#f97316', fillOpacity: 0.45, color: '#fed7aa', weight: 1.1 };
    }
    return { fillColor: '#fde047', fillOpacity: 0.38, color: '#fef08a', weight: 1.0 };
  }

  if (layerName === 'inundacao') {
    const value = Number(props.indice_risco_inundacao || 0);
    return { fillColor: scoreColor(value, ['#075985', '#0284c7', '#7dd3fc']), fillOpacity: 0.42, color: '#bae6fd', weight: 1.3 };
  }

  if (layerName === 'socioeconomico') {
    const sub = options?.socioSubcamada ?? 'renda';
    const deficits = props.deficits_censo as Record<string, number> | undefined;
    if (sub !== 'renda' && deficits && deficits[sub] != null) {
      const pct = Number(deficits[sub]);
      const palettes: Record<string, { thresholds: [number, number]; colors: [string, string, string] }> = {
        arborizacao: { thresholds: [15, 35], colors: ['#facc15', '#84cc16', '#14532d'] },
        calcada: { thresholds: [15, 35], colors: ['#f97316', '#60a5fa', '#1e3a8a'] },
        iluminacao: { thresholds: [5, 15], colors: ['#ef4444', '#a78bfa', '#312e81'] },
        agua: { thresholds: [5, 15], colors: ['#dc2626', '#38bdf8', '#0c4a6e'] },
        esgoto: { thresholds: [10, 25], colors: ['#b91c1c', '#2dd4bf', '#134e4a'] },
        lixo: { thresholds: [3, 8], colors: ['#ea580c', '#a1a1aa', '#3f3f46'] },
        alfabetizacao: { thresholds: [5, 12], colors: ['#be123c', '#c084fc', '#4c1d95'] },
      };
      const cfg = palettes[sub];
      if (cfg) {
        const fill = deficitColor(pct, cfg.thresholds, cfg.colors);
        return { fillColor: fill, fillOpacity: 0.42, color: '#e2e8f0', weight: 0.9 };
      }
    }
    const value = props.classe_renda === 'ALTA' ? 0.8 : props.classe_renda === 'MEDIA' ? 0.5 : 0.2;
    return { fillColor: scoreColor(value, ['#22c55e', '#eab308', '#f97316']), fillOpacity: 0.34, color: '#fef3c7', weight: 0.8 };
  }

  if (layerName === 'adaptacao_climatica') {
    const value = Number(props.capacidade_adaptacao || 0);
    return { fillColor: scoreColor(value, ['#16a34a', '#facc15', '#f97316']), fillOpacity: 0.38, color: '#dcfce7', weight: 1.1 };
  }

  if (layerName === 'prioridade_planejamento') {
    const cls = props.classe_prioridade;
    if (cls === 'ALTA') {
      return { fillColor: '#be123c', fillOpacity: 0.58, color: '#881337', weight: 1.4 };
    }
    if (cls === 'MEDIA') {
      return { fillColor: '#9333ea', fillOpacity: 0.48, color: '#6b21a8', weight: 1.2 };
    }
    return { fillColor: '#c4b5fd', fillOpacity: 0.42, color: '#8b5cf6', weight: 1.0 };
  }

  if (layerName === 'saneamento_drenagem') {
    const cls = props.classe_drenagem;
    if (cls === 'CRITICA') {
      return { fillColor: '#0e7490', fillOpacity: 0.58, color: '#155e75', weight: 1.4 };
    }
    if (cls === 'ATENCAO') {
      return { fillColor: '#06b6d4', fillOpacity: 0.48, color: '#0891b2', weight: 1.2 };
    }
    return { fillColor: '#e0f2fe', fillOpacity: 0.42, color: '#7dd3fc', weight: 1.0 };
  }

  if (layerName === 'lacunas_dados') {
    const value = Number(props.maturidade_dados || 0) / 100;
    return { fillColor: scoreColor(value, ['#16a34a', '#f59e0b', '#e11d48']), fillOpacity: 0.5, color: '#fef3c7', weight: 2 };
  }

  if (layerName === 'territorios_especiais') {
    const tipo = props.tipo || 'comunidade_urbana';
    const palette: Record<string, { fill: string; stroke: string }> = {
      quilombo: { fill: '#a16207', stroke: '#fbbf24' },
      terra_indigena: { fill: '#15803d', stroke: '#4ade80' },
      comunidade_urbana: { fill: '#c026d3', stroke: '#e879f9' },
    };
    const colors = palette[tipo] || palette.comunidade_urbana;
    return { fillColor: colors.fill, fillOpacity: 0.42, color: colors.stroke, weight: 1.6 };
  }

  if (layerName === 'bairros') {
    const nome = String(props.nome || props.codigo_bairro || '');
    let hash = 0;
    for (let i = 0; i < nome.length; i += 1) {
      hash = (hash * 31 + nome.charCodeAt(i)) >>> 0;
    }
    // Tons distintos por bairro, mas com contraste alto no basemap escuro
    const hue = hash % 360;
    const fill = `hsl(${hue}, 58%, 48%)`;
    return {
      fillColor: fill,
      fillOpacity: 0.42,
      color: '#c7d2fe',
      weight: 1.8,
      opacity: 0.95,
    };
  }

  if (layerName === 'desastres') {
    return { fillColor: '#ef4444', fillOpacity: 0.7, color: '#fecaca', weight: 2, radius: 7 };
  }

  if (layerName === 'infraestrutura') {
    const tipo = props.tipo;
    if (tipo === 'hospital') {
      return { fillColor: '#ef4444', fillOpacity: 0.85, color: '#fecaca', weight: 2, radius: 8 };
    }
    if (tipo === 'escola') {
      return { fillColor: '#3b82f6', fillOpacity: 0.85, color: '#bfdbfe', weight: 2, radius: 6 };
    }
    if (tipo === 'via') {
      return { fillColor: 'transparent', fillOpacity: 0, color: '#c4b5fd', weight: 3 };
    }
    return { fillColor: '#a78bfa', fillOpacity: 0.55, color: '#ddd6fe', weight: 1.5, radius: 5 };
  }

  if (layerName === 'educacao') {
    const etapa = options?.educacaoEtapa || 'todas';
    const color = getEducacaoEtapa(etapa).color;
    const matriculas = Number(props.matriculas_ativas ?? props.matriculas_total ?? 0);
    return {
      fillColor: color,
      fillOpacity: 0.88,
      color: '#f8fafc',
      weight: 2,
      radius: markerRadiusFromMatriculas(matriculas),
    };
  }

  if (layerName === 'saude_risco') {
    const cls = props.cobertura_classe;
    const palette: Record<string, string> = {
      ADEQUADA: '#16a34a',
      ATENCAO: '#eab308',
      CRITICA: '#ef4444',
    };
    const color = palette[cls] || '#64748b';
    if (props.feature_kind === 'setor_pressao') {
      return { fillColor: color, fillOpacity: 0.24, color, weight: 0.7 };
    }
    return { fillColor: 'transparent', fillOpacity: 0, color: 'transparent', weight: 0 };
  }

  if (layerName === 'seguranca_publica') {
    const cls = props.classe_intensidade;
    if (cls === 'ALTA') {
      return { fillColor: '#7f1d1d', fillOpacity: 0.58, color: '#991b1b', weight: 1.3 };
    }
    if (cls === 'MEDIA') {
      return { fillColor: '#f97316', fillOpacity: 0.48, color: '#ea580c', weight: 1.1 };
    }
    return { fillColor: '#fde68a', fillOpacity: 0.42, color: '#fbbf24', weight: 1.0 };
  }

  if (layerName === 'vulnerabilidade_multidimensional') {
    const flagged = props.vulnerabilidade_multidimensional;
    const cls = props.classe_vm;
    if (flagged || cls === 'CRITICA') {
      return { fillColor: '#581c87', fillOpacity: 0.58, color: '#f5d0fe', weight: 2 };
    }
    if (cls === 'ALTA') {
      return { fillColor: '#a855f7', fillOpacity: 0.48, color: '#ddd6fe', weight: 1.2 };
    }
    return { fillColor: '#e9d5ff', fillOpacity: 0.38, color: '#c4b5fd', weight: 1.0 };
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
  if (props.temp_increase_celsius != null) {
    const band = props.heat_band as string | undefined;
    if (band === 'leve') {
      return { fillColor: '#fbbf24', fillOpacity: 0.5, color: '#d97706', weight: 2 };
    }
    if (band === 'moderada') {
      return { fillColor: '#f97316', fillOpacity: 0.55, color: '#c2410c', weight: 2 };
    }
    if (band === 'severa') {
      return { fillColor: '#ef4444', fillOpacity: 0.62, color: '#b91c1c', weight: 2 };
    }
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
    const style = getSimulationFeatureStyle(feature);

    let extrusionHeightM = 0.25;
    let depthCm: number | null = null;

    if (props.temp_increase_celsius != null) {
      extrusionHeightM = Math.max(0.15, Number(props.temp_increase_celsius) * 12);
    } else if (props.layer_type === 'flood_band' || props.depth_band) {
      const lo = Number(props.depth_min_m ?? 0.05);
      const hiRaw = props.depth_max_m;
      const hi = hiRaw == null || Number(hiRaw) > 100 ? lo + 0.45 : Number(hiRaw);
      extrusionHeightM = Math.max(0.08, (lo + hi) / 2);
      depthCm = Math.round(extrusionHeightM * 100);
    }

    return {
      ...feature,
      properties: {
        ...props,
        _fill: style.fillColor,
        _fillOpacity: style.fillOpacity,
        _stroke: style.color,
        _strokeWidth: style.weight ?? 2,
        _extrusionHeightM: extrusionHeightM,
        _depthCm: depthCm,
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
