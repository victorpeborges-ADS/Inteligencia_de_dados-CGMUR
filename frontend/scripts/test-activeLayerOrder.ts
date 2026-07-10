import {
  buildVectorRenderOrder,
  canReorderLayer,
  moveLayerInStack,
} from '../src/utils/activeLayerOrder';

function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(message);
}

const order = buildVectorRenderOrder(['cobertura', 'bairros', 'municipio', 'vulnerabilidade']);
assert(
  JSON.stringify(order) === JSON.stringify(['municipio', 'bairros', 'cobertura', 'vulnerabilidade']),
  `ordem de render inválida: ${order.join(',')}`,
);

assert(!canReorderLayer('municipio'), 'municipio não deve reordenar');
assert(
  moveLayerInStack(['municipio', 'bairros', 'cobertura'], 'municipio', 'up') === null,
  'municipio não deve mover',
);

const moved = moveLayerInStack(
  ['municipio', 'bairros', 'cobertura', 'vulnerabilidade'],
  'cobertura',
  'up',
);
assert(
  JSON.stringify(moved) === JSON.stringify(['municipio', 'bairros', 'vulnerabilidade', 'cobertura']),
  `move up falhou: ${moved?.join(',')}`,
);

console.log('test-activeLayerOrder: OK');
