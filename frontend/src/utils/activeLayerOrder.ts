import { EXTERNAL_RASTER_LAYER_IDS } from '@/config/externalRasters';

const RASTER_LAYER_IDS = new Set<string>(EXTERNAL_RASTER_LAYER_IDS);

export function isRasterLayer(layerId: string): boolean {
  return RASTER_LAYER_IDS.has(layerId);
}

/** Ordem de desenho: base fixa no fundo; demais camadas seguem a ordem em activeLayers. */
export function buildVectorRenderOrder(activeLayers: string[]): string[] {
  const vector = activeLayers.filter((id) => !isRasterLayer(id));
  const municipio = vector.filter((id) => id === 'municipio');
  const bairros = vector.filter((id) => id === 'bairros');
  const thematic = vector.filter((id) => id !== 'municipio' && id !== 'bairros');
  return [...municipio, ...bairros, ...thematic];
}

/** Índice mínimo para reordenar (município/bairros ficam ancorados no fundo). */
export function minReorderIndex(activeLayers: string[]): number {
  let min = 0;
  if (activeLayers.includes('municipio')) min += 1;
  if (activeLayers.includes('bairros')) min += 1;
  return min;
}

export function canReorderLayer(layerId: string): boolean {
  return layerId !== 'municipio' && layerId !== 'bairros';
}

export function moveLayerInStack(
  activeLayers: string[],
  layerId: string,
  direction: 'up' | 'down',
): string[] | null {
  if (!canReorderLayer(layerId)) return null;

  const layers = [...activeLayers];
  const idx = layers.indexOf(layerId);
  const minIdx = minReorderIndex(layers);
  if (idx < minIdx) return null;

  const newIdx = direction === 'up' ? idx + 1 : idx - 1;
  if (newIdx < minIdx || newIdx >= layers.length) return null;

  [layers[idx], layers[newIdx]] = [layers[newIdx], layers[idx]];
  return layers;
}

/** Lista para UI: camada no topo do mapa aparece primeiro. */
export function displayStackOrder(activeLayers: string[]): string[] {
  return [...activeLayers].reverse();
}
