/**
 * Testes do motor de recomendações — npx tsx frontend/scripts/test-territorialRecommendations.ts
 */
import { buildTerritorialRecommendations } from '../src/utils/territorialRecommendations';

function assert(cond: boolean, msg: string) {
  if (!cond) throw new Error(msg);
}

const recifeAltoRisco = buildTerritorialRecommendations({
  indicators: {
    codigo_ibge: '2611606',
    nome: 'Recife',
    uf: 'PE',
    populacao: 1600000,
    area_km2: 218,
    cobertura_vegetal_percent: 18,
    densidade_demografica: 7300,
    historico_desastres_count: 12,
    alertas_ativos_count: 8,
    renda_media_setores: 1200,
    renda_media_fonte: 'IBGE',
    danos_materiais_total: 0,
    score_sinidu: 72,
    media_ivc: 0.68,
    media_iri: 0.71,
    nota_capag: 'B',
    score_confiabilidade: 'MEDIA',
  },
  indices: {
    vulnerabilidade: [{ bairro_nome: 'Santo Amaro', indice_vulnerabilidade: 0.82 }],
    inundacao: [{ bairro_nome: 'Boa Viagem', indice_risco_inundacao: 0.79 }],
  } as never,
  maturity: {
    codigo_ibge: '2611606',
    nome: 'Recife',
    uf: 'PE',
    score: 22,
    completeness_score: 22,
    classificacao: 'Bronze',
    fontes: [],
    fontes_faltantes: [{ id: 'geosgb', nome: 'GeoSGB/CPRM', recomendacao: 'Convênio MCID–CPRM' }],
    fontes_parciais: [],
    resumo: '',
    calculado_em: '',
  },
  diagnostic: null,
  avgIvc: 0.68,
  avgIri: 0.71,
});

assert(recifeAltoRisco.length <= 5, 'max 5 recommendations');
assert(recifeAltoRisco.some((r) => r.id === 'cemaden-ativo'), 'expects CEMADEN rec');
assert(recifeAltoRisco.some((r) => r.id === 'simular-inundacao'), 'expects flood sim');
assert(recifeAltoRisco[0].priority === 'alta', 'top priority alta');
assert(recifeAltoRisco[0].evidence.length >= 1, 'explainability evidence');

const estavel = buildTerritorialRecommendations({
  indicators: {
    codigo_ibge: '0000000',
    nome: 'Teste',
    uf: 'XX',
    populacao: 10000,
    area_km2: 100,
    cobertura_vegetal_percent: 45,
    densidade_demografica: 100,
    historico_desastres_count: 0,
    alertas_ativos_count: 0,
    renda_media_setores: 1500,
    renda_media_fonte: 'IBGE',
    danos_materiais_total: 0,
    score_sinidu: 25,
    media_ivc: 0.3,
    media_iri: 0.28,
    nota_capag: 'A',
    score_confiabilidade: 'ALTA',
  },
  diagnostic: { headline: 'OK', narrativa_md: 'x' } as never,
});

assert(estavel.some((r) => r.id === 'explorar-territorio'), 'fallback exploration');

console.log('territorialRecommendations: OK');
