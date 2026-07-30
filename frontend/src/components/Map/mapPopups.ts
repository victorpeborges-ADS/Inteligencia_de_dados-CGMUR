/**
 * 20f.2 — Popup HTML builders e helpers `onEachFeature`/`pointToLayer` extraídos de `MapContainer.tsx`.
 * Mantém exatamente a mesma lógica/markup; apenas move o código para reduzir o tamanho do componente.
 */
import L from 'leaflet';
import {
  DEPENDENCIA_LABELS,
  TIPO_EQUIPAMENTO_LABELS,
  getDependenciaColor,
  getEducacaoEtapa,
  getEquipamentoTipo,
  markerRadiusFromMatriculas,
  markerRadiusFromTipo,
  type EducacaoEtapaId,
} from '@/config/educacaoInep';

export const layerTitles: Record<string, string> = {
  municipio: 'Limite Municipal',
  bairros: 'Bairros',
  territorios_especiais: 'Territórios Especiais',
  infraestrutura: 'Equipamentos e redes',
  educacao: 'Educação (escolas / creches / faculdades)',
  socioeconomico: 'Socioeconômico',
  cobertura: 'Uso do Solo',
  lst_observada: 'LST observada',
  vulnerabilidade: 'Vulnerabilidade',
  inundacao: 'Risco de Inundação',
  alertas: 'Alertas',
  desastres: 'Desastres',
  saneamento_drenagem: 'Saneamento e Drenagem',
  adaptacao_climatica: 'Adaptação Climática',
  prioridade_planejamento: 'Prioridade de Planejamento',
  risco_consolidado: 'Risco consolidado',
  lacunas_dados: 'Lacunas de Dados',
  saude_risco: 'Saúde × Risco',
  seguranca_publica: 'Segurança Pública',
  vulnerabilidade_multidimensional: 'Vulnerabilidade Multidimensional',
};

