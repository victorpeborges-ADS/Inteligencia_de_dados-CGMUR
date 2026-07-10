"""Interpretação IA pós-simulação pluvial e territorial — Sinidu+Clima Step 3."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from shapely.ops import unary_union
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.analytics import executive_snapshot
from app.models import Bairro, HistoricoDesastreS2ID, InfraestruturaUrbana, Municipio
from app.services.dem_processor import slope_analysis

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Esta é uma simulação exploratória. Não substitui estudos hidráulicos de engenharia. "
    "Para decisões oficiais, consulte a Defesa Civil."
)
DISCLAIMER_CALOR = (
    "Simulação exploratória de ilha de calor — não substitui medição de temperatura de superfície (LST) "
    "nem estudo microclimático. Para ações de saúde pública, consulte vigilância epidemiológica municipal."
)

TIPO_LABELS = {
    "chuva": "Chuva extrema",
    "asfalto": "Impermeabilização urbana",
    "vegetacao": "Perda de vegetação",
    "drenagem": "Déficit de drenagem",
    "calor": "Ilha de calor urbana",
}

EQUIPMENT_KEYWORDS = (
    "hospital",
    "escola",
    "ubs",
    "unidade",
    "saude",
    "saúde",
    "atendimento",
    "posto",
    "caps",
    "upa",
    "creche",
)


def _hazard_union(simulation: dict[str, Any]):
    fc = simulation.get("geometry") or {}
    features = fc.get("features") or []
    geoms = []
    for feat in features:
        props = feat.get("properties") or {}
        layer = props.get("layer_type")
        if layer and layer not in {"flood_band", "landslide", "heat_band"}:
            continue
        if not feat.get("geometry"):
            continue
        try:
            geoms.append(shape(feat["geometry"]))
        except Exception:
            continue
    if not geoms:
        for feat in features:
            if feat.get("geometry"):
                try:
                    geoms.append(shape(feat["geometry"]))
                except Exception:
                    pass
    if not geoms:
        return None
    merged = unary_union(geoms)
    return merged if not merged.is_empty else None


def _extract_bairros(simulation: dict[str, Any]) -> list[dict[str, Any]]:
    meta = simulation.get("simulation_meta") or {}
    exposures = meta.get("bairros_exposicao") or []
    if exposures:
        return [
            {
                "nome": row.get("bairro", ""),
                "exposicao_pct": row.get("exposicao_pct", row.get("delta_t_c")),
                "populacao_exposta": row.get("populacao_exposta", 0),
                "delta_t_c": row.get("delta_t_c"),
                "temp_local_c": row.get("temp_local_c") or row.get("temp_superficie_c"),
                "faixa_calor": row.get("faixa_calor"),
            }
            for row in exposures
            if row.get("bairro")
        ]
    return [{"nome": b, "exposicao_pct": None, "populacao_exposta": None} for b in (simulation.get("affected_bairros") or [])]


def _equipamentos_na_mancha(db: Session, muni: Municipio, hazard) -> list[dict[str, str]]:
    if hazard is None or hazard.is_empty:
        return []
    hazard_wkt = from_shape(hazard, srid=4326)
    rows = (
        db.query(InfraestruturaUrbana)
        .filter(
            InfraestruturaUrbana.municipio_id == muni.id,
            func.ST_Intersects(InfraestruturaUrbana.geom, hazard_wkt),
        )
        .limit(40)
        .all()
    )
    out: list[dict[str, str]] = []
    for row in rows:
        tipo = (row.tipo or "").lower()
        nome = row.nome or "Equipamento"
        if any(k in tipo or k in nome.lower() for k in EQUIPMENT_KEYWORDS):
            out.append({"tipo": row.tipo, "nome": nome})
    return out[:12]


def _historico_s2id(db: Session, muni: Municipio, area_km2: float) -> dict[str, Any]:
    events = (
        db.query(HistoricoDesastreS2ID)
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .order_by(HistoricoDesastreS2ID.data_ocorrencia.desc())
        .limit(15)
        .all()
    )
    if not events:
        return {"total": 0, "evento_similar": None}
    similar = None
    for ev in events:
        tipo = (ev.tipo_desastre or "").lower()
        if any(k in tipo for k in ("inund", "alag", "encher", "chuva", "desliz")):
            similar = ev
            break
    if similar is None:
        similar = events[0]
    ano = similar.data_ocorrencia.year if similar.data_ocorrencia else None
    return {
        "total": len(events),
        "evento_similar": {
            "ano": ano,
            "tipo": similar.tipo_desastre,
            "danos_materiais": float(similar.danos_materiais or 0),
            "populacao_afetada": int(similar.populacao_afetada or 0),
        },
    }


def extract_simulation_metrics(
    db: Session,
    muni: Municipio,
    simulation: dict[str, Any],
    *,
    parametro_atual: float,
    parametro_referencia: float | None = None,
    resultado_referencia: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hazard = _hazard_union(simulation)
    bairros = _extract_bairros(simulation)
    equipamentos = _equipamentos_na_mancha(db, muni, hazard)
    area = float(simulation.get("affected_area_km2") or 0)
    pop = int(simulation.get("affected_population") or 0)
    s2id = _historico_s2id(db, muni, area)

    delta_vs_referencia: dict[str, Any] | None = None
    if resultado_referencia:
        ref_area = float(resultado_referencia.get("affected_area_km2") or 0)
        ref_pop = int(resultado_referencia.get("affected_population") or 0)
        ref_bairros = set(resultado_referencia.get("affected_bairros") or [])
        scen_bairros = set(simulation.get("affected_bairros") or [])
        delta_area = area - ref_area
        delta_pop = pop - ref_pop
        pct = round((delta_area / ref_area) * 100, 1) if ref_area > 0 else None
        delta_vs_referencia = {
            "parametro_referencia": parametro_referencia,
            "parametro_atual": parametro_atual,
            "delta_area_km2": round(delta_area, 2),
            "delta_populacao": delta_pop,
            "delta_area_pct": pct,
            "bairros_novos": sorted(scen_bairros - ref_bairros),
            "bairros_removidos": sorted(ref_bairros - scen_bairros),
        }

    return {
        "area_afetada_km2": round(area, 2),
        "populacao_estimada_atingida": pop,
        "n_bairros_afetados": len(bairros),
        "bairros_afetados": bairros[:12],
        "n_equipamentos_na_mancha": len(equipamentos),
        "equipamentos": equipamentos,
        "delta_vs_referencia": delta_vs_referencia,
        "historico_s2id": s2id,
        "simulation_meta": simulation.get("simulation_meta") or {},
    }


def _deterministic_interpretation(
    muni: Municipio,
    metrics: dict[str, Any],
    *,
    tipo_simulacao: str,
    parametro_atual: float,
    parametro_referencia: float | None,
) -> dict[str, Any]:
    bairros = metrics.get("bairros_afetados") or []
    top3 = bairros[:3]
    equip = metrics.get("equipamentos") or []
    s2id = metrics.get("historico_s2id") or {}
    ev = s2id.get("evento_similar")
    sim_meta = metrics.get("simulation_meta") or {}
    is_calor = tipo_simulacao == "calor"

    if is_calor:
        max_delta = sim_meta.get("max_delta_t_c", 0)
        pico = sim_meta.get("temperatura_pico_c", parametro_atual)
        pico_local = sim_meta.get("temp_pico_local_c")
        ganho_veg = sim_meta.get("ganho_vegetal_pct", 0) or 0
        resfria_max = sim_meta.get("resfriamento_max_c", 0) or 0
        resumo = (
            f"Com pico previsto de {pico}°C em {muni.nome}/{muni.uf}, os bairros mais "
            f"impermeabilizados podem chegar a {pico_local or round(pico + max_delta, 1)}°C "
            f"(ilha de calor de até +{max_delta}°C), "
            f"afetando ~{metrics.get('populacao_estimada_atingida'):,} habitantes em "
            f"{metrics.get('n_bairros_afetados')} bairro(s)."
        ).replace(",", ".")
        if ganho_veg and resfria_max:
            resumo += (
                f" A arborização de {ganho_veg}% da área pode reduzir a ilha de calor em até "
                f"{resfria_max}°C nos bairros priorizados."
            )
    else:
        resumo = (
            f"Cenário de {TIPO_LABELS.get(tipo_simulacao, tipo_simulacao)} com parâmetro {parametro_atual} "
            f"em {muni.nome}/{muni.uf} pode afetar cerca de {metrics.get('area_afetada_km2')} km² "
            f"e ~{metrics.get('populacao_estimada_atingida'):,} habitantes em {metrics.get('n_bairros_afetados')} bairro(s)."
        ).replace(",", ".")

    areas_criticas = []
    for row in top3:
        if is_calor and row.get("delta_t_c") is not None:
            band = row.get("faixa_calor") or "—"
            temp_local = row.get("temp_local_c")
            local_txt = f" → {temp_local}°C" if temp_local is not None else ""
            areas_criticas.append(
                f"{row.get('nome')} (+{row.get('delta_t_c')}°C{local_txt}, faixa {band})"
            )
        else:
            pct = row.get("exposicao_pct")
            suffix = f" ({pct}% da área do bairro)" if pct is not None else ""
            areas_criticas.append(f"{row.get('nome')}{suffix}")

    equipamentos_txt = (
        [f"{e.get('tipo', 'equipamento')}: {e.get('nome')}" for e in equip[:5]]
        if equip
        else ["Nenhum equipamento público mapeado na mancha (camada infraestrutura)."]
    )

    comparacao = "Sem registro S2ID comparável no município."
    lst_cmp = metrics.get("lst_comparison") or {}
    if is_calor and lst_cmp.get("disponivel"):
        lst_med = lst_cmp.get("lst_mediana_c")
        sim_med = lst_cmp.get("sim_temp_mediana_c")
        div = lst_cmp.get("divergencia_mediana_c")
        div_txt = f"{div:+.1f}°C" if div is not None else "—"
        comparacao = (
            f"LST observada ({lst_cmp.get('lst_periodo', '2021–2025')}, {lst_cmp.get('lst_fonte', 'GeoReDUS')}): "
            f"mediana {lst_med}°C em {lst_cmp.get('amostras_validas', 0)} bairro(s). "
            f"Simulação Sinidu: mediana {sim_med}°C no pico · divergência {div_txt}. "
            f"{lst_cmp.get('narrativa', '')}"
        )
    elif is_calor:
        comparacao = (
            f"Normal climatológica local: {sim_meta.get('baseline_normal_c', sim_meta.get('baseline_temp_c', '—'))}°C "
            f"({sim_meta.get('baseline_temp_fonte', 'fonte municipal')}). "
            f"Pico previsto: {sim_meta.get('temperatura_pico_c', '—')}°C · "
            f"amplificação da onda de calor: {sim_meta.get('heatwave_amplification', '—')}×. "
            f"Faixas térmicas: {sim_meta.get('faixas_contagem', {})}."
        )
    elif ev:
        comparacao = (
            f"Evento similar: {ev.get('tipo')} em {ev.get('ano')} "
            f"(danos materiais R$ {ev.get('danos_materiais', 0):,.0f})."
        ).replace(",", ".")

    if is_calor:
        ganho_veg = sim_meta.get("ganho_vegetal_pct", 0) or 0
        resfria_medio = sim_meta.get("resfriamento_medio_c", 0) or 0
        if ganho_veg and resfria_medio:
            rec_arboriza = (
                f"Executar a arborização simulada ({ganho_veg}% de nova cobertura) — resfriamento médio "
                f"estimado de {resfria_medio}°C — priorizando bairros de maior ΔT e IVC."
            )
        else:
            rec_arboriza = "Priorizar arborização e corredores verdes nos bairros de maior ΔT e menor cobertura vegetal."
        recomendacoes = [
            rec_arboriza,
            "Instalar pontos de hidratação e abrigos climáticos próximos a UBS, escolas e terminais.",
            "Monitorar população vulnerável (IVC alto) em ondas de calor — SMS e Defesa Civil.",
        ]
    else:
        recomendacoes = [
            "Acionar monitoramento CEMADEN e Defesa Civil nos bairros de maior exposição.",
            "Inspecionar pontos crônicos de alagamento e galerias pluviais nas áreas críticas.",
            "Restringir circulação em faixas de profundidade crítica até validação de campo.",
        ]

    interpretacao_diferencial = None
    delta = metrics.get("delta_vs_referencia")
    if is_calor and lst_cmp.get("disponivel"):
        div = lst_cmp.get("divergencia_mediana_c")
        div_txt = f"{div:+.1f}°C" if div is not None else "—"
        interpretacao_diferencial = (
            f"Observado × simulado: LST mediana {lst_cmp.get('lst_mediana_c')}°C vs "
            f"simulação {lst_cmp.get('sim_temp_mediana_c')}°C "
            f"(Δ mediano {div_txt} em {lst_cmp.get('amostras_validas')} bairros). "
            "Use a comparação para calibrar narrativa de oficina — não como validação científica."
        )
    elif delta and parametro_referencia is not None:
        pct = delta.get("delta_area_pct")
        novos = delta.get("bairros_novos") or []
        interpretacao_diferencial = (
            f"Em comparação com {parametro_referencia} mm (referência), o cenário de {parametro_atual} mm representa "
            f"+{pct or 0}% de área afetada ({delta.get('delta_area_km2')} km² a mais) e "
            f"+{delta.get('delta_populacao')} habitantes adicionais em risco."
        )
        if novos:
            interpretacao_diferencial += f" Bairros exclusivos do cenário intenso: {', '.join(novos[:6])}."
        if ev:
            interpretacao_diferencial += f" Aproxima-se do evento S2ID de {ev.get('ano')} ({ev.get('tipo')})."

    findings = [resumo, *areas_criticas, *equipamentos_txt[:3], comparacao, *recomendacoes]

    return {
        "resumo_executivo": resumo,
        "areas_criticas": areas_criticas,
        "equipamentos_em_risco": equipamentos_txt,
        "comparacao_historica": comparacao,
        "recomendacoes_imediatas": recomendacoes,
        "interpretacao_diferencial": interpretacao_diferencial,
        "disclaimer": DISCLAIMER_CALOR if is_calor else DISCLAIMER,
        "findings": findings,
        "metricas": metrics,
        "ai_provider": "deterministic",
        "ai_model": None,
        "confidence": "media",
    }


def _parse_llm_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


def _llm_interpretation(
    db: Session,
    muni: Municipio,
    metrics: dict[str, Any],
    *,
    tipo_simulacao: str,
    parametro_atual: float,
    parametro_referencia: float | None,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    ai_api_key: str | None = None,
) -> dict[str, Any] | None:
    snap = executive_snapshot(db, muni)
    municipio_dados = {
        "nome": muni.nome,
        "uf": muni.uf,
        "populacao": snap.get("populacao"),
        "score_sinidu": snap.get("score_sinidu"),
        "historico_desastres": snap.get("historico_desastres_count"),
    }
    s2id = metrics.get("historico_s2id") or {}
    ev = s2id.get("evento_similar") or {}
    delta = metrics.get("delta_vs_referencia") or {}
    sim_meta = metrics.get("simulation_meta") or {}
    is_calor = tipo_simulacao == "calor"

    expert_role = (
        "especialista em ilhas de calor urbanas, saúde pública e adaptação climática"
        if is_calor
        else "especialista em gestão de risco urbano e hidrologia urbana"
    )

    heat_block = ""
    if is_calor:
        heat_block = f"""
