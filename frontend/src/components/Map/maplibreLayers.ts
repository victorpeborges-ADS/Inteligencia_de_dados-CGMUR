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
  if (map.getLayer(id)) return;
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

function upsertExtrusionLayer(map: MapLibreMap, layerName: string) {
  const id = extrusionId(layerName);
  if (map.getLayer(id)) return;
  map.addLayer({
    id,
    type: 'fill-extrusion',
    source: sourceId(layerName),
    filter: POLYGON_FILTER,
    paint: {
      'fill-extrusion-color': ['coalesce', ['get', '_fill'], '#0284c7'],
      'fill-extrusion-height': ['coalesce', ['get', '_extrusionHeightM'], 0.25],
      'fill-extrusion-opacity': 0.78,
      'fill-extrusion-base': 0,
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
    upsertFillLayer(map, 'simulation', { flatOpacity: 0.22 });
    upsertExtrusionLayer(map, 'simulation');
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
