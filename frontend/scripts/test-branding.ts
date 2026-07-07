/**
 * Testes branding institucional — npx tsx frontend/scripts/test-branding.ts
 */
import { PRESENTATION_DISCLAIMER, presentationDisclaimer } from '../src/config/branding';

function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error(msg);
}

const prev = process.env.NEXT_PUBLIC_INSTITUTIONAL_MODE;

process.env.NEXT_PUBLIC_INSTITUTIONAL_MODE = 'false';
assert(
  presentationDisclaimer() === PRESENTATION_DISCLAIMER.internal,
  'dev disclaimer',
);

process.env.NEXT_PUBLIC_INSTITUTIONAL_MODE = 'true';
assert(
  presentationDisclaimer() === PRESENTATION_DISCLAIMER.institutional,
  'institutional disclaimer',
);

process.env.NEXT_PUBLIC_INSTITUTIONAL_MODE = prev;

console.log('branding: OK');