DADOS TÉRMICOS:
- Temperatura de pico prevista para a cidade: {sim_meta.get('temperatura_pico_c')}°C
- Normal climatológica local (INMET/série): {sim_meta.get('baseline_normal_c', sim_meta.get('baseline_temp_c'))}°C ({sim_meta.get('baseline_temp_fonte')})
- Amplificação da onda de calor sobre a ilha de calor: {sim_meta.get('heatwave_amplification')}×
- Ilha de calor máxima (ΔT) estimada: +{sim_meta.get('max_delta_t_c')}°C
- Temperatura local máxima nos bairros críticos: {sim_meta.get('temp_pico_local_c')}°C
- Perda vegetal simulada: {sim_meta.get('perda_vegetal_pct')}%
- Ganho de vegetação/arborização simulado: {sim_meta.get('ganho_vegetal_pct')}%
- Resfriamento por arborização (máx / médio): {sim_meta.get('resfriamento_max_c')}°C / {sim_meta.get('resfriamento_medio_c')}°C
- Impermeabilização extra: {sim_meta.get('impermeabilizacao_extra_pct')}%
- Contagem por faixa (leve/moderada/severa): {json.dumps(sim_meta.get('faixas_contagem', {}), ensure_ascii=False)}
"""
        lst_cmp = metrics.get("lst_comparison") or {}
        if lst_cmp.get("disponivel"):
            heat_block += f"""
