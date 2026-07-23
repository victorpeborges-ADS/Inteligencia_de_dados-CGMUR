import { enrichGeoJSON, enrichSimulationGeoJSON, enrichContourGeoJSON, enrichFlowPathGeoJSON } from './layerStyles';

type MapLibreMap = any;

const POLYGON_FILTER: any = ['match', ['geometry-type'], ['Polygon', 'MultiPolygon'], true, false];
const LINE_FILTER: any = ['match', ['geometry-type'], ['LineString', 'MultiLineString'], true, false];
const POINT_FILTER: any = ['match', ['geometry-type'], ['Point', 'MultiPoint'], true, false];

function sourceId(layerName: string) {
  return `src-${layerName}`;
}

function fillId(layerName: string) {
  return `fill-${layerName}`;
}

function lineId(layerName: string) {
  return `line-${layerName}`;
}

function circleId(layerName: string) {
  return `circle-${layerName}`;
}

function extrusionId(layerName: string) {
  return `extrusion-${layerName}`;
}

function markerSourceId() {
  return 'src-inspect-marker';
}

function markerLayerId() {
  return 'inspect-marker';
}

function upsertSource(map: MapLibreMap, id: string, data: { type: 'FeatureCollection'; features: any[] }) {
  if (map.getSource(id)) {
    map.getSource(id).setData(data);
  } else {
    map.addSource(id, { type: 'geojson', data });
  }
}

function upsertFillLayer(map: MapLibreMap, layerName: string, opts?: { flatOpacity?: number }) {
  const id = fillId(layerName);
  if (!map.getLayer(id)) {
    map.addLayer({
      id,
      type: 'fill',
      source: sourceId(layerName),
      filter: POLYGON_FILTER,
      paint: {
        'fill-color': ['coalesce', ['get', '_fill'], '#6366f1'],
        'fill-opacity': opts?.flatOpacity ?? ['coalesce', ['get', '_fillOpacity'], 0.4],
      },
    });
  }
}

function upsertExtrusionLayer(map: MapLibreMap, layerName: string, opts?: { minzoom?: number }) {
  const id = extrusionId(layerName);
  if (!map.getLayer(id)) {
    map.addLayer({
      id,
      type: 'fill-extrusion',
      source: sourceId(layerName),
      filter: POLYGON_FILTER,
      minzoom: opts?.minzoom,
      paint: {
        'fill-extrusion-color': ['coalesce', ['get', '_fill'], '#0284c7'],
        'fill-extrusion-height': ['coalesce', ['get', '_extrusionHeightM'], 0.25],
        'fill-extrusion-opacity': 0.78,
        'fill-extrusion-base': 0,
      },
    });
  }
}

function upsertLineLayer(map: MapLibreMap, layerName: string) {
  const id = lineId(layerName);
  if (!map.getLayer(id)) {
    map.addLayer({
      id,
      type: 'line',
      source: sourceId(layerName),
      filter: ['any', POLYGON_FILTER, LINE_FILTER],
      paint: {
        'line-color': ['coalesce', ['get', '_stroke'], '#818cf8'],
        'line-width': ['coalesce', ['get', '_strokeWidth'], 1.2],
      },
    });
  }
}

function upsertCircleLayer(map: MapLibreMap, layerName: string) {
  const id = circleId(layerName);
  if (map.getLayer(id)) return;
  map.addLayer({
    id,
    type: 'circle',
    source: sourceId(layerName),
    filter: POINT_FILTER,
    paint: {
      'circle-color': ['coalesce', ['get', '_fill'], '#a78bfa'],
      'circle-opacity': ['coalesce', ['get', '_fillOpacity'], 0.85],
      'circle-radius': ['coalesce', ['get', '_radius'], 6],
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 1.5,
    },
  });
}

function removeLayerBundle(map: MapLibreMap, layerName: string) {
  [extrusionId(layerName), circleId(layerName), lineId(layerName), fillId(layerName)].forEach((id) => {
    if (map.getLayer(id)) map.removeLayer(id);
  });
  const sid = sourceId(layerName);
  if (map.getSource(sid)) map.removeSource(sid);
}

