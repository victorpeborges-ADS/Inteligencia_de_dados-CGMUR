/**
 * Smoke test — npx tsx scripts/test-solarPosition.ts
 */
import {
  computeSceneLighting,
  dateAtLocalHour,
  presetDefaultHour,
  solarPosition,
} from '../src/utils/solarPosition';

function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error(msg);
}

const noon = dateAtLocalHour(new Date('2026-03-21T00:00:00Z'), 12, -34.88);
const sunNoon = solarPosition(-8.05, -34.88, noon);
assert(sunNoon.elevacaoGraus > 40, `elevação meio-dia deveria ser >40, got ${sunNoon.elevacaoGraus}`);

const nightWhen = dateAtLocalHour(new Date('2026-03-21T00:00:00Z'), 21, -34.88);
const sunNight = solarPosition(-8.05, -34.88, nightWhen);
assert(sunNight.elevacaoGraus < 10, `elevação 21h deveria ser <10, got ${sunNight.elevacaoGraus}`);

const day = computeSceneLighting(-8.05, -34.88, 12, 'dia');
const night = computeSceneLighting(-8.05, -34.88, 21, 'noite');
assert(night.lightIntensity < day.lightIntensity, 'noite deveria ter menos intensidade');

assert(presetDefaultHour('entardecer') === 17.5, 'preset entardecer');
assert(presetDefaultHour('chuva') === 14, 'preset chuva');

console.log('ok — solarPosition (17f.1/17f.2)');