/** Monta o handler `onEachFeature` (popup HTML) de uma camada vetorial de acordo com as propriedades disponíveis. */
export function createFeaturePopupHandler(layerName: string, lstIdentifyActive: boolean) {
  return (feature: any, layer: any) => {
    const props = feature.properties || {};
    let popupContent = '<div class="p-1 font-sans text-xs min-w-[220px] max-w-[320px]">';
    popupContent += `<p class="mb-1 text-[10px] font-bold uppercase tracking-wide text-indigo-300">${layerTitles[layerName] || layerName}</p>`;

    if (props.nome) {
      popupContent += `<h4 class="font-bold text-sm text-zinc-100 border-b border-zinc-700 pb-1 mb-1">${props.nome}</h4>`;
    }

    if (props.tipo) {
      const tipoLabel = TIPO_EQUIPAMENTO_LABELS[String(props.tipo).toLowerCase()] || props.tipo;
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Tipo:</span> <span class="font-semibold text-teal-200">${tipoLabel}</span></p>`;
    }

    if (props.tipo_label && !props.tipo) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Tipo:</span> <span class="font-semibold text-fuchsia-200">${props.tipo_label}</span></p>`;
    }
    if (props.populacao_estimada != null) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">População est.:</span> ${Number(props.populacao_estimada).toLocaleString('pt-BR')}</p>`;
    }
    if (props.codigo_oficial) {
      popupContent += `<p class="mb-1 text-[10px] text-zinc-500">Código: ${props.codigo_oficial}</p>`;
    }

    if (props.codigo_inep) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Código INEP:</span> ${props.codigo_inep}</p>`;
    }
    if (props.dependencia) {
      const dep = DEPENDENCIA_LABELS[props.dependencia] || props.dependencia;
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Dependência:</span> <span class="font-semibold" style="color:${getDependenciaColor(props.dependencia)}">${dep}</span></p>`;
    }
    if (props.matriculas_ativas != null) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Matrículas (etapa):</span> <span class="font-semibold text-sky-200">${Number(props.matriculas_ativas).toLocaleString('pt-BR')}</span></p>`;
    }
    if (props.matriculas_total != null) {
      popupContent += `<p class="mb-1 text-[10px] text-zinc-500">Total escola: ${Number(props.matriculas_total).toLocaleString('pt-BR')} · Inf ${props.matriculas_infantil ?? 0} · Fund ${props.matriculas_fundamental ?? 0} · Méd ${props.matriculas_medio ?? 0}</p>`;
    }

    if (props.codigo_bairro) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Código Bairro:</span> ${props.codigo_bairro}</p>`;
    }

    if (props.populacao) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">População:</span> ${props.populacao.toLocaleString()}</p>`;
    }

    if (props.renda_media) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Renda Média:</span> R$ ${props.renda_media.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>`;
    }
    if (props.classe_renda) {
      const cls = props.classe_renda === 'ALTA' ? 'alta' : props.classe_renda === 'MEDIA' ? 'média' : 'baixa';
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Classe (no município):</span> <span class="font-semibold">${cls}</span></p>`;
    }
    if (props.deficits_censo && typeof props.deficits_censo === 'object') {
      const d = props.deficits_censo as Record<string, number>;
      const labels: Record<string, string> = {
        arborizacao: 'Sem arborização',
        calcada: 'Sem calçada',
        iluminacao: 'Sem iluminação',
        agua: 'Sem rede de água',
        esgoto: 'Esgoto inadequado',
        lixo: 'Lixo sem coleta',
        alfabetizacao: 'Baixa alfabetização',
      };
      popupContent += `<p class="mt-2 mb-1 text-[10px] font-bold uppercase text-amber-300">Déficits Censo 2022</p>`;
      Object.entries(labels).forEach(([key, label]) => {
        if (d[key] != null) {
          popupContent += `<p class="mb-0.5 text-[10px] text-zinc-400">${label}: <span class="text-amber-200">${d[key]}%</span></p>`;
        }
      });
    }

    if (props.densidade_demografica) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Densidade:</span> ${props.densidade_demografica.toLocaleString()} hab/km²</p>`;
    }

    if (props.nivel_alerta) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Nível do Alerta:</span> <span class="font-bold text-red-400">${props.nivel_alerta}</span></p>`;
      if (props.descricao) popupContent += `<p class="mt-2 text-zinc-300 italic border-l-2 border-amber-500 pl-2 text-[10px]">${props.descricao}</p>`;
    }

    if (layerName === 'desastres' || props.tipo_desastre) {
      const tipo = props.tipo_desastre || 'Evento';
      const dataFmt = props.data_ocorrencia
        ? new Date(`${String(props.data_ocorrencia).slice(0, 10)}T12:00:00`).toLocaleDateString('pt-BR')
        : '—';
      popupContent += `<h4 class="font-bold text-sm text-rose-200 border-b border-zinc-700 pb-1 mb-1">${tipo}</h4>`;
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Data:</span> <span class="font-semibold text-zinc-100">${dataFmt}</span></p>`;
      if (props.local || props.referencia) {
        popupContent += `<p class="mb-1"><span class="text-zinc-400">Local:</span> <span class="text-zinc-200">${props.local || props.referencia}</span></p>`;
      }
      if (props.descricao) {
        popupContent += `<p class="mt-2 mb-1 text-[10px] font-bold uppercase text-rose-300">O que aconteceu</p>`;
        popupContent += `<p class="mb-2 text-[11px] leading-snug text-zinc-300">${props.descricao}</p>`;
      }
      if (props.medidas) {
        popupContent += `<p class="mb-1 text-[10px] font-bold uppercase text-sky-300">Medidas tomadas</p>`;
        popupContent += `<p class="mb-2 text-[11px] leading-snug text-zinc-300">${props.medidas}</p>`;
      }
      popupContent += `<p class="mb-1 text-[10px] font-bold uppercase text-amber-300">Impacto humano</p>`;
      const fmtN = (v: unknown) =>
        v == null ? '—' : Number(v).toLocaleString('pt-BR');
      popupContent += `<p class="mb-0.5 text-[11px] text-zinc-400">Mortos: <span class="font-semibold text-rose-200">${fmtN(props.mortos)}</span></p>`;
      popupContent += `<p class="mb-0.5 text-[11px] text-zinc-400">Feridos: <span class="font-semibold text-orange-200">${fmtN(props.feridos)}</span></p>`;
      popupContent += `<p class="mb-0.5 text-[11px] text-zinc-400">Desalojados: <span class="font-semibold text-amber-200">${fmtN(props.desalojados)}</span></p>`;
      popupContent += `<p class="mb-0.5 text-[11px] text-zinc-400">Desabrigados: <span class="font-semibold text-amber-100">${fmtN(props.desabrigados)}</span></p>`;
      popupContent += `<p class="mb-2 text-[11px] text-zinc-400">Altamente prejudicados: <span class="font-semibold text-zinc-100">${fmtN(props.prejudicados ?? props.populacao_afetada)}</span></p>`;
      const custo = props.custo_resposta_estimado ?? props.danos_materiais;
      if (custo != null) {
        popupContent += `<p class="mb-1"><span class="text-zinc-400">Custo estimado (resposta/danos):</span> <span class="font-semibold text-emerald-200">R$ ${Number(custo).toLocaleString('pt-BR', { maximumFractionDigits: 0 })}</span></p>`;
      }
      if (props.impacto_nota) {
        popupContent += `<p class="mb-1 text-[9px] italic text-zinc-500">${props.impacto_nota}</p>`;
      }
      if (props.link_noticia) {
        const label = props.link_label || 'Matéria / balanço público';
        popupContent += `<p class="mt-2 mb-1"><a href="${props.link_noticia}" target="_blank" rel="noopener noreferrer" class="text-[11px] font-semibold text-sky-300 underline hover:text-sky-200">${label} ↗</a></p>`;
      }
    }

    if (props.classe_uso) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Uso do Solo (MapBiomas):</span> <span class="font-semibold text-zinc-300">${props.classe_uso}</span></p>`;
    }

    if (props.indice_vulnerabilidade !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">IVC:</span> <span class="font-bold text-rose-300">${props.indice_vulnerabilidade}</span></p>`;
    }

    if (props.indice_risco_inundacao !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">IRI:</span> <span class="font-bold text-sky-300">${props.indice_risco_inundacao}</span></p>`;
      if (props.hidrografia_proximidade_score !== undefined) {
        popupContent += `<p class="mb-1 text-[10px] text-zinc-500">Prox. hidrografia: ${props.hidrografia_proximidade_score} · Impermeab.: ${props.impermeabilizacao_score ?? '—'}</p>`;
      }
    }

    if (props.capacidade_adaptacao !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Adaptação:</span> <span class="font-bold text-emerald-300">${props.capacidade_adaptacao}</span></p>`;
    }

    if (props.layer === 'risco_consolidado' && props.nivel) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Risco agora:</span> <span class="font-bold text-rose-300">${props.nivel}</span>`;
      if (props.score_sinidu != null) {
        popupContent += ` <span class="text-zinc-500">(score ${props.score_sinidu})</span>`;
      }
      popupContent += `</p>`;
      if (props.alerta_vivo) {
        popupContent += `<p class="mb-1"><span class="text-zinc-400">Alerta vivo:</span> <span class="font-bold text-amber-300">${props.alerta_vivo}</span></p>`;
      }
    }
    if (props.prioridade_planejamento !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Prioridade:</span> <span class="font-bold text-fuchsia-300">${props.prioridade_planejamento}</span>`;
      if (props.classe_prioridade) {
        popupContent += ` <span class="text-[10px] text-fuchsia-200/80">(${props.classe_prioridade})</span>`;
      }
      popupContent += `</p>`;
      if (props.classificacao_relativa) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-500">Classe relativa ao município (tertil intra-urbano)</p>`;
      }
    }

    if (props.risco_drenagem !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Risco drenagem:</span> <span class="font-bold text-cyan-300">${props.risco_drenagem}</span>`;
      if (props.classe_drenagem) {
        popupContent += ` <span class="text-[10px] text-cyan-200/80">(${props.classe_drenagem})</span>`;
      }
      popupContent += `</p>`;
      if (props.impermeabilizacao_score !== undefined) {
        popupContent += `<p class="mb-1 text-[10px] text-zinc-500">IRI ${props.indice_risco_inundacao ?? '—'} · Impermeab. ${props.impermeabilizacao_score} · Hidrografia ${props.hidrografia_proximidade_score ?? '—'}</p>`;
      }
      if (props.snis?.deficit_saneamento_pct !== undefined) {
        popupContent += `<p class="mb-1 text-[10px] text-zinc-500">Déficit SNIS esgoto/água: ${props.snis.deficit_saneamento_pct}% (${props.snis.ano_referencia ?? '—'})</p>`;
      }
      if (props.score_explicacao) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-600">${props.score_explicacao}</p>`;
      }
    }

    if (props.maturidade_dados !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Maturidade dos dados:</span> <span class="font-bold text-indigo-300">${props.maturidade_dados}%</span></p>`;
      if (props.lacunas_prioritarias) {
        popupContent += `<p class="mb-1"><span class="text-zinc-400">Lacunas:</span> <span class="text-zinc-300">${props.lacunas_prioritarias}</span></p>`;
      }
    }

    if (props.tipo && props.feature_kind === 'estabelecimento') {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Tipo:</span> ${props.tipo}${props.leitos_sus ? ` · ${props.leitos_sus} leitos SUS` : ''}</p>`;
    }
    if (props.pressao_assistencial !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Pressão assistencial:</span> <span class="font-bold">${props.pressao_assistencial}</span></p>`;
    }
    if (props.cobertura_classe) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Classe:</span> <span class="font-bold">${props.cobertura_classe}</span></p>`;
    }

    if (props.bairro) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Bairro:</span> ${props.bairro}</p>`;
    }
    if (props.cobertura_classe) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Cobertura:</span> <span class="font-bold">${props.cobertura_classe}</span></p>`;
    }
    if (props.distancia_maior_risco_km !== undefined && props.distancia_maior_risco_km !== null) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Dist. maior risco:</span> ${props.distancia_maior_risco_km} km</p>`;
    }
    if (props.taxa_violenta_100k !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Taxa violenta / 100k:</span> ${props.taxa_violenta_100k}</p>`;
    }
    if (props.intensidade_seguranca !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Intensidade local:</span> <span class="font-bold text-orange-300">${props.intensidade_seguranca}</span>`;
      if (props.classe_intensidade) {
        popupContent += ` <span class="text-[10px] text-orange-200/80">(${props.classe_intensidade})</span>`;
      }
      popupContent += `</p>`;
      if (props.classificacao_relativa) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-500">Classe relativa ao município (tertil intra-urbano)</p>`;
      }
      if (props.score_explicacao) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-600">${props.score_explicacao}</p>`;
      }
    }

    if (props.indice_vm !== undefined) {
      popupContent += `<p class="mb-1"><span class="text-zinc-400">Índice VM:</span> <span class="font-bold text-purple-300">${props.indice_vm}</span>`;
      if (props.classe_vm) {
        popupContent += ` <span class="text-[10px] text-purple-200/80">(${props.classe_vm})</span>`;
      }
      popupContent += `</p>`;
      if (props.classificacao_relativa) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-500">Classe relativa ao município (tertil intra-urbano)</p>`;
      }
      if (props.score_explicacao) {
        popupContent += `<p class="mb-1 text-[9px] text-zinc-600">${props.score_explicacao}</p>`;
      }
    }
    if (props.vulnerabilidade_multidimensional) {
      popupContent += `<p class="mb-1 font-bold text-fuchsia-300">⚠ Vulnerabilidade multidimensional</p>`;
    }

    if (props.score_componentes && props.layer === 'prioridade_planejamento') {
      popupContent += `
        <div class="mt-2 rounded-md border border-fuchsia-500/30 bg-fuchsia-950/30 p-2">
          <p class="mb-1 text-[10px] font-bold uppercase text-fuchsia-200">Composição do score</p>
          <p class="text-[10px] text-zinc-300">Vulnerabilidade: +${props.score_componentes.vulnerabilidade_pct} pts</p>
          <p class="text-[10px] text-zinc-300">Inundação: +${props.score_componentes.inundacao_pct} pts</p>
          <p class="text-[10px] text-zinc-300">Déficit de adaptação: +${props.score_componentes.deficit_adaptacao_pct} pts</p>
          ${props.score_explicacao ? `<p class="mt-1 text-[9px] text-zinc-500">${props.score_explicacao}</p>` : ''}
        </div>
      `;
    } else if (props.score_componentes) {
      popupContent += `
        <div class="mt-2 rounded-md border border-fuchsia-500/30 bg-fuchsia-950/30 p-2">
          <p class="mb-1 text-[10px] font-bold uppercase text-fuchsia-200">Por que este score?</p>
          <p class="text-[10px] text-zinc-300">Vulnerabilidade: +${props.score_componentes.vulnerabilidade_pct} pts</p>
          <p class="text-[10px] text-zinc-300">Inundação: +${props.score_componentes.inundacao_pct} pts</p>
          <p class="text-[10px] text-zinc-300">Déficit de adaptação: +${props.score_componentes.deficit_adaptacao_pct} pts</p>
          ${props.score_explicacao ? `<p class="mt-1 text-[9px] text-zinc-500">${props.score_explicacao}</p>` : ''}
        </div>
      `;
    }

    if (props.qualidade_dado) {
      const q = props.qualidade_dado;
      const qualityColor =
        q === 'Oficial'
          ? 'text-emerald-300 border-emerald-500/40 bg-emerald-950/30'
          : q === 'Referencia'
            ? 'text-sky-300 border-sky-500/40 bg-sky-950/30'
            : q === 'Estimado'
              ? 'text-amber-300 border-amber-500/40 bg-amber-950/30'
              : 'text-zinc-300 border-zinc-500/40 bg-zinc-950/30';
      popupContent += `<p class="mt-2"><span class="rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase ${qualityColor}">${props.qualidade_dado}</span></p>`;
    }

    if (props.fonte_referencia) {
      popupContent += `<p class="mt-2 border-t border-zinc-800 pt-1 text-[10px] text-zinc-500">${props.fonte_referencia}</p>`;
    }

    popupContent += '</div>';
    // Com LST ativa, o clique identifica temperatura GeoReDUS (não abre popup vetorial).
    if (lstIdentifyActive) {
      layer.unbindPopup?.();
      return;
    }
    layer.bindPopup(popupContent);
  };
}