export function setInspectMarker(map: MapLibreMap, lng: number, lat: number) {
  const data = {
    type: 'FeatureCollection' as const,
    features: [
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lng, lat] },
        properties: {},
      },
    ],
  };
  upsertSource(map, markerSourceId(), data);
  if (!map.getLayer(markerLayerId())) {
    map.addLayer({
      id: markerLayerId(),
      type: 'circle',
      source: markerSourceId(),
      paint: {
        'circle-radius': 8,
        'circle-color': '#fbbf24',
        'circle-stroke-color': '#0f172a',
        'circle-stroke-width': 2,
      },
    });
  }
}

export function clearInspectMarker(map: MapLibreMap) {
  if (map.getLayer(markerLayerId())) map.removeLayer(markerLayerId());
  if (map.getSource(markerSourceId())) map.removeSource(markerSourceId());
}

export function simulationLayerIds(): string[] {
  return [extrusionId('simulation'), fillId('simulation')];
}

export type SimOverlayOptions3D = {
  showFlood?: boolean;
  showContours?: boolean;
  showFlow?: boolean;
};

function applyLayerOpacity(map: MapLibreMap, layerName: string, opacity: number) {
  const o = Math.max(0, Math.min(1, opacity));
  const fill = fillId(layerName);
  const line = lineId(layerName);
  const circle = circleId(layerName);
  const extrusion = extrusionId(layerName);
  try {
    if (map.getLayer(fill)) {
      if (layerName === 'simulation') {
        map.setPaintProperty(fill, 'fill-opacity', 0.5 * o);
      } else {
        map.setPaintProperty(fill, 'fill-opacity', [
          '*',
          o,
          ['coalesce', ['get', '_fillOpacity'], 0.4],
        ]);
      }
    }
    if (map.getLayer(line)) {
      map.setPaintProperty(line, 'line-opacity', o);
    }
    if (map.getLayer(circle)) {
      map.setPaintProperty(circle, 'circle-opacity', [
        '*',
        o,
        ['coalesce', ['get', '_fillOpacity'], 0.85],
      ]);
    }
    if (map.getLayer(extrusion)) {
      map.setPaintProperty(extrusion, 'fill-extrusion-opacity', 0.78 * o);
    }
  } catch {
    /* style may be mid-transition */
  }
}

export type ContingencyLayers3D = {
  zonas?: { type: 'FeatureCollection'; features: any[] } | null;
  rotas?: { type: 'FeatureCollection'; features: any[] } | null;
  pontos?: { type: 'FeatureCollection'; features: any[] } | null;
} | null;

