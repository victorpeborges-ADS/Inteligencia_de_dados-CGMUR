/**
 * Smoke test — npx tsx scripts/test-mapNavAssist.ts
 */
import {
  bairrosFromGeoJSON,
  featureCentroid,
  makeBookmark,
  normalizeInBounds,
  SCENARIO_PRESETS,
} from '../src/utils/mapNavAssist';

function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error(msg);
}

const poly = {
  type: 'Polygon' as const,
  coordinates: [
    [
      [-34.9, -8.1],
      [-34.8, -8.1],
      [-34.8, -8.0],
      [-34.9, -8.0],
      [-34.9, -8.1],
    ],
  ],
};

const c = featureCentroid(poly);
assert(!!c && Math.abs(c[0] + 34.85) < 0.01, `centroid lng ${c}`);
assert(!!c && Math.abs(c[1] + 8.05) < 0.01, `centroid lat ${c}`);

const items = bairrosFromGeoJSON({
  features: [
    { geometry: poly, properties: { nome: 'Boa Viagem' } },
    { geometry: poly, properties: { nome: 'Centro' } },
  ],
});
assert(items.length === 2, '2 bairros');
assert(items[0].nome === 'Boa Viagem', 'ordenado');

const n = normalizeInBounds(-34.85, -8.05, [
  [-34.9, -8.1],
  [-34.8, -8.0],
]);
assert(Math.abs(n.x - 0.5) < 0.05, `x=${n.x}`);
assert(Math.abs(n.y - 0.5) < 0.05, `y=${n.y}`);

const bm = makeBookmark('Teste', {
  center: [-34.88, -8.05],
  zoom: 13,
  pitch: 60,
  bearing: -20,
});
assert(bm.name === 'Teste' && bm.id.startsWith('bm-'), 'bookmark');
assert(SCENARIO_PRESETS.length === 3, 'presets');

console.log('ok — mapNavAssist (17f.4)');
