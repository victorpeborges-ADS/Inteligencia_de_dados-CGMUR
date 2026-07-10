/** Lacunas que exigem trâmite institucional (convênio/credencial) — ver PLANO_LACUNAS_INSTITUCIONAIS.md */
export type InstitutionalGap = {
  rank: number;
  fonteId: string;
  nome: string;
  impactoScore: string;
  dificuldade: string;
  responsavel: string;
  prazo: string;
  acao: string;
  municipiosAfetados: number;
};

export const INSTITUTIONAL_GAPS: InstitutionalGap[] = [
  {
    rank: 1,
    fonteId: 'geosgb',
    nome: 'GeoSGB / CPRM',
    impactoScore: '±8 pts',
    dificuldade: 'Convênio',
    responsavel: 'MCID ↔ CPRM',
    prazo: '6 meses',
    acao: 'Trâmite convênio MCID–CPRM para litologia e susceptibilidade geológica',
    municipiosAfetados: 61,
  },
  {
    rank: 2,
    fonteId: 'brasil_mais',
    nome: 'Brasil MAIS',
    impactoScore: '±5 pts',
    dificuldade: 'Técnica + MCID',
    responsavel: 'Secretaria Nacional de Habitação',
    prazo: '2–3 meses',
    acao: 'API interna MCID ou carga batch acordada com equipe Brasil MAIS',
    municipiosAfetados: 61,
  },
  {
    rank: 3,
    fonteId: 'sirene',
    nome: 'SIRENE / MCTI',
    impactoScore: '±4 pts',
    dificuldade: 'Institucional',
    responsavel: 'MCID ↔ MCTI',
    prazo: '4 meses',
    acao: 'Credencial ou extract anual de emissões antrópicas por município',
    municipiosAfetados: 10,
  },
  {
    rank: 4,
    fonteId: 'adapta_brasil',
    nome: 'AdaptaBrasil / INPE',
    impactoScore: '±3 pts',
    dificuldade: 'Técnica',
    responsavel: 'INPE',
    prazo: 'Contínuo',
    acao: 'Substituir proxy MapBiomas quando credencial API INPE estiver disponível',
    municipiosAfetados: 61,
  },
  {
    rank: 5,
    fonteId: 'sinter',
    nome: 'SINTER / Receita',
    impactoScore: '±2 pts',
    dificuldade: 'Institucional',
    responsavel: 'Receita Federal',
    prazo: 'Avaliar',
    acao: 'Confirmar necessidade vs. dados IBGE/SICONFI já integrados',
    municipiosAfetados: 61,
  },
];

export function gapStatusFromCatalog(
  fonteId: string,
  bases: Array<{ id: string; status: string }>,
): string | null {
  return bases.find((b) => b.id === fonteId)?.status ?? null;
}
