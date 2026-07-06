/**
 * Testes manuais para floodInspect — rodar com: npx tsx frontend/scripts/test-floodInspect.ts
 */
import { buildInspectResult, inspectFloodFeature } from '../src/utils/floodInspect';

function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error(msg);
}

const flood = inspectFloodFeature({
  layer_type: 'flood_band',
  depth_band: 'moderada',
  depth_min_m: 0.35,
  depth_max_m: 0.8,
  precipitation_mm: 120,
});
assert(flood.scenario === 'flood', 'flood scenario');
assert(flood.depthCm != null && flood.depthCm >= 57 && flood.depthCm <= 58, `depthCm expected ~58 got ${flood.depthCm}`);

const heat = inspectFloodFeature({ temp_increase_celsius: 2.5 });
assert(heat.scenario === 'heat', 'heat scenario');

const full = buildInspectResult(-8.05, -34.88, {
  layer_type: 'flood_band',
  depth_band: 'superficial',
  depth_min_m: 0.05,
  depth_max_m: 0.35,
}, 12.0);
assert(full.inFlood === true, 'in flood');
assert(full.waterSurfaceM != null && full.waterSurfaceM > 12, 'water surface');

const none = buildInspectResult(-8.05, -34.88, null, 10.0);
assert(none.scenario === 'none', 'no feature');
assert(none.inFlood === false, 'not in flood');

const critica = inspectFloodFeature({
  layer_type: 'flood_band',
  depth_band: 'critica',
  depth_min_m: 0.8,
  depth_max_m: 1.5,
});
assert(critica.depthCm === 115, `critica depth ${critica.depthCm}`);

console.log('floodInspect: OK');
