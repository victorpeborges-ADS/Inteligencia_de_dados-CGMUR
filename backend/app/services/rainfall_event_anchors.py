"""Âncoras históricas de chuva extrema + impactos operacionais da simulação.

Subsidia o slider de precipitação com eventos documentados (S2ID, CEMADEN,
APAC, imprensa) e estima tempo de escoamento / mobilidade a partir da mancha.
"""

from __future__ import annotations

from typing import Any

# Eventos de referência — Recife (IBGE 2611606).
# mm e impactos são consolidados de APAC/CEMADEN/imprensa; qualidade Estimado/Referência.
RECIFE_RAIN_ANCHORS: list[dict[str, Any]] = [
    {
        "id": "recife_2010_capibaribe",
        "label": "Cheia Capibaribe 2010",
        "data": "2010-06-17",
        "precipitacao_mm": 120.0,
        "duracao_h": 48.0,
        "antecedente_mm": 180.0,
        "tipo_dominante": "inundacao_fluvial",
        "bairros": ["Santo Amaro", "Afogados", "Torre", "Ilha Joana Bezerra", "Coque"],
        "populacao_afetada_obs": 20000,
        "mortos_obs": 0,
        "fonte": "S2ID / Defesa Civil / G1",
        "url": "https://g1.globo.com/pernambuco/noticia/2010/06/cheia-do-capibaribe-deixa-milhares-desalojados-no-recife.html",
        "nota": "Transbordamento do Capibaribe — várzeas urbanas submersas.",
    },
    {
        "id": "recife_2022_maio",
        "label": "Tragédia maio/2022",
        "data": "2022-05-28",
        "precipitacao_mm": 190.0,
        "duracao_h": 24.0,
        "antecedente_mm": 280.0,
        "tipo_dominante": "deslizamento_e_alagamento",
        "bairros": ["Ibura", "Cohab", "Barro", "Guabiraba", "Tejipió", "Casa Amarela"],
        "populacao_afetada_obs": 12000,
        "mortos_obs": 51,
        "fonte": "CEMADEN / APAC / Marengo et al. 2023",
        "url": "https://www.gov.br/cemaden/pt-br/assuntos/noticias-cemaden/pesquisadores-brasileiros-fazem-recomendacoes-analisando-as-repentinas-inundacoes-e-deslizamentos-de-terra-em-recife-pe-apos-fortes-chuvas-ocorridas-em-maio-de-2022",
        "nota": (
            "Pico ~190 mm/24h em estações da capital; acumulado RMR 25–30/mai ~450–550 mm. "
            "Padrão dominante: deslizamentos em morros/tabuleiros (não só cheia fluvial)."
        ),
    },
    {
        "id": "recife_2022_passarinho",
        "label": "Passarinho / Zona Norte 2022",
        "data": "2022-05-27",
        "precipitacao_mm": 160.0,
        "duracao_h": 24.0,
        "antecedente_mm": 250.0,
        "tipo_dominante": "deslizamento",
        "bairros": ["Passarinho", "Dois Irmãos", "Sítio dos Pintos", "Cajueiro"],
        "populacao_afetada_obs": 5000,
        "mortos_obs": 10,
        "fonte": "Defesa Civil / DW / G1",
        "url": "https://www.dw.com/pt-br/chuvas-no-recife-foi-como-um-tsunami-que-arrastou-tudo-pela-frente/a-61986769",
        "nota": "Encostas da Zona Norte — barreira e vias intransitáveis.",
    },
    {
        "id": "recife_2023_agamenon",
        "label": "Alagamento Agamenon 2023",
        "data": "2023-06-15",
        "precipitacao_mm": 85.0,
        "duracao_h": 6.0,
        "antecedente_mm": 60.0,
        "tipo_dominante": "alagamento_urbano",
        "bairros": ["Espinheiro", "Graças", "Derby"],
        "populacao_afetada_obs": 8000,
        "mortos_obs": 0,
        "fonte": "G1 / Defesa Civil Recife",
        "url": "https://g1.globo.com/pe/pernambuco/noticia/2023/06/15/chuva-causa-alagamentos-em-varios-pontos-do-recife.ghtml",
        "nota": "Chuva concentrada — vias arteriais intransitáveis (direito de ir e vir).",
    },
    {
        "id": "recife_2024_maio",
        "label": "Alagamentos maio/2024",
        "data": "2024-05-10",
        "precipitacao_mm": 95.0,
        "duracao_h": 12.0,
        "antecedente_mm": 80.0,
        "tipo_dominante": "alagamento_urbano",
        "bairros": ["Boa Viagem", "Imbiribeira", "Afogados"],
        "populacao_afetada_obs": 6000,
        "mortos_obs": 0,
        "fonte": "G1 / Defesa Civil",
        "url": "https://g1.globo.com/pe/pernambuco/noticia/2024/05/10/chuva-forte-causa-alagamentos-no-recife.ghtml",
        "nota": "Evento urbano recente — útil para calibrar TR ~10–25 anos em 12 h.",
    },
]