export function syncThematicLayers(
  map: MapLibreMap,
  activeLayers: string[],
  layerData: Record<string, any>,
  simGeoJSON: any | null,
  simContours: any | null = null,
  simFlowPaths: any | null = null,
  options?: {
    layerOpacityById?: Record<string, number>;
    simOverlays?: SimOverlayOptions3D;
    contingency?: ContingencyLayers3D;
  },
) {
  const wanted = new Set<string>();
  const opacityById = options?.layerOpacityById ?? {};
  const overlays = options?.simOverlays ?? {};
  const showFlood = overlays.showFlood !== false;
  const showContours = overlays.showContours !== false;
  const showFlow = overlays.showFlow !== false;
  const contingency = options?.contingency;

  activeLayers.forEach((layerName) => {
    const raw = layerData[layerName];
    if (!raw?.features?.length) return;

    wanted.add(layerName);
    const data = enrichGeoJSON(layerName, raw);
    upsertSource(map, sourceId(layerName), data);

    const geomTypes = new Set(data.features.map((f) => f.geometry?.type));
    const types = Array.from(geomTypes);
    const hasPolygons = types.some((t) => t === 'Polygon' || t === 'MultiPolygon');
    const hasLines = types.some((t) => t === 'LineString' || t === 'MultiLineString');
    const hasPoints = types.some((t) => t === 'Point' || t === 'MultiPoint');

    if (hasPolygons || hasLines) {
      upsertFillLayer(map, layerName);
      upsertLineLayer(map, layerName);
    }
    if (hasPoints) {
      upsertCircleLayer(map, layerName);
    }
    applyLayerOpacity(map, layerName, opacityById[layerName] ?? 1);
  });

  if (showFlood && simGeoJSON?.features?.length) {
    wanted.add('simulation');
    upsertSource(map, sourceId('simulation'), enrichSimulationGeoJSON(simGeoJSON));
    upsertFillLayer(map, 'simulation', { flatOpacity: 0.5 });
    upsertExtrusionLayer(map, 'simulation');
    upsertLineLayer(map, 'simulation');
    applyLayerOpacity(map, 'simulation', opacityById.simulation ?? 1);
    for (const id of [lineId('simulation'), extrusionId('simulation'), fillId('simulation')]) {
      if (map.getLayer(id)) {
        try {
          map.moveLayer(id);
        } catch {
          /* ignore */
        }
      }
    }
  }

  if (showContours && simContours?.features?.length) {
    wanted.add('sim-contours');
    upsertSource(map, sourceId('sim-contours'), enrichContourGeoJSON(simContours));
    upsertLineLayer(map, 'sim-contours');
    applyLayerOpacity(map, 'sim-contours', opacityById['sim-contours'] ?? 1);
  }

  if (showFlow && simFlowPaths?.features?.length) {
    wanted.add('sim-flow');
    upsertSource(map, sourceId('sim-flow'), enrichFlowPathGeoJSON(simFlowPaths));
    upsertLineLayer(map, 'sim-flow');
    applyLayerOpacity(map, 'sim-flow', opacityById['sim-flow'] ?? 1);
  }

  if (contingency?.zonas?.features?.length) {
    wanted.add('contingency-zonas');
    upsertSource(map, sourceId('contingency-zonas'), contingency.zonas as any);
    upsertFillLayer(map, 'contingency-zonas', { flatOpacity: 0.35 });
    upsertLineLayer(map, 'contingency-zonas');
    try {
      if (map.getLayer(fillId('contingency-zonas'))) {
        map.setPaintProperty(fillId('contingency-zonas'), 'fill-color', '#fb923c');
        map.setPaintProperty(fillId('contingency-zonas'), 'fill-opacity', 0.35);
      }
      if (map.getLayer(lineId('contingency-zonas'))) {
        map.setPaintProperty(lineId('contingency-zonas'), 'line-color', '#f97316');
        map.setPaintProperty(lineId('contingency-zonas'), 'line-width', 2);
      }
    } catch {
      /* ignore */
    }
  }

  if (contingency?.rotas?.features?.length) {
    wanted.add('contingency-rotas');
    upsertSource(map, sourceId('contingency-rotas'), contingency.rotas as any);
    upsertLineLayer(map, 'contingency-rotas');
    try {
      if (map.getLayer(lineId('contingency-rotas'))) {
        map.setPaintProperty(lineId('contingency-rotas'), 'line-color', '#38bdf8');
        map.setPaintProperty(lineId('contingency-rotas'), 'line-width', 3.5);
      }
    } catch {
      /* ignore */
    }
  }

  if (contingency?.pontos?.features?.length) {
    wanted.add('contingency-pontos');
    upsertSource(map, sourceId('contingency-pontos'), contingency.pontos as any);
    upsertCircleLayer(map, 'contingency-pontos');
    try {
      if (map.getLayer(circleId('contingency-pontos'))) {
        map.setPaintProperty(circleId('contingency-pontos'), 'circle-color', '#fbbf24');
        map.setPaintProperty(circleId('contingency-pontos'), 'circle-radius', 7);
        map.setPaintProperty(circleId('contingency-pontos'), 'circle-opacity', 0.95);
      }
    } catch {
      /* ignore */
    }
  }

  const existing = (map.__siniduLayerIds as string[] | undefined) || [];
  existing.forEach((layerName) => {
    if (!wanted.has(layerName)) removeLayerBundle(map, layerName);
  });
  map.__siniduLayerIds = Array.from(wanted);
}

const LIVE_SENSORS_SRC = 'src-live-sensors';
const LIVE_SENSORS_CLUSTER = 'live-sensors-cluster';
const LIVE_SENSORS_COUNT = 'live-sensors-count';
const LIVE_SENSORS_HALO = 'live-sensors-halo';
const LIVE_SENSORS_CORE = 'live-sensors-core';

