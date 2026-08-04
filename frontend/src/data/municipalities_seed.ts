import type { MunicipalityOption } from '@/utils/api';

/** Catálogo piloto (8 municípios) — espelho de backend/seeds/municipios_seed_50.yaml.
 * Recife e Aracaju primeiro (BOOT_PRIORITY_IBGE_CODES).
 * Camutanga / Itamaracá: PE LiDAR (PE3D). */
export const BOOT_PRIORITY_IBGE_CODES = ['2611606', '2800308'] as const;

export const SEED_MUNICIPALITIES: MunicipalityOption[] = [
  { codigo_ibge: '2611606', nome: 'Recife', uf: 'PE', criterio: 'capital' },
  { codigo_ibge: '2800308', nome: 'Aracaju', uf: 'SE', criterio: 'capital' },
  { codigo_ibge: '2927408', nome: 'Salvador', uf: 'BA', criterio: 'capital' },
  { codigo_ibge: '3550308', nome: 'São Paulo', uf: 'SP', criterio: 'capital' },
  { codigo_ibge: '3304557', nome: 'Rio de Janeiro', uf: 'RJ', criterio: 'capital' },
  { codigo_ibge: '5300108', nome: 'Brasília', uf: 'DF', criterio: 'capital' },
  { codigo_ibge: '2603603', nome: 'Camutanga', uf: 'PE', criterio: 'lidar_pe3d' },
  { codigo_ibge: '2607604', nome: 'Ilha de Itamaracá', uf: 'PE', criterio: 'lidar_pe3d' },
];
