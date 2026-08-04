/** Água nas ruas + prédios emergindo (estilo das refs 3D de enchente). */

type Ring = number[][];
type BBox = [number, number, number, number]; // minLng, minLat, maxLng, maxLat

const MAX_HOLES_PER_POLY = 450;

function pointInRing(lng: number, lat: number, ring: Ring): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    const intersect =
      yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-15) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function pointInPolygonCoords(lng: number, lat: number, coords: any): boolean {
  if (!coords?.length) return false;
  if (typeof coords[0][0][0] === 'number') {
    if (!pointInRing(lng, lat, coords[0])) return false;
    for (let h = 1; h < coords.length; h++) {
      if (pointInRing(lng, lat, coords[h])) return false;
    }
    return true;
  }
  for (const poly of coords) {
    if (pointInPolygonCoords(lng, lat, poly)) return true;
  }
  return false;
}

function ringBBox(ring: Ring): BBox {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of ring) {
    const x = p[0];
    const y = p[1];
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  return [minX, minY, maxX, maxY];
}

function bboxOverlap(a: BBox, b: BBox): boolean {
  return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
}

function ensureClosed(ring: Ring): Ring {
  if (ring.length < 3) return ring;
  const f = ring[0];
  const l = ring[ring.length - 1];
  if (f[0] === l[0] && f[1] === l[1]) return ring;
  return [...ring, [f[0], f[1]]];
}

/** Furo no sentido oposto ao anel exterior (GeoJSON). */
function asHoleRing(ring: Ring): Ring {
  const closed = ensureClosed(ring);
  const body = closed.slice(0, -1).reverse();
  return ensureClosed(body);
}

function featureCentroid(feature: any): [number, number] | null {
  const g = feature?.geometry;
  if (!g) return null;
  if (g.type === 'Point') return [g.coordinates[0], g.coordinates[1]];
  let ring: Ring | null = null;
  if (g.type === 'Polygon') ring = g.coordinates[0];
  else if (g.type === 'MultiPolygon') ring = g.coordinates[0]?.[0];
  if (!ring?.length) return null;
  let sx = 0;
  let sy = 0;
  const n = ring.length - (ring[0][0] === ring[ring.length - 1][0] ? 1 : 0);
  for (let i = 0; i < n; i++) {
    sx += ring[i][0];
    sy += ring[i][1];
  }
  return [sx / Math.max(n, 1), sy / Math.max(n, 1)];
}

function buildingFootprints(buildings: { features: any[] } | null | undefined): {
  ring: Ring;
  bbox: BBox;
  centroid: [number, number];
}[] {
  const out: { ring: Ring; bbox: BBox; centroid: [number, number] }[] = [];
  for (const f of buildings?.features || []) {
    const g = f?.geometry;
    if (!g) continue;
    const polys: Ring[][] =
      g.type === 'Polygon'
        ? [g.coordinates]
        : g.type === 'MultiPolygon'
          ? g.coordinates
          : [];
    for (const poly of polys) {
      const ring = poly?.[0];
      if (!ring || ring.length < 4) continue;
      const c = featureCentroid({ geometry: { type: 'Polygon', coordinates: poly } });
      if (!c) continue;
      const closed = ensureClosed(ring);
      out.push({ ring: closed, bbox: ringBBox(closed), centroid: c });
    }
  }
  return out;
}

function punchHolesIntoPolygonCoords(
  polyCoords: any[],
  footprints: { ring: Ring; bbox: BBox; centroid: [number, number] }[],
): any[] {
  const outer = polyCoords[0] as Ring;
  if (!outer?.length) return polyCoords;
  const outerBBox = ringBBox(outer);
  const holes: Ring[] = polyCoords.slice(1).map((h) => ensureClosed(h as Ring));
  for (const fp of footprints) {
    if (holes.length >= MAX_HOLES_PER_POLY) break;
    if (!bboxOverlap(outerBBox, fp.bbox)) continue;
    if (!pointInRing(fp.centroid[0], fp.centroid[1], outer)) continue;
    // já dentro de um furo existente?
    let inHole = false;
    for (const h of holes) {
      if (pointInRing(fp.centroid[0], fp.centroid[1], h)) {
        inHole = true;
        break;
      }
    }
    if (inHole) continue;
    holes.push(asHoleRing(fp.ring));
  }
  return [ensureClosed(outer), ...holes];
}

