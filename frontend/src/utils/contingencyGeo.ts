import type { ContingencyPlan } from '@/utils/api';

export type ContingencyMapOverlay = {
  planId: number;
  nivel: string;
  cenario: string;
  zonas: GeoJSON.FeatureCollection;
  rotas: GeoJSON.FeatureCollection;
  pontos: GeoJSON.FeatureCollection;
};

function asGeometry(raw: unknown): GeoJSON.Geometry | null {
  if (!raw || typeof raw !== 'object') return null;
  const g = raw as Record<string, unknown>;
  if (g.type === 'Feature' && g.geometry) return g.geometry as GeoJSON.Geometry;
  if (typeof g.type === 'string' && g.coordinates != null) return raw as GeoJSON.Geometry;
  return null;
}

/** Converte plano de contingência em FeatureCollections para o mapa principal. */
export function contingencyPlanToOverlay(plan: ContingencyPlan | null | undefined): ContingencyMapOverlay | null {
  if (!plan?.id) return null;

  const zonas: GeoJSON.Feature[] = (plan.zonas_evacuacao || [])
    .map((z, i) => {
      const geometry = asGeometry(z?.geometry) || asGeometry(z?.geojson) || asGeometry(z);
      if (!geometry) return null;
      return {
        type: 'Feature' as const,
        properties: {
          nome: z?.nome || `Zona ${i + 1}`,
          capacidade: z?.capacidade,
          prioridade: z?.prioridade,
          kind: 'zona',
        },
        geometry,
      };
    })
    .filter(Boolean) as GeoJSON.Feature[];

  const rotas: GeoJSON.Feature[] = (plan.rotas_fuga || [])
    .map((r, i) => {
      const geometry =
        asGeometry(r?.geojson?.geometry) ||
        asGeometry(r?.geometry) ||
        asGeometry(r?.geojson) ||
        asGeometry(r);
      if (!geometry) return null;
      const aproximada = Boolean(r?.aproximada || r?.fonte_rota === 'fallback' || r?.malha_viaria === false);
      return {
        type: 'Feature' as const,
        properties: {
          nome: r?.nome || `Rota ${i + 1}`,
          aproximada,
          kind: 'rota',
        },
        geometry,
      };
    })
    .filter(Boolean) as GeoJSON.Feature[];

  const pontos: GeoJSON.Feature[] = (plan.pontos_apoio || [])
    .map((p, i) => {
      let geometry = asGeometry(p?.geometry) || asGeometry(p?.geojson);
      if (!geometry && Array.isArray(p?.coordinates) && p.coordinates.length >= 2) {
        geometry = { type: 'Point', coordinates: [p.coordinates[0], p.coordinates[1]] };
      }
      if (!geometry || geometry.type !== 'Point') return null;
      return {
        type: 'Feature' as const,
        properties: {
          nome: p?.nome || `Ponto ${i + 1}`,
          tipo: p?.tipo || 'apoio',
          kind: 'ponto',
        },
        geometry,
      };
    })
    .filter(Boolean) as GeoJSON.Feature[];

  if (!zonas.length && !rotas.length && !pontos.length) return null;

  return {
    planId: plan.id,
    nivel: plan.nivel_alerta || 'AMARELO',
    cenario: plan.cenario_tipo || 'INUNDACAO',
    zonas: { type: 'FeatureCollection', features: zonas },
    rotas: { type: 'FeatureCollection', features: rotas },
    pontos: { type: 'FeatureCollection', features: pontos },
  };
}