_ANCHORS_BY_IBGE: dict[str, list[dict[str, Any]]] = {
    "2611606": RECIFE_RAIN_ANCHORS,
}

# Faixas operacionais do slider (mm no horizonte do evento simulado).
SLIDER_BOUNDS: dict[str, dict[str, float]] = {
    "2611606": {"min_mm": 20.0, "max_mm": 350.0, "step_mm": 5.0, "default_mm": 105.0},
    "_default": {"min_mm": 20.0, "max_mm": 280.0, "step_mm": 5.0, "default_mm": 100.0},
}


def rainfall_anchors_for(codigo_ibge: str) -> dict[str, Any]:
    code = str(codigo_ibge or "").zfill(7)[:7]
    anchors = list(_ANCHORS_BY_IBGE.get(code) or [])
    bounds = SLIDER_BOUNDS.get(code) or SLIDER_BOUNDS["_default"]
    return {
        "codigo_ibge": code,
        "anchors": anchors,
        "slider": bounds,
        "qualidade": "Referencia" if anchors else "Estimado",
        "nota": (
            "Âncoras históricas documentadas (APAC/CEMADEN/S2ID/imprensa) para calibrar "
            "o volume do cenário. A simulação Sinidu permanece triagem (Derivado), não laudo."
            if anchors
            else "Sem âncoras históricas curadas para este município — use curvas IDF."
        ),
    }


def match_anchor(
    codigo_ibge: str,
    precip_mm: float,
    *,
    duracao_h: float | None = None,
    tol_mm: float = 25.0,
    tol_h: float = 24.0,
) -> dict[str, Any] | None:
    """Retorna a âncora histórica mais próxima do cenário simulado (mm e, se informado, duração)."""
    catalog = rainfall_anchors_for(codigo_ibge).get("anchors") or []
    if not catalog:
        return None

    def _dist(a: dict[str, Any]) -> float:
        d_mm = abs(float(a.get("precipitacao_mm") or 0) - float(precip_mm)) / max(tol_mm, 1.0)
        if duracao_h is None:
            return d_mm
        d_h = abs(float(a.get("duracao_h") or 0) - float(duracao_h)) / max(tol_h, 1.0)
        return (d_mm ** 2 + d_h ** 2) ** 0.5

    best = min(catalog, key=_dist)
    delta = abs(float(best.get("precipitacao_mm") or 0) - float(precip_mm))
    delta_h = abs(float(best.get("duracao_h") or 0) - float(duracao_h)) if duracao_h is not None else None
    dist = _dist(best)
    dist_limit = 1.0 if duracao_h is None else 1.4
    if dist > dist_limit:
        return None
    return {
        **best,
        "delta_mm": round(delta, 1),
        "delta_duracao_h": round(delta_h, 1) if delta_h is not None else None,
        "similaridade": round(max(0.0, 1.0 - min(dist, 1.0)), 2),
    }


