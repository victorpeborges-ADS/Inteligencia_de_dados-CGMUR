/** Cor de destaque por camada — usada no painel "Camadas ativas". */
export const LAYER_CHIP_COLORS: Record<string, string> = {
  municipio: '#38bdf8',
  bairros: '#6366f1',
  territorios_especiais: '#c026d3',
  infraestrutura: '#ef4444',
  educacao: '#3b82f6',
  socioeconomico: '#22c55e',
  cobertura: '#10b981',
  lst_observada: '#f97316',
  vulnerabilidade: '#7f1d1d',
  inundacao: '#075985',
  risco_consolidado: '#dc2626',
  alertas: '#f43f5e',
  desastres: '#ef4444',
  saneamento_drenagem: '#0e7490',
  adaptacao_climatica: '#16a34a',
  prioridade_planejamento: '#be123c',
  lacunas_dados: '#16a34a',
  saude_risco: '#16a34a',
  seguranca_publica: '#7f1d1d',
  vulnerabilidade_multidimensional: '#581c87',
};

export function layerChipColor(layerId: string): string {
  return LAYER_CHIP_COLORS[layerId] || '#6366f1';
}
