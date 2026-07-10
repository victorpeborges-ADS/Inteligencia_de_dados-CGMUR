export type RegionalEscopo = 'regiao_imediata' | 'mesorregiao';

export const REGIONAL_ESCOPO_LABELS: Record<RegionalEscopo, string> = {
  regiao_imediata: 'Região imediata (RM)',
  mesorregiao: 'Mesorregião',
};

export type RegionalOverlayResponse = {
  codigo_ibge: string;
  municipio_nome: string;
  uf: string;
  escopo: RegionalEscopo;
  mesorregiao?: { id: number; nome: string; tipo: string; uf?: string } | null;
  regiao_imediata?: { id: number; nome: string; tipo: string; uf?: string } | null;
  total_municipios_escopo: number;
  municipios_carregados_mapa: number;
  referencia_comparacao?: {
    codigo_ibge: string;
    nome: string;
    motivo: string;
  } | null;
  indicadores: {
    municipio: Record<string, unknown>;
    regional: Record<string, unknown>;
  };
  geojson: GeoJSON.FeatureCollection;
  nota?: string;
};
