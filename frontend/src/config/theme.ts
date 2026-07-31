export type ColorMode = 'dark' | 'light';
export type MapBasemapId = 'dark' | 'light' | 'satellite';

export const COLOR_MODE_STORAGE_KEY = 'sinidu-color-mode';

export const MAP_BASEMAP_DARK =
  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';

export const MAP_BASEMAP_LIGHT =
  'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';

export const MAP_BASEMAP_SATELLITE =
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

/** Basemap padrão do Leaflet 2D por modo de UI (override local via toggle). */
export const MAP_BASEMAPS: Record<ColorMode, string> = {
  dark: MAP_BASEMAP_DARK,
  light: MAP_BASEMAP_LIGHT,
};

export const MAP_TILE_URLS: Record<MapBasemapId, { url: string; attribution: string }> = {
  dark: {
    url: MAP_BASEMAP_DARK,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  light: {
    url: MAP_BASEMAP_LIGHT,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  satellite: {
    url: MAP_BASEMAP_SATELLITE,
    attribution: 'Esri, Maxar, Earthstar Geographics',
  },
};

export const MAPLIBRE_BASEMAPS: Record<ColorMode, { tiles: string[]; attribution: string }> = {
  dark: {
    tiles: ['https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'],
    attribution: '© CARTO © OpenStreetMap',
  },
  light: {
    tiles: ['https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'],
    attribution: '© CARTO © OpenStreetMap',
  },
};