COMPARAÇÃO LST OBSERVADA × SIMULADO (GeoReDUS):
- LST mediana observada: {lst_cmp.get('lst_mediana_c')}°C ({lst_cmp.get('lst_periodo')})
- Simulação mediana: {lst_cmp.get('sim_temp_mediana_c')}°C
- Divergência mediana: {lst_cmp.get('divergencia_mediana_c')}°C
- Amostras válidas: {lst_cmp.get('amostras_validas')} / {lst_cmp.get('amostras_total')}
- Narrativa: {lst_cmp.get('narrativa', '')}
- Limites: {json.dumps(lst_cmp.get('limites_metodologicos', [])[:3], ensure_ascii=False)}
Explique explicitamente que LST mede superfície histórica e a simulação projeta cenário futuro — a divergência não invalida o modelo.
"""

    system = f"""Você é um {expert_role}.
Analise o resultado desta simulação e produza interpretação técnica mas acessível para gestores municipais e Defesa Civil.

DADOS DO MUNICÍPIO: {json.dumps(municipio_dados, ensure_ascii=False)}

RESULTADO DA SIMULAÇÃO ({TIPO_LABELS.get(tipo_simulacao, tipo_simulacao)}):
- Parâmetro simulado: {parametro_atual}
- Área potencialmente afetada: {metrics.get('area_afetada_km2')} km²
- População estimada na zona de risco: {metrics.get('populacao_estimada_atingida')} habitantes
- Bairros atingidos: {json.dumps(metrics.get('bairros_afetados', [])[:8], ensure_ascii=False)}
- Equipamentos públicos na mancha: {json.dumps(metrics.get('equipamentos', [])[:8], ensure_ascii=False)}
- Comparação com referência {parametro_referencia} mm: {json.dumps(delta, ensure_ascii=False) if delta else 'não aplicável'}
{heat_block}
HISTÓRICO S2ID: {json.dumps(ev, ensure_ascii=False)}

