export type TemporalTemaId = 'mapbiomas' | 's2id' | 'inep' | 'lst' | 'pib';

export type TemporalTemaOption = {
  tema_id: TemporalTemaId;
  label: string;
  layer_id: string | null;
  anos: number[];
  padrao: number | null;
  context_only?: boolean;
  nota?: string | null;
};

export type TemporalOptionsResponse = {
  codigo_ibge: string;
  temas: Record<TemporalTemaId, TemporalTemaOption>;
};

/** Camada ativa → tema temporal */
export const LAYER_TO_TEMPORAL_TEMA: Partial<Record<string, TemporalTemaId>> = {
  cobertura: 'mapbiomas',
  desastres: 's2id',
  educacao: 'inep',
  lst_observada: 'lst',
};

/** Camadas que disparam referência PIB no painel temporal */
export const PIB_CONTEXT_LAYERS = new Set(['socioeconomico', 'vulnerabilidade', 'prioridade_planejamento']);

export function getTemporalTemaForLayer(layerId: string): TemporalTemaId | null {
  return LAYER_TO_TEMPORAL_TEMA[layerId] ?? null;
}

export function layerUsesAnoParam(layerId: string): boolean {
  return layerId in LAYER_TO_TEMPORAL_TEMA && layerId !== 'lst_observada';
}

export function buildLayerFetchParams(
  layerId: string,
  options: {
    educacaoEtapa?: string;
    territorioTipo?: string;
    layerAnoByTema?: Partial<Record<TemporalTemaId, number>>;
  },
): Record<string, string | number> | undefined {
  const params: Record<string, string | number> = {};
  const tema = getTemporalTemaForLayer(layerId);

  if (layerId === 'educacao' && options.educacaoEtapa) {
    params.etapa = options.educacaoEtapa;
  }

  if (layerId === 'territorios_especiais' && options.territorioTipo) {
    params.tipo = options.territorioTipo;
  }

  if (tema && options.layerAnoByTema?.[tema] != null) {
    if (layerUsesAnoParam(layerId)) {
      params.ano = options.layerAnoByTema[tema] as number;
    }
  }

  return Object.keys(params).length > 0 ? params : undefined;
}

export function resolveActiveTemporalTemas(
  activeLayers: string[],
  temporalOptions: TemporalOptionsResponse | null,
): TemporalTemaOption[] {
  if (!temporalOptions) return [];

  const temaIds = new Set<TemporalTemaId>();
  activeLayers.forEach((layerId) => {
    const tema = getTemporalTemaForLayer(layerId);
    if (tema) temaIds.add(tema);
    if (PIB_CONTEXT_LAYERS.has(layerId)) temaIds.add('pib');
  });

  return Array.from(temaIds)
    .map((id) => temporalOptions.temas[id])
    .filter((item): item is TemporalTemaOption => Boolean(item));
}
