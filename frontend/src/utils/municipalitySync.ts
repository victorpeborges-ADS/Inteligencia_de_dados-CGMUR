import { api } from '@/utils/api';

export const DEFAULT_MAP_LAYERS = ['municipio', 'bairros'] as const;

/** Centros aproximados para zoom inicial quando a API territorial ainda não responde. */
export const MUNICIPALITY_CENTERS: Record<string, [number, number]> = {
  '2611606': [-8.0578, -34.9004],
  '2927408': [-12.9714, -38.5014],
  '4314902': [-30.0346, -51.2177],
  '2507507': [-7.115, -34.8631],
  '4113700': [-23.3045, -51.1696],
  '2806701': [-11.015, -37.206],
  '5201108': [-16.6869, -49.2648],
  '1400233': [0.0349, -60.0469],
  '3550308': [-23.5505, -46.6333],
  '3304557': [-22.9068, -43.1729],
  '5300108': [-15.7939, -47.8828],
  '3106200': [-19.9167, -43.9345],
  '2304400': [-3.7172, -38.5433],
  '1302603': [-3.119, -60.0217],
  '4106902': [-25.4284, -49.2733],
};

export function getGeoJsonCenter(geojson: any): [number, number] | null {
  const coords: [number, number][] = [];
  const collect = (node: any) => {
    if (!Array.isArray(node)) return;
    if (typeof node[0] === 'number' && typeof node[1] === 'number') {
      coords.push([node[1], node[0]]);
      return;
    }
    node.forEach(collect);
  };
  geojson?.features?.forEach((feature: any) => collect(feature.geometry?.coordinates));
  if (!geojson?.features?.length && geojson?.geometry) collect(geojson.geometry.coordinates);
  if (!coords.length) return null;
  const lat = coords.reduce((sum, item) => sum + item[0], 0) / coords.length;
  const lng = coords.reduce((sum, item) => sum + item[1], 0) / coords.length;
  return [lat, lng];
}

export async function fetchIbgeMunicipalityCenter(codigoIbge: string): Promise<[number, number] | null> {
  try {
    const res = await fetch(
      `https://servicodados.ibge.gov.br/api/v3/malhas/municipios/${codigoIbge}?formato=application/vnd.geo+json&qualidade=minima`,
    );
    if (!res.ok) return null;
    const geo = await res.json();
    return getGeoJsonCenter(geo.type === 'FeatureCollection' ? geo : { features: [geo] });
  } catch {
    return null;
  }
}

export async function resolveMunicipalityCenter(codigoIbge: string): Promise<[number, number]> {
  try {
    const geo = await api.getLayerGeoJSON('municipio', codigoIbge);
    const center = getGeoJsonCenter(geo);
    if (center) return center;
  } catch {
    /* município ainda não integrado ao PostGIS */
  }

  if (MUNICIPALITY_CENTERS[codigoIbge]) {
    return MUNICIPALITY_CENTERS[codigoIbge];
  }

  const ibgeCenter = await fetchIbgeMunicipalityCenter(codigoIbge);
  if (ibgeCenter) return ibgeCenter;

  return [-14.235, -51.9253];
}

export async function isMunicipalityInDatabase(codigoIbge: string): Promise<boolean> {
  try {
    const rows = await api.getMunicipalities();
    return rows.some((row) => row.codigo_ibge === codigoIbge);
  } catch {
    return false;
  }
}
