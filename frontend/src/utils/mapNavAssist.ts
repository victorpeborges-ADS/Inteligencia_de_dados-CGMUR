/** Utilitários de navegação assistida no gêmeo 3D (17f.4). */

export type CameraBookmark = {
  id: string;
  name: string;
  center: [number, number]; // [lng, lat]
  zoom: number;
  pitch: number;
  bearing: number;
  createdAt: string;
};

export type BairroNavItem = {
  nome: string;
  center: [number, number]; // [lng, lat]
  bounds: [[number, number], [number, number]] | null;
};

const STORAGE_PREFIX = 'sinidu.3d.bookmarks.';

function visitCoords(coords: unknown, visit: (lng: number, lat: number) => void): void {
  if (!coords) return;
  if (typeof (coords as number[])[0] === 'number') {
    const [lng, lat] = coords as [number, number];
    if (Number.isFinite(lng) && Number.isFinite(lat)) visit(lng, lat);
    return;
  }
  (coords as unknown[]).forEach((c) => visitCoords(c, visit));
}

export function featureBounds(
  geometry: { coordinates?: unknown } | null | undefined,
): [[number, number], [number, number]] | null {
  if (!geometry?.coordinates) return null;
  let minLng = Infinity;
  let minLat = Infinity;
  let maxLng = -Infinity;
  let maxLat = -Infinity;
  visitCoords(geometry.coordinates, (lng, lat) => {
    minLng = Math.min(minLng, lng);
    minLat = Math.min(minLat, lat);
    maxLng = Math.max(maxLng, lng);
    maxLat = Math.max(maxLat, lat);
  });
  if (!Number.isFinite(minLng)) return null;
  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ];
}

export function featureCentroid(
  geometry: { coordinates?: unknown } | null | undefined,
): [number, number] | null {
  const b = featureBounds(geometry);
  if (!b) return null;
  return [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2];
}

export function bairrosFromGeoJSON(geojson: {
  features?: Array<{ geometry?: { coordinates?: unknown }; properties?: Record<string, unknown> }>;
}): BairroNavItem[] {
  const items: BairroNavItem[] = [];
  for (const f of geojson?.features || []) {
    const nome = String(f.properties?.nome || f.properties?.name || '').trim();
    if (!nome) continue;
    const center = featureCentroid(f.geometry);
    if (!center) continue;
    items.push({
      nome,
      center,
      bounds: featureBounds(f.geometry),
    });
  }
  items.sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
  return items;
}

export function loadBookmarks(codigoIbge: string): CameraBookmark[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + codigoIbge);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveBookmarks(codigoIbge: string, bookmarks: CameraBookmark[]): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_PREFIX + codigoIbge, JSON.stringify(bookmarks.slice(0, 20)));
}

export function makeBookmark(
  name: string,
  camera: { center: [number, number]; zoom: number; pitch: number; bearing: number },
): CameraBookmark {
  return {
    id: `bm-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    name: name.trim() || 'Cena',
    center: camera.center,
    zoom: camera.zoom,
    pitch: camera.pitch,
    bearing: camera.bearing,
    createdAt: new Date().toISOString(),
  };
}

/** Posição normalizada 0–1 do centro da câmera dentro de um bbox municipal. */
export function normalizeInBounds(
  lng: number,
  lat: number,
  bounds: [[number, number], [number, number]],
): { x: number; y: number } {
  const [[minLng, minLat], [maxLng, maxLat]] = bounds;
  const dx = maxLng - minLng || 1;
  const dy = maxLat - minLat || 1;
  return {
    x: Math.max(0, Math.min(1, (lng - minLng) / dx)),
    y: Math.max(0, Math.min(1, 1 - (lat - minLat) / dy)), // norte no topo
  };
}

export const SCENARIO_PRESETS: Array<{
  id: string;
  label: string;
  zoom: number;
  pitch: number;
  bearing: number;
}> = [
  { id: 'overview', label: 'Visão geral', zoom: 12.2, pitch: 42, bearing: -12 },
  { id: 'orbit', label: 'Órbita urbana', zoom: 13.8, pitch: 65, bearing: -40 },
  { id: 'street', label: 'Nível de rua', zoom: 15.2, pitch: 72, bearing: 15 },
];