function removeLayersAndSource(map: MapLibreMap, layerIds: string[], sourceIdToRemove: string) {
  layerIds.forEach((id) => {
    if (map.getLayer(id)) map.removeLayer(id);
  });
  if (map.getSource(sourceIdToRemove)) map.removeSource(sourceIdToRemove);
}

function upsertClusterSource(
  map: MapLibreMap,
  id: string,
  data: { type: 'FeatureCollection'; features: any[] },
  opts: { clusterMaxZoom: number; clusterRadius: number; layerIdsBeforeRecreate: string[] },
) {
  const existing = map.getSource(id);
  if (existing?.__siniduCluster) {
    existing.setData(data);
    return;
  }
  if (existing) {
    removeLayersAndSource(map, opts.layerIdsBeforeRecreate, id);
  }
  map.addSource(id, {
    type: 'geojson',
    data,
    cluster: true,
    clusterMaxZoom: opts.clusterMaxZoom,
    clusterRadius: opts.clusterRadius,
  });
  map.getSource(id).__siniduCluster = true;
}

/** Overlay vivo CEMADEN/estações no gêmeo 3D (17e.3) + cluster (17f.10). */
export function syncLiveSensorsOverlay(
  map: MapLibreMap,
  geojson: { type: 'FeatureCollection'; features: any[] } | null,
  visible: boolean,
) {
  const sensorLayerIds = [
    LIVE_SENSORS_COUNT,
    LIVE_SENSORS_CLUSTER,
    LIVE_SENSORS_HALO,
    LIVE_SENSORS_CORE,
  ];
  if (!visible || !geojson?.features?.length) {
    removeLayersAndSource(map, sensorLayerIds, LIVE_SENSORS_SRC);
    return;
  }

  upsertClusterSource(map, LIVE_SENSORS_SRC, geojson, {
    clusterMaxZoom: 13,
    clusterRadius: 48,
    layerIdsBeforeRecreate: sensorLayerIds,
  });

  if (!map.getLayer(LIVE_SENSORS_CLUSTER)) {
    map.addLayer({
      id: LIVE_SENSORS_CLUSTER,
      type: 'circle',
      source: LIVE_SENSORS_SRC,
      filter: ['has', 'point_count'],
      paint: {
        'circle-color': '#f43f5e',
        'circle-opacity': 0.78,
        'circle-radius': ['step', ['get', 'point_count'], 16, 5, 22, 15, 28],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.5,
      },
    });
  }

  if (!map.getLayer(LIVE_SENSORS_COUNT)) {
    map.addLayer({
      id: LIVE_SENSORS_COUNT,
      type: 'symbol',
      source: LIVE_SENSORS_SRC,
      filter: ['has', 'point_count'],
      layout: {
        'text-field': ['get', 'point_count_abbreviated'],
        'text-size': 11,
        'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
      },
      paint: { 'text-color': '#ffffff' },
    });
  }

  if (!map.getLayer(LIVE_SENSORS_HALO)) {
    map.addLayer({
      id: LIVE_SENSORS_HALO,
      type: 'circle',
      source: LIVE_SENSORS_SRC,
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-color': ['coalesce', ['get', '_fill'], '#f43f5e'],
        'circle-opacity': 0.28,
        'circle-radius': 18,
        'circle-blur': 0.6,
        'circle-stroke-width': 0,
      },
    });
  }

  if (!map.getLayer(LIVE_SENSORS_CORE)) {
    map.addLayer({
      id: LIVE_SENSORS_CORE,
      type: 'circle',
      source: LIVE_SENSORS_SRC,
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-color': ['coalesce', ['get', '_fill'], '#f43f5e'],
        'circle-opacity': ['coalesce', ['get', '_fillOpacity'], 0.92],
        'circle-radius': ['coalesce', ['get', '_radius'], 8],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 1.5,
      },
    });
  }

  try {
    map.moveLayer(LIVE_SENSORS_CLUSTER);
    map.moveLayer(LIVE_SENSORS_COUNT);
    map.moveLayer(LIVE_SENSORS_HALO);
    map.moveLayer(LIVE_SENSORS_CORE);
  } catch {
    /* ignore */
  }
}