def estimate_operational_impacts(
    *,
    precip_mm: float,
    max_depth_m: float,
    affected_area_km2: float,
    affected_population: int,
    landslide_zones: int = 0,
    drainage_cap_mm_h: float = 18.0,
    drain_removed_mm: float = 0.0,
    drenagem_aplicada: bool = True,
    hydrograph_duration_h: float = 6.0,
    duracao_h: float = 1.0,
) -> dict[str, Any]:
    """Estima escoamento e impacto à mobilidade a partir da mancha (proxy operacional)."""
    precip = max(0.0, float(precip_mm or 0.0))
    depth_m = max(0.0, float(max_depth_m or 0.0))
    area = max(0.0, float(affected_area_km2 or 0.0))
    pop = max(0, int(affected_population or 0))
    cap = max(4.0, float(drainage_cap_mm_h or 18.0))
    removed = max(0.0, float(drain_removed_mm or 0.0))
    dur_h = max(0.25, float(duracao_h or 1.0))
    intensidade_mm_h = round(precip / dur_h, 1)

    if dur_h <= 3.0:
        regime = "CONCENTRADO"
        regime_label = "Chuva concentrada (flash)"
    elif dur_h <= 24.0:
        regime = "INTENSO_24H"
        regime_label = "Chuva intensa em até 24h"
    elif dur_h <= 72.0:
        regime = "PROLONGADO"
        regime_label = "Evento prolongado (2–3 dias)"
    else:
        regime = "SUSTENTADO"
        regime_label = "Chuva sustentada (vários dias)"

    # Excesso residual após rede (ou chuva bruta se rede desligada).
    excess_mm = max(0.0, precip - removed) if drenagem_aplicada else precip
    # Escoamento natural (infiltração + microdrenagem superficial sem intervenção).
    natural_mm_h = 3.5 + min(depth_m, 1.0) * 1.5  # ~3.5–5 mm/h
    # Com intervenções sugeridas: rede + limpeza/bombas/SUDS → +40% sobre capacidade atual.
    intervened_mm_h = max(cap * 0.85, natural_mm_h) * 1.4

    t_sem = excess_mm / natural_mm_h if natural_mm_h > 0 else hydrograph_duration_h
    t_com = excess_mm / intervened_mm_h if intervened_mm_h > 0 else hydrograph_duration_h * 0.5
    # Piso/teto: alinhados ao hidrograma (já escalado pela duração do evento, 17g.3) +
    # recessão longa em extremos — eventos de vários dias podem levar bem mais que 72h.
    teto_sem = max(72.0, hydrograph_duration_h * 1.6)
    teto_com = max(36.0, hydrograph_duration_h * 0.9)
    t_sem_h = round(min(teto_sem, max(hydrograph_duration_h * 0.5, t_sem)), 1)
    t_com_h = round(min(teto_com, max(1.5, t_com)), 1)
    reducao_pct = round(max(0.0, (1.0 - (t_com_h / t_sem_h)) * 100.0), 0) if t_sem_h > 0 else 0.0

    # Mobilidade / direito de ir e vir — fração da pop. afetada com lâmina impeditiva.
    if depth_m >= 0.80:
        frac_impedida = 0.75
        nivel_mobilidade = "CRITICO"
        nota_mob = "Lâmina crítica (≥0,80 m): vias arteriais e locais intransitáveis para pedestres e veículos leves."
    elif depth_m >= 0.35:
        frac_impedida = 0.45
        nivel_mobilidade = "SEVERO"
        nota_mob = "Lâmina moderada (0,35–0,80 m): restrição forte ao ir e vir; risco a pedestres e motos."
    elif depth_m >= 0.05:
        frac_impedida = 0.20
        nivel_mobilidade = "MODERADO"
        nota_mob = "Lâmina superficial: calçadas e vias locais comprometidas; desvios necessários."
    else:
        frac_impedida = 0.0
        nivel_mobilidade = "BAIXO"
        nota_mob = "Sem lâmina significativa estimada — mobilidade pouco afetada neste cenário."

    pop_mobilidade = int(round(pop * frac_impedida))
    # Proxy de vias: ~1,2 km de via comprometida por km² alagado (denso urbano).
    vias_km = round(area * 1.2 * (0.4 + min(depth_m, 1.0) * 0.6), 1)

    risco_deslizamento = (
        "MUITO_ALTO"
        if landslide_zones >= 8 or (precip >= 150 and landslide_zones >= 3) or intensidade_mm_h >= 60
        else "ALTO"
        if landslide_zones >= 4 or precip >= 120 or intensidade_mm_h >= 35
        else "MEDIO"
        if landslide_zones >= 1 or precip >= 80 or intensidade_mm_h >= 20
        else "BAIXO"
    )

    return {
        "qualidade": "Estimado",
        "metodo": "proxy_lamina_drenagem_hidrograma",
        "regime_chuva": {
            "codigo": regime,
            "label": regime_label,
            "duracao_h": round(dur_h, 1),
            "intensidade_mm_h": intensidade_mm_h,
            "nota": (
                "Mesma lâmina (mm) concentrada em poucas horas gera intensidade (mm/h) muito maior "
                "que espalhada em dias — por isso a mancha, o gatilho de deslizamento e o hidrograma "
                "mudam com a duração informada, mesmo com o mm do evento fixo."
            ),
        },
        "escoamento": {
            "tempo_sem_intervencao_h": t_sem_h,
            "tempo_com_intervencoes_h": t_com_h,
            "reducao_pct": reducao_pct,
            "taxa_natural_mm_h": round(natural_mm_h, 1),
            "taxa_com_intervencoes_mm_h": round(intervened_mm_h, 1),
            "excesso_residual_mm": round(excess_mm, 1),
            "nota": (
                "Tempo até reduzir a lâmina residual sob escoamento natural vs. com "
                "intervenções sugeridas (rede + limpeza/bombas/SUDS, +40% capacidade), a partir do "
                f"pico do hidrograma ({regime_label.lower()}, {dur_h:.0f}h de chuva). "
                "Não substitui modelagem hidrodinâmica de rede."
            ),
        },
        "mobilidade": {
            "nivel": nivel_mobilidade,
            "populacao_com_ir_e_vir_impedido": pop_mobilidade,
            "fracao_afetada": round(frac_impedida, 2),
            "vias_comprometidas_km_proxy": vias_km,
            "nota": nota_mob,
        },
        "deslizamento": {
            "nivel": risco_deslizamento,
            "zonas_estimadas": int(landslide_zones or 0),
            "nota": (
                "Zonas por declividade × chuva efetiva (evento ponderado pela intensidade + "
                "antecedente). Maio/2022 em Recife mostrou que deslizamento pode dominar sobre "
                "cheia fluvial, sobretudo em chuva concentrada de alta intensidade."
            ),
        },
        "resumo_populacao": {
            "exposta_alagamento": pop,
            "area_alagada_km2": round(area, 3),
            "profundidade_max_m": round(depth_m, 2),
        },
    }
