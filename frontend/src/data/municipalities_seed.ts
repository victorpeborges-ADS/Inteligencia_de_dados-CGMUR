import type { MunicipalityOption } from '@/utils/api';

/** Catálogo piloto (6 municípios) — espelho de backend/seeds/municipios_seed_50.yaml.
 * Recife e Aracaju primeiro (BOOT_PRIORITY_IBGE_CODES). */
export const BOOT_PRIORITY_IBGE_CODES = ['2611606', '2800308'] as const;

export const SEED_MUNICIPALITIES: MunicipalityOption[] = [
  { codigo_ibge: '2611606', nome: 'Recife', uf: 'PE', criterio: 'capital' },
  { codigo_ibge: '2800308', nome: 'Aracaju', uf: 'SE', criterio: 'capital' },
  { codigo_ibge: '2927408', nome: 'Salvador', uf: 'BA', criterio: 'capital' },
  { codigo_ibge: '3550308', nome: 'São Paulo', uf: 'SP', criterio: 'capital' },
  { codigo_ibge: '3304557', nome: 'Rio de Janeiro', uf: 'RJ', criterio: 'capital' },
  { codigo_ibge: '5300108', nome: 'Brasília', uf: 'DF', criterio: 'capital' },
];