/** Pulso do halo dos sensores vivos (chamar via rAF). */
export function pulseLiveSensorsHalo(map: MapLibreMap, tMs: number) {
  if (!map.getLayer(LIVE_SENSORS_HALO)) return;
  const phase = (tMs % 1800) / 1800;
  const radius = 14 + phase * 16;
  const opacity = 0.38 * (1 - phase);
  try {
    map.setPaintProperty(LIVE_SENSORS_HALO, 'circle-radius', radius);
    map.setPaintProperty(LIVE_SENSORS_HALO, 'circle-opacity', opacity);
  } catch {
    /* style mid-transition */
  }
}

const CRITICAL_POIS_SRC = 'src-critical-pois';
const CRITICAL_POIS_CLUSTER = 'critical-pois-cluster';
const CRITICAL_POIS_COUNT = 'critical-pois-count';
const CRITICAL_POIS_CIRCLE = 'critical-pois-circle';
const CRITICAL_POIS_LABEL = 'critical-pois-label';

const URBAN_CTX_SRC = 'src-urban-context';
const URBAN_CTX_FILL = 'urban-context-fill';
const URBAN_CTX_LINE = 'urban-context-line';

const EDIF_MVT_SRC = 'src-edificacoes-mvt';
const EDIF_MVT_EXT = 'extrusion-edificacoes-mvt';
const EDIF_MVT_LINE = 'line-edificacoes-mvt';

/** Remove overlay LOD1 — UI pausada (qualidade insuficiente). */
export function clearEdificacoesMvt(map: MapLibreMap) {
  removeLayersAndSource(map, [EDIF_MVT_EXT, EDIF_MVT_LINE], EDIF_MVT_SRC);
}

/** POIs críticos INEP/CNES/abrigos com rótulos (17f.3) + cluster (17f.10). */
export function syncCriticalPoisOverlay(
  map: MapLibreMap,
  geojson: { type: 'FeatureCollection'; features: any[] } | null,
  visible: boolean,
) {
  const poiLayerIds = [
    CRITICAL_POIS_COUNT,
    CRITICAL_POIS_CLUSTER,
    CRITICAL_POIS_LABEL,
    CRITICAL_POIS_CIRCLE,
  ];
  if (!visible || !geojson?.features?.length) {
    removeLayersAndSource(map, poiLayerIds, CRITICAL_POIS_SRC);
    return;
  }

  upsertClusterSource(map, CRITICAL_POIS_SRC, geojson, {
    clusterMaxZoom: 13,
    clusterRadius: 52,
    layerIdsBeforeRecreate: poiLayerIds,
  });

  if (!map.getLayer(CRITICAL_POIS_CLUSTER)) {
    map.addLayer({
      id: CRITICAL_POIS_CLUSTER,
      type: 'circle',
      source: CRITICAL_POIS_SRC,
      filter: ['has', 'point_count'],
      paint: {
        'circle-color': '#38bdf8',
        'circle-opacity': 0.82,
        'circle-radius': ['step', ['get', 'point_count'], 15, 8, 20, 20, 26],
        'circle-stroke-color': '#0f172a',
        'circle-stroke-width': 1.4,
      },
    });
  }

  if (!map.getLayer(CRITICAL_POIS_COUNT)) {
    map.addLayer({
      id: CRITICAL_POIS_COUNT,
      type: 'symbol',
      source: CRITICAL_POIS_SRC,
      filter: ['has', 'point_count'],
      layout: {
        'text-field': ['get', 'point_count_abbreviated'],
        'text-size': 11,
        'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
      },
      paint: { 'text-color': '#0f172a' },
    });
  }

  if (!map.getLayer(CRITICAL_POIS_CIRCLE)) {
    map.addLayer({
      id: CRITICAL_POIS_CIRCLE,
      type: 'circle',
      source: CRITICAL_POIS_SRC,
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-color': ['coalesce', ['get', '_fill'], '#38bdf8'],
        'circle-opacity': ['coalesce', ['get', '_fillOpacity'], 0.95],
        'circle-radius': ['coalesce', ['get', '_radius'], 7],
        'circle-stroke-color': ['coalesce', ['get', '_stroke'], '#0f172a'],
        'circle-stroke-width': 1.4,
      },
    });
  }

  if (!map.getLayer(CRITICAL_POIS_LABEL)) {
    map.addLayer({
      id: CRITICAL_POIS_LABEL,
      type: 'symbol',
      source: CRITICAL_POIS_SRC,
      filter: ['!', ['has', 'point_count']],
      layout: {
        'text-field': ['coalesce', ['get', 'label'], ['get', 'nome'], ''],
        'text-size': 11,
        'text-offset': [0, 1.15],
        'text-anchor': 'top',
        'text-max-width': 10,
        'text-font': ['Open Sans Regular', 'Arial Unicode MS Regular'],
        'text-optional': true,
        'symbol-sort-key': [
          'match',
          ['get', 'categoria'],
          'abrigo',
          0,
          'saude',
          1,
          'escola',
          2,
          3,
        ],
      },
      paint: {
        'text-color': '#f8fafc',
        'text-halo-color': '#0f172a',
        'text-halo-width': 1.4,
        'text-opacity': [
          'interpolate',
          ['linear'],
          ['zoom'],
          12,
          0,
          13.2,
          0.85,
          15,
          1,
        ],
      },
    });
  }

  try {
    map.moveLayer(CRITICAL_POIS_CLUSTER);
    map.moveLayer(CRITICAL_POIS_COUNT);
    map.moveLayer(CRITICAL_POIS_CIRCLE);
    map.moveLayer(CRITICAL_POIS_LABEL);
  } catch {
    /* ignore */
  }
}