/** Monta o handler `pointToLayer` (marcadores/círculos) de acordo com a camada. */
export function createPointToLayer(
  layerName: string,
  opts: { educacaoEtapa: EducacaoEtapaId; showEducacaoBuffer: boolean; educacaoRaioM: number },
) {
  const { educacaoEtapa, showEducacaoBuffer, educacaoRaioM } = opts;
  return (feature: any, latlng: L.LatLngExpression) => {
    if (layerName === 'saude_risco') {
      if (feature?.properties?.feature_kind !== 'estabelecimento') {
        return L.circleMarker(latlng, { radius: 0, fillOpacity: 0, opacity: 0 });
      }
      const cls = feature?.properties?.cobertura_classe;
      const color = cls === 'ADEQUADA' ? '#16a34a' : cls === 'ATENCAO' ? '#eab308' : '#ef4444';
      const tipo = feature?.properties?.tipo;
      const radius = tipo === 'HOSPITAL' ? 10 : tipo === 'SAMU' ? 9 : 7;
      return L.circleMarker(latlng, { radius, fillColor: color, color: '#fff', weight: 2, fillOpacity: 0.95 });
    }
    if (layerName === 'infraestrutura') {
      const tipo = String(feature?.properties?.tipo || '').toLowerCase();
      if (tipo === 'via') {
        return L.circleMarker(latlng, { radius: 0, fillOpacity: 0, opacity: 0 });
      }
      const tipoOpt = getEquipamentoTipo(tipo);
      const dep = String(feature?.properties?.dependencia || '').toLowerCase();
      const border = getDependenciaColor(dep);
      const size = Math.max(18, markerRadiusFromTipo(tipo) * 2 + 4);
      const html = `<div title="${tipoOpt.label}" style="
        width:${size}px;height:${size}px;border-radius:9999px;
        background:${tipoOpt.color};border:2.5px solid ${border};
        box-shadow:0 0 0 1px rgba(15,23,42,.55);
        display:flex;align-items:center;justify-content:center;
        color:#fff;font:700 9px/1 ui-sans-serif,system-ui,sans-serif;
        letter-spacing:-0.02em;">${tipoOpt.short}</div>`;
      return L.marker(latlng, {
        icon: L.divIcon({
          className: 'equipamento-marker',
          html,
          iconSize: [size, size],
          iconAnchor: [size / 2, size / 2],
        }),
      });
    }
    if (layerName === 'educacao') {
      const props = feature?.properties || {};
      const color =
        educacaoEtapa === 'todas' && props.dependencia
          ? getDependenciaColor(props.dependencia)
          : getEducacaoEtapa(educacaoEtapa).color;
      const matriculas = Number(props.matriculas_ativas ?? props.matriculas_total ?? 0);
      const radius = markerRadiusFromMatriculas(matriculas);
      const marker = L.circleMarker(latlng, {
        radius,
        fillColor: color,
        color: '#fff',
        weight: 1.5,
        fillOpacity: 0.92,
      });
      if (!showEducacaoBuffer) return marker;
      const buffer = L.circle(latlng, {
        radius: educacaoRaioM,
        color,
        weight: 1,
        opacity: 0.45,
        fillColor: color,
        fillOpacity: 0.06,
      });
      return L.layerGroup([buffer, marker]);
    }
    const color = layerName === 'desastres' ? '#ef4444' : '#a78bfa';
    return L.circleMarker(latlng, {
      radius: layerName === 'desastres' ? 7 : 5,
      fillColor: color,
      color: '#f8fafc',
      weight: 1.5,
      opacity: 1,
      fillOpacity: 0.85,
    });
  };
}