/**
 * Recorta a mancha pelos footprints — a água passa a ocupar só as ruas/vãos
 * entre prédios (look das referências de enchente 3D).
 */
type FC = { type: 'FeatureCollection'; features: any[] };

export function punchBuildingsIntoFlood(
  flood: { type: string; features: any[] } | null | undefined,
  buildings: { type: string; features: any[] } | null | undefined,
): FC | null {
  if (!flood?.features?.length) return flood ? { type: 'FeatureCollection', features: flood.features } : null;
  const footprints = buildingFootprints(buildings);
  if (!footprints.length) return flood;

  const features = flood.features.map((f) => {
    const p = f?.properties || {};
    const isFlood = p.layer_type === 'flood_band' || p.depth_band;
    if (!isFlood) return f;
    const g = f.geometry;
    if (!g) return f;

    if (g.type === 'Polygon') {
      return {
        ...f,
        geometry: {
          type: 'Polygon',
          coordinates: punchHolesIntoPolygonCoords(g.coordinates, footprints),
        },
        properties: {
          ...p,
          _street_flood: true,
        },
      };
    }
    if (g.type === 'MultiPolygon') {
      return {
        ...f,
        geometry: {
          type: 'MultiPolygon',
          coordinates: g.coordinates.map((poly: any[]) =>
            punchHolesIntoPolygonCoords(poly, footprints),
          ),
        },
        properties: {
          ...p,
          _street_flood: true,
        },
      };
    }
    return f;
  });

  return { type: 'FeatureCollection', features };
}

export type FloodHitBand = 'superficial' | 'moderada' | 'critica';

/** Marca edificações cujo centroide cai na mancha — cor “molhada” no LOD1. */
export function tintBuildingsInFlood(
  buildings: { type: string; features: any[] } | null | undefined,
  flood: { type: string; features: any[] } | null | undefined,
): FC | null {
  if (!buildings?.features?.length) {
    return buildings ? { type: 'FeatureCollection', features: buildings.features } : null;
  }
  const floodPolys = (flood?.features || []).filter((f) => {
    const p = f?.properties || {};
    return p.layer_type === 'flood_band' || p.depth_band;
  });
  if (!floodPolys.length) return buildings;

  const features = buildings.features.map((f) => {
    const c = featureCentroid(f);
    if (!c) return f;
    let band: FloodHitBand | null = null;
    const rank = { superficial: 1, moderada: 2, critica: 3 } as const;
    for (const fp of floodPolys) {
      const g = fp.geometry;
      if (!g || (g.type !== 'Polygon' && g.type !== 'MultiPolygon')) continue;
      if (!pointInPolygonCoords(c[0], c[1], g.coordinates)) continue;
      const b = (fp.properties?.depth_band || 'superficial') as FloodHitBand;
      if (!band || rank[b] > rank[band]) band = b;
    }
    if (!band) return f;
    return {
      ...f,
      properties: {
        ...f.properties,
        _flood_band: band,
      },
    };
  });
  return { type: 'FeatureCollection', features };
}

/**
 * Prepara cena 3D: água só nos vãos + deslizamento discreto + superficial mais suave.
 */
export function prepareFloodScene3D(
  flood: { type: string; features: any[] } | null | undefined,
  buildings: { type: string; features: any[] } | null | undefined,
): FC | null {
  if (!flood?.features?.length) {
    return flood ? { type: 'FeatureCollection', features: flood.features } : null;
  }
  const punched = punchBuildingsIntoFlood(flood, buildings) ?? {
    type: 'FeatureCollection' as const,
    features: flood.features,
  };
  return {
    type: 'FeatureCollection',
    features: punched.features.map((f) => {
      const p = f.properties || {};
      if (p.layer_type === 'landslide') {
        return {
          ...f,
          properties: {
            ...p,
            _fillOpacity: 0.18,
            _fill: '#f87171',
          },
        };
      }
      if (p.depth_band === 'superficial') {
        return {
          ...f,
          properties: {
            ...p,
            _fillOpacity: 0.38,
            _street_flood: true,
          },
        };
      }
      if (p.depth_band === 'moderada' || p.depth_band === 'critica') {
        return {
          ...f,
          properties: {
            ...p,
            _fillOpacity: p.depth_band === 'critica' ? 0.62 : 0.52,
            _street_flood: true,
          },
        };
      }
      return f;
    }),
  };
}
