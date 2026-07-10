/** Camadas raster externas (mosaicjson / TiTiler) — Fase 16d.4 */

export type ExternalRasterId = 'lst_observada';

export const EXTERNAL_RASTER_LAYER_IDS: ExternalRasterId[] = ['lst_observada'];

export type RasterRescaleUi = {
  min: number;
  max: number;
  minBound: number;
  maxBound: number;
  minSliderMax: number;
  maxSliderMin: number;
  step: number;
  unit: string;
  gradient: string;
};

export const RASTER_RESCALE_UI: Record<ExternalRasterId, RasterRescaleUi> = {
  lst_observada: {
    min: 20,
    max: 60,
    minBound: 15,
    maxBound: 70,
    minSliderMax: 55,
    maxSliderMin: 25,
    step: 1,
    unit: '°C',
    gradient:
      'linear-gradient(to right, #30123b, #4662d7, #35aab9, #1ae187, #fde724, #fca50a, #f66e0b, #d31e1f)',
  },
};

export function isExternalRasterLayer(layerId: string): layerId is ExternalRasterId {
  return (EXTERNAL_RASTER_LAYER_IDS as string[]).includes(layerId);
}
