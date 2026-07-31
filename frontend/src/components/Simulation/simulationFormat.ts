/**
 * 20f.2 — Helpers de formatação compartilhados entre `SimulationPanel` e `SimulationResults`.
 * Extraídos para evitar import circular entre os dois componentes.
 */
export function formatDuration(min: number): string {
  if (min < 60) return `${min} min`;
  if (min < 1440) {
    const h = min / 60;
    return `${Number.isInteger(h) ? h : h.toFixed(1)} h`;
  }
  const d = min / 1440;
  return `${Number.isInteger(d) ? d : d.toFixed(1)} dia${d > 1 ? 's' : ''}`;
}

export function isVolumeSimulation(geojson: unknown): boolean {
  const features = (geojson as { features?: Array<{ properties?: Record<string, unknown> }> })?.features;
  if (!features?.length) return false;
  return features.some(
    (f) =>
      f.properties?.layer_type === 'flood_band'
      || f.properties?.depth_band
      || f.properties?.temp_increase_celsius != null,
  );
}