Responda APENAS JSON válido com:
resumo_executivo (string 2 frases),
areas_criticas (array de strings, top 3),
equipamentos_em_risco (array strings),
comparacao_historica (string),
recomendacoes_imediatas (array 3 strings),
interpretacao_diferencial (string ou null se sem comparação)."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "Gere a interpretação da simulação."},
    ]

    try:
        from rag.providers.registry import resolve_chat_provider_with_fallback

        provider = resolve_chat_provider_with_fallback(ai_provider, api_key=ai_api_key)
        if not provider.is_available():
            return None
        model = ai_model or provider.info().default_model
        raw = provider.chat(messages, model=model, temperature=0.15)
        parsed = _parse_llm_json(raw)
        if not parsed:
            return None
        parsed.setdefault("disclaimer", DISCLAIMER_CALOR if is_calor else DISCLAIMER)
        parsed["metricas"] = metrics
        parsed["ai_provider"] = provider.id
        parsed["ai_model"] = model
        parsed["confidence"] = "alta"
        findings = [parsed.get("resumo_executivo", "")]
        findings.extend(parsed.get("areas_criticas") or [])
        findings.extend(parsed.get("equipamentos_em_risco") or [])
        if parsed.get("comparacao_historica"):
            findings.append(parsed["comparacao_historica"])
        findings.extend(parsed.get("recomendacoes_imediatas") or [])
        parsed["findings"] = [f for f in findings if f]
        return parsed
    except Exception as exc:
        logger.warning("LLM simulation interpret failed: %s", exc)
        return None


