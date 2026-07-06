/** Utilitários para inspeção de profundidade de alagamento no mapa 3D. */

export type FloodInspectResult = {
  lat: number;
  lng: number;
  inFlood: boolean;
  depthCm: number | null;
  depthBand: string | null;
  bandLabel: string | null;
  precipitationMm: number | null;
  groundElevationM: number | null;
  waterSurfaceM: number | null;
  tempIncreaseC: number | null;
  scenario: 'flood' | 'heat' | 'none';
};

const BAND_LABELS: Record<string, string> = {
  superficial: 'Alagamento superficial (< 35 cm)',
  moderada: 'Alagamento moderado (35–80 cm)',
  critica: 'Alagamento crítico (> 80 cm)',
};

function depthMidM(props: Record<string, unknown>): number {
  const lo = Number(props.depth_min_m ?? 0);
  const hiRaw = props.depth_max_m;
  const hi = hiRaw == null || Number(hiRaw) > 100 ? lo + 0.5 : Number(hiRaw);
  return (lo + hi) / 2;
}

export function inspectFloodFeature(props: Record<string, unknown>): {
  depthCm: number | null;
  depthBand: string | null;
  bandLabel: string | null;
  precipitationMm: number | null;
  tempIncreaseC: number | null;
  scenario: 'flood' | 'heat' | 'none';
} {
  if (props.temp_increase_celsius != null) {
    return {
      depthCm: null,
      depthBand: null,
      bandLabel: null,
      precipitationMm: null,
      tempIncreaseC: Number(props.temp_increase_celsius),
      scenario: 'heat',
    };
  }

  if (props.layer_type === 'flood_band' || props.depth_band) {
    const band = String(props.depth_band || 'superficial');
    const depthM = depthMidM(props);
    return {
      depthCm: Math.round(depthM * 100),
      depthBand: band,
      bandLabel: BAND_LABELS[band] || String(props.name || band),
      precipitationMm: props.precipitation_mm != null ? Number(props.precipitation_mm) : null,
      tempIncreaseC: null,
      scenario: 'flood',
    };
  }

  return {
    depthCm: null,
    depthBand: null,
    bandLabel: null,
    precipitationMm: null,
    tempIncreaseC: null,
    scenario: 'none',
  };
}

export function buildInspectResult(
  lat: number,
  lng: number,
  featureProps: Record<string, unknown> | null,
  groundElevationM: number | null,
): FloodInspectResult {
  if (!featureProps) {
    return {
      lat,
      lng,
      inFlood: false,
      depthCm: null,
      depthBand: null,
      bandLabel: null,
      precipitationMm: null,
      groundElevationM,
      waterSurfaceM: null,
      tempIncreaseC: null,
      scenario: 'none',
    };
  }

  const partial = inspectFloodFeature(featureProps);
  if (partial.scenario === 'heat') {
    return {
      lat,
      lng,
      inFlood: false,
      depthCm: null,
      depthBand: null,
      bandLabel: null,
      precipitationMm: null,
      groundElevationM,
      waterSurfaceM: null,
      tempIncreaseC: partial.tempIncreaseC,
      scenario: 'heat',
    };
  }

  if (partial.scenario === 'flood' && partial.depthCm != null) {
    const waterSurfaceM =
      groundElevationM != null ? groundElevationM + partial.depthCm / 100 : null;
    return {
      lat,
      lng,
      inFlood: true,
      depthCm: partial.depthCm,
      depthBand: partial.depthBand,
      bandLabel: partial.bandLabel,
      precipitationMm: partial.precipitationMm,
      groundElevationM,
      waterSurfaceM,
      tempIncreaseC: null,
      scenario: 'flood',
    };
  }

  return {
    lat,
    lng,
    inFlood: false,
    depthCm: null,
    depthBand: null,
    bandLabel: null,
    precipitationMm: null,
    groundElevationM,
    waterSurfaceM: null,
    tempIncreaseC: null,
    scenario: 'none',
  };
}

export function formatElevation(m: number | null): string {
  if (m == null || Number.isNaN(m)) return '—';
  return `${m.toFixed(1)} m`;
}