/** Hidrografia / vias / curvas de nível no gêmeo 3D (17f.6). */
export function syncUrbanContextOverlay(
  map: MapLibreMap,
  geojson: { type: 'FeatureCollection'; features: any[] } | null,
  visible: boolean,
  opacity = 1,
) {
  if (!visible || !geojson?.features?.length) {
    if (map.getLayer(URBAN_CTX_LINE)) map.removeLayer(URBAN_CTX_LINE);
    if (map.getLayer(URBAN_CTX_FILL)) map.removeLayer(URBAN_CTX_FILL);
    if (map.getSource(URBAN_CTX_SRC)) map.removeSource(URBAN_CTX_SRC);
    return;
  }

  upsertSource(map, URBAN_CTX_SRC, geojson);
  const o = Math.max(0, Math.min(1, opacity));

  if (!map.getLayer(URBAN_CTX_FILL)) {
    map.addLayer({
      id: URBAN_CTX_FILL,
      type: 'fill',
      source: URBAN_CTX_SRC,
      filter: POLYGON_FILTER,
      paint: {
        'fill-color': ['coalesce', ['get', '_fill'], '#0284c7'],
        'fill-opacity': ['*', o, ['coalesce', ['get', '_fillOpacity'], 0.35]],
      },
    });
  } else {
    try {
      map.setPaintProperty(URBAN_CTX_FILL, 'fill-opacity', [
        '*',
        o,
        ['coalesce', ['get', '_fillOpacity'], 0.35],
      ]);
    } catch {
      /* ignore */
    }
  }

  if (!map.getLayer(URBAN_CTX_LINE)) {
    map.addLayer({
      id: URBAN_CTX_LINE,
      type: 'line',
      source: URBAN_CTX_SRC,
      filter: ['any', POLYGON_FILTER, LINE_FILTER],
      paint: {
        'line-color': ['coalesce', ['get', '_stroke'], '#94a3b8'],
        'line-width': ['coalesce', ['get', '_strokeWidth'], 1.2],
        'line-opacity': o,
      },
    });
  } else {
    try {
      map.setPaintProperty(URBAN_CTX_LINE, 'line-opacity', o);
    } catch {
      /* ignore */
    }
  }

  try {
    map.moveLayer(URBAN_CTX_FILL);
    map.moveLayer(URBAN_CTX_LINE);
  } catch {
    /* ignore */
  }
}