def interpret_simulation(
    db: Session,
    muni: Municipio,
    *,
    tipo_simulacao: Literal["chuva", "asfalto", "vegetacao", "drenagem", "calor"],
    parametro_atual: float,
    parametro_referencia: float = 80.0,
    resultado_simulacao: dict[str, Any],
    resultado_referencia: dict[str, Any] | None = None,
    comparacao_delta: dict[str, Any] | None = None,
    lst_comparison: dict[str, Any] | None = None,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    ai_api_key: str | None = None,
    use_ai: bool = True,
) -> dict[str, Any]:
    metrics = extract_simulation_metrics(
        db,
        muni,
        resultado_simulacao,
        parametro_atual=parametro_atual,
        parametro_referencia=parametro_referencia if resultado_referencia else None,
        resultado_referencia=resultado_referencia,
    )
    if comparacao_delta and not metrics.get("delta_vs_referencia"):
        metrics["delta_vs_referencia"] = {
            "parametro_referencia": comparacao_delta.get("baseline_mm", parametro_referencia),
            "parametro_atual": comparacao_delta.get("scenario_mm", parametro_atual),
            "delta_area_km2": comparacao_delta.get("affected_area_km2"),
            "delta_populacao": comparacao_delta.get("affected_population"),
            "bairros_novos": comparacao_delta.get("bairros_novos") or [],
        }
        ref_area = float(resultado_referencia.get("affected_area_km2") or 0) if resultado_referencia else 0
        d_area = comparacao_delta.get("affected_area_km2")
        if ref_area and d_area is not None:
            metrics["delta_vs_referencia"]["delta_area_pct"] = round(float(d_area) / ref_area * 100, 1)

    if lst_comparison:
        metrics["lst_comparison"] = lst_comparison

    if use_ai:
        llm = _llm_interpretation(
            db,
            muni,
            metrics,
            tipo_simulacao=tipo_simulacao,
            parametro_atual=parametro_atual,
            parametro_referencia=parametro_referencia if resultado_referencia or comparacao_delta else None,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_api_key=ai_api_key,
        )
        if llm:
            for key, default in (
                ("resumo_executivo", ""),
                ("areas_criticas", []),
                ("equipamentos_em_risco", []),
                ("comparacao_historica", ""),
                ("recomendacoes_imediatas", []),
            ):
                llm.setdefault(key, default)
            return llm

    return _deterministic_interpretation(
        muni,
        metrics,
        tipo_simulacao=tipo_simulacao,
        parametro_atual=parametro_atual,
        parametro_referencia=parametro_referencia if resultado_referencia or comparacao_delta else None,
    )


