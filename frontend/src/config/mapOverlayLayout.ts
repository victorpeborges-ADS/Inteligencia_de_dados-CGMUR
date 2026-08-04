/** Espaçamento compartilhado dos painéis flutuantes sobre o mapa (camadas, oficina, legenda). */
export const MAP_PANEL_INSET = '1rem';
export const MAP_PANEL_WIDTH = '18rem'; // w-72
export const MAP_PANEL_GAP = '0.75rem';
export const MAP_RIGHT_PANEL_WIDTH = '13rem'; // w-52 basemap 3D

/** À direita do LayerPanel (esquerda) — overlays do mapa não devem usar left-4. */
export const MAP_CENTER_LEFT = `calc(${MAP_PANEL_INSET} + ${MAP_PANEL_WIDTH} + ${MAP_PANEL_GAP})`;
export const MAP_CENTER_RIGHT = MAP_CENTER_LEFT;

/** Coluna segura à direita (basemap / camadas ativas), abaixo do toggle 2D·3D. */
export const MAP_SAFE_RIGHT = MAP_PANEL_INSET;
export const MAP_SAFE_BOTTOM = '1rem';
