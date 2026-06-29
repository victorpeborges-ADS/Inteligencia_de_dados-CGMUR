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

function upsertSource(map: MapLibreMap, id: string, data: { type: 'FeatureCollection'; features: any[] }) {
  if (map.getSource(id)) {
    map.getSource(id).setData(data);
  } else {
    map.addSource(id, { type: 'geojson', data });
  }
}

function upsertFillLayer(map: MapLibreMap, layerName: string) {
  const id = fillId(layerName);
  if (map.getLayer(id)) return;
  map.addLayer({
    id,
    type: 'fill',
    source: sourceId(layerName),
    filter: POLYGON_FILTER,
    paint: {
      'fill-color': ['coalesce', ['get', '_fill'], '#6366f1'],
      'fill-opacity': ['coalesce', ['get', '_fillOpacity'], 0.4],
    },
  });
}

function upsertLineLayer(map: MapLibreMap, layerName: string) {
  const id = lineId(layerName);
  if (map.getLayer(id)) return;
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
  [circleId(layerName), lineId(layerName), fillId(layerName)].forEach((id) => {
    if (map.getLayer(id)) map.removeLayer(id);
  });
  const sid = sourceId(layerName);
  if (map.getSource(sid)) map.removeSource(sid);
}

export function syncThematicLayers(
  map: MapLibreMap,
  activeLayers: string[],
  layerData: Record<string, any>,
  simGeoJSON: any | null,
  simContours: any | null = null,
  simFlowPaths: any | null = null,
) {
  const wanted = new Set<string>();

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
  });

  if (simGeoJSON?.features?.length) {
    wanted.add('simulation');
    upsertSource(map, sourceId('simulation'), enrichSimulationGeoJSON(simGeoJSON));
    upsertFillLayer(map, 'simulation');
    upsertLineLayer(map, 'simulation');
  }

  if (simContours?.features?.length) {
    wanted.add('sim-contours');
    upsertSource(map, sourceId('sim-contours'), enrichContourGeoJSON(simContours));
    upsertLineLayer(map, 'sim-contours');
  }

  if (simFlowPaths?.features?.length) {
    wanted.add('sim-flow');
    upsertSource(map, sourceId('sim-flow'), enrichFlowPathGeoJSON(simFlowPaths));
    upsertLineLayer(map, 'sim-flow');
  }

  const existing = (map.__siniduLayerIds as string[] | undefined) || [];
  existing.forEach((layerName) => {
    if (!wanted.has(layerName)) removeLayerBundle(map, layerName);
  });
  map.__siniduLayerIds = Array.from(wanted);
}