def _nivel_suscetibilidade(pct: float) -> str:
    if pct >= 35:
        return "MUITO_ALTA"
    if pct >= 20:
        return "ALTA"
    if pct >= 10:
        return "MEDIA"
    return "BAIXA"


def interpret_slope_zones(
    db: Session,
    muni: Municipio,
    *,
    precip_mm: float = 80.0,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    ai_api_key: str | None = None,
    use_ai: bool = True,
) -> dict[str, Any]:
    analysis = slope_analysis(db, muni.codigo_ibge)
    pct = float(analysis.get("suscetibilidade_alta_pct") or analysis.get("pct_declividade_critica") or 0)
    area_ha = float(analysis.get("area_critica_ha") or 0)
    area_km2 = round(area_ha / 100.0, 2)
    pop = int(analysis.get("populacao_exposta") or 0)
    bairros = [b.get("nome") for b in (analysis.get("bairros_criticos") or []) if b.get("nome")]
    nivel = _nivel_suscetibilidade(pct)

    base_text = (
        f"Encostas com declividade crítica (DEM SRTM) cobrem ~{area_km2} km² ({pct:.1f}% do município), "
        f"com ~{pop:,} habitantes expostos em {len(bairros)} bairro(s) de encosta."
    ).replace(",", ".")

    interpretacao_ia = base_text
    if use_ai:
        try:
            from rag.providers.registry import resolve_chat_provider_with_fallback

            provider = resolve_chat_provider_with_fallback(ai_provider, api_key=ai_api_key)
            if provider.is_available():
                model = ai_model or provider.info().default_model
                prompt = (
                    f"Interprete suscetibilidade a deslizamentos em {muni.nome}/{muni.uf}: "
                    f"área {area_km2} km², pop {pop}, bairros {bairros[:5]}, nível {nivel}. "
                    "Responda em 2 parágrafos para gestores. Referência COBRADE 1.1.4.1.0."
                )
                interpretacao_ia = provider.chat(
                    [{"role": "user", "content": prompt}],
                    model=model,
                    temperature=0.2,
                )
        except Exception as exc:
            logger.warning("Slope LLM interpret failed: %s", exc)

    return {
        "codigo_ibge": muni.codigo_ibge,
        "area_suscetivel_km2": area_km2,
        "populacao_exposta": pop,
        "bairros_encosta": bairros,
        "nivel_suscetibilidade": nivel,
        "interpretacao_ia": interpretacao_ia,
        "referencia_cobrade": "1.1.4.1.0 — Deslizamento",
        "dem_source": analysis.get("dem_source"),
        "precipitacao_mm": precip_mm,
    }