/** Popup HTML para features de mancha de simulação (flood/heat/etc.). */
export function buildSimulationFeaturePopup(props: Record<string, any>): string {
  let content = `<div class="p-2 font-sans text-xs">
                <h4 class="font-bold text-sm text-zinc-100 mb-1 border-b border-zinc-700 pb-1">${props.name || 'Mancha Simulada'}</h4>`;
  if (props.temp_increase_celsius != null) {
    content += `<p class="text-red-400 font-semibold">ΔT: +${props.temp_increase_celsius}°C</p>`;
    if (props.temp_surface_celsius != null) {
      content += `<p class="text-orange-300">Superfície est.: ${props.temp_surface_celsius}°C</p>`;
    }
    if (props.heat_band) {
      content += `<p class="text-amber-300">Faixa: ${props.heat_band}</p>`;
    }
    if (props.vegetacao_pct != null) {
      content += `<p class="text-lime-300">Vegetação: ${props.vegetacao_pct}%</p>`;
    }
  }
  if (props.precipitation_mm) {
    content += `<p class="text-sky-400 font-semibold">Chuva: ${props.precipitation_mm} mm</p>`;
  }
  if (props.water_level_m) {
    content += `<p class="text-sky-300">Cota simulada: ${props.water_level_m} m</p>`;
  }
  if (props.depth_band) {
    content += `<p class="text-blue-300">Faixa: ${props.depth_band}</p>`;
  }
  if (props.intensity_pct) {
    content += `<p class="text-sky-400 font-semibold">Impermeabilização: +${props.intensity_pct}%</p>`;
  }
  if (props.description) content += `<p class="mt-1 text-zinc-400 text-[10px]">${props.description}</p>`;
  content += '</div>';
  return content;
}

/** Popup HTML para features do overlay regional (municípios do escopo / referência de comparação). */
export function buildRegionalFeaturePopup(props: Record<string, any>): string {
  const kind = props.feature_kind === 'referencia_comparacao' ? 'Referência de comparação' : 'Município regional';
  let content = `<div class="p-2 font-sans text-xs min-w-[180px]">
                <p class="mb-1 text-[10px] font-bold uppercase tracking-wide text-teal-300">${kind}</p>
                <h4 class="font-bold text-sm text-zinc-100 border-b border-zinc-700 pb-1 mb-1">${props.nome || 'Município'}</h4>`;
  if (props.uf) content += `<p class="text-zinc-400">${props.uf}</p>`;
  content += '</div>';
  return content;
}

/** Texto do tooltip de curvas de nível (DEM), ou `null` se a feature não tiver cota. */
export function buildContourTooltip(feature: any): string | null {
  const elev = feature.properties?.elevation_m;
  const res = feature.properties?.dem_resolution_m;
  const indexed = feature.properties?.index_contour;
  if (elev == null) return null;
  return res != null
    ? `${indexed ? 'Cota indexada ' : 'Cota '}${elev} m · DEM ~${res} m`
    : `Cota ${elev} m`;
}
