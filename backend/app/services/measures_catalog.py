"""Catálogo de medidas filtrado por porte, CAPAG e risco (17h.3a).

Biblioteca estática de respostas (baixo/médio/alto custo) condicionada ao perfil municipal.
"""

from __future__ import annotations

from typing import Any

from app.services.federal_financing_catalog import attach_financing_to_measures

COST_LOW = "Baixo"
COST_MED = "Médio"
COST_HIGH = "Alto"

HORIZON_SHORT = "Curto prazo"
HORIZON_MED = "Médio prazo"
HORIZON_LONG = "Longo prazo"

# portes_ok: se vazio, vale para todos
# custos_bloqueados_capag: notas CAPAG que excluem esta medida
# fatores: gatilhos do ranking (renda, densidade, s2id, impermeabilizacao, hidrografia, adaptacao, exposicao)
# niveis_risco: VERDE/AMARELO/LARANJA/VERMELHO — se vazio, sempre candidata
MEASURES: list[dict[str, Any]] = [
    {
        "id": "mon_cemaden_dc",
        "titulo": "Monitoramento integrado CEMADEN + Defesa Civil",
        "descricao": "Articular alertas hidrológicos com protocolo municipal de resposta e comunicação às áreas expostas.",
        "tipo_risco": "alerta",
        "horizonte": HORIZON_SHORT,
        "custo": COST_LOW,
        "portes_ok": [],
        "custos_bloqueados_capag": [],
        "fatores": ["s2id", "exposicao"],
        "niveis_risco": ["AMARELO", "LARANJA", "VERMELHO"],
        "orgao": "Defesa Civil / Meio Ambiente",
        "fonte": "CEMADEN + Sinidu+Clima",
        "prioridade_base": "Alta",
    },
    {
        "id": "microdrenagem",
        "titulo": "Desobstrução e microdrenagem nos pontos críticos",
        "descricao": "Limpeza de bocas de lobo, galerias pluviais e pontos de alagamento recorrente nas áreas prioritárias.",
        "tipo_risco": "inundacao",
        "horizonte": HORIZON_SHORT,
        "custo": COST_MED,
        "portes_ok": [],
        "custos_bloqueados_capag": [],
        "fatores": ["impermeabilizacao", "hidrografia", "s2id", "iri"],
        "niveis_risco": ["AMARELO", "LARANJA", "VERMELHO"],
        "orgao": "Obras / Saneamento",
        "fonte": "AnalyticalEngine / MapBiomas",
        "prioridade_base": "Alta",
    },
    {
        "id": "plano_contingencia",
        "titulo": "Atualizar plano de contingência com histórico S2ID",
        "descricao": "Incorporar eventos registrados na matriz de risco, rotas de evacuação e pontos de apoio.",
        "tipo_risco": "contingencia",
        "horizonte": HORIZON_SHORT,
        "custo": COST_LOW,
        "portes_ok": [],
        "custos_bloqueados_capag": [],
        "fatores": ["s2id", "exposicao"],
        "niveis_risco": ["AMARELO", "LARANJA", "VERMELHO"],
        "orgao": "Defesa Civil",
        "fonte": "S2ID / CENAD",
        "prioridade_base": "Alta",
    },
    {
        "id": "capacitacao_dc",
        "titulo": "Capacitação operacional da Defesa Civil municipal",
        "descricao": "Treinar equipes, padronizar COBRADE e ensaiar protocolo de alerta e abrigo.",
        "tipo_risco": "capacidade",
        "horizonte": HORIZON_SHORT,
        "custo": COST_LOW,
        "portes_ok": ["pequeno", "medio"],
        "custos_bloqueados_capag": [],
        "fatores": [],
        "niveis_risco": ["AMARELO", "LARANJA", "VERMELHO", "VERDE"],
        "orgao": "Defesa Civil / SEDEC",
        "fonte": "MIDR / SEDEC",
        "prioridade_base": "Média",
    },
    {
        "id": "revegetacao",
        "titulo": "Arborização e revegetação urbana",
        "descricao": "Implantar corredores verdes e arborização de via pública para reduzir escoamento e ilhas de calor.",
        "tipo_risco": "calor_escoamento",
        "horizonte": HORIZON_MED,
        "custo": COST_MED,
        "portes_ok": [],
        "custos_bloqueados_capag": [],
        "fatores": ["adaptacao", "impermeabilizacao"],
        "niveis_risco": ["AMARELO", "LARANJA", "VERMELHO"],
        "orgao": "Meio Ambiente / Urbanismo",
        "fonte": "MapBiomas / Sinidu+Clima",
        "prioridade_base": "Média",
    },
    {
        "id": "nbs_retencao",
        "titulo": "Soluções baseadas na natureza e retenção pluvial",
        "descricao": "Jardins de chuva, valas de infiltração e reservatórios de detenção nas bacias prioritárias.",
        "tipo_risco": "inundacao",
        "horizonte": HORIZON_LONG,
        "custo": COST_HIGH,
        "portes_ok": ["medio", "grande", "metropole"],
        "custos_bloqueados_capag": ["C", "D", "E"],
        "fatores": ["impermeabilizacao", "hidrografia", "iri"],
        "niveis_risco": ["LARANJA", "VERMELHO"],
        "orgao": "Obras / Planejamento Urbano",
        "fonte": "Sinidu+Clima / boas práticas MCID",
        "prioridade_base": "Alta",
    },
    {
        "id": "carteira_drenagem",
        "titulo": "Carteira priorizada de obras de drenagem",
        "descricao": "Estudos, projetos executivos e cronograma plurianual alinhados ao Plano Diretor.",
        "tipo_risco": "estrutural",
        "horizonte": HORIZON_LONG,
        "custo": COST_HIGH,
        "portes_ok": ["grande", "metropole"],
        "custos_bloqueados_capag": ["C", "D", "E"],
        "fatores": ["impermeabilizacao", "iri", "s2id"],
        "niveis_risco": ["LARANJA", "VERMELHO"],
        "orgao": "Obras / Planejamento",
        "fonte": "Plano Diretor / Sinidu+Clima",
        "prioridade_base": "Média",
    },
    {
        "id": "priorizar_nao_reembolsavel",
        "titulo": "Priorizar baixo custo e fontes não reembolsáveis",
        "descricao": "CAPAG restritiva — focar capacitação, prevenção e apoio técnico federal antes de crédito.",
        "tipo_risco": "fiscal",
        "horizonte": HORIZON_SHORT,
        "custo": COST_LOW,
        "portes_ok": [],
        "custos_bloqueados_capag": [],
        "fatores": [],
        "niveis_risco": [],
        "orgao": "Finanças / Controle Interno",
        "fonte": "CAPAG / Tesouro Nacional",
        "prioridade_base": "Alta",
        "exige_capag": ["C", "D", "E"],
    },
    {
        "id": "apoio_sedec",
        "titulo": "Solicitar apoio técnico SEDEC / CENAD",
        "descricao": "Articular com a Secretaria Nacional de Proteção e Defesa Civil para orientação e recursos de preparação.",
        "tipo_risco": "capacidade",
        "horizonte": HORIZON_SHORT,
        "custo": COST_LOW,
        "portes_ok": ["pequeno", "medio"],
        "custos_bloqueados_capag": [],
        "fatores": [],
        "niveis_risco": ["LARANJA", "VERMELHO"],
        "orgao": "Defesa Civil / SEDEC",
        "fonte": "MIDR / SEDEC",
        "prioridade_base": "Alta",
    },
    {
        "id": "mapeamento_expostos",
        "titulo": "Mapear população e equipamentos expostos",
        "descricao": "Consolidar escolas, UBS e territórios especiais nas áreas de score elevado para priorizar proteção.",
        "tipo_risco": "exposicao",
        "horizonte": HORIZON_SHORT,
        "custo": COST_LOW,
        "portes_ok": [],
        "custos_bloqueados_capag": [],
        "fatores": ["exposicao", "densidade", "renda"],
        "niveis_risco": ["AMARELO", "LARANJA", "VERMELHO"],
        "orgao": "Planejamento / Defesa Civil",
        "fonte": "INEP / CNES / Sinidu+Clima",
        "prioridade_base": "Alta",
    },
]

_COST_RANK = {COST_LOW: 0, COST_MED: 1, COST_HIGH: 2}
_PRIO_RANK = {"Alta": 0, "Média": 1, "Baixa": 2}


def _measure_allowed(measure: dict[str, Any], porte: str, nota_capag: str | None) -> bool:
    portes = measure.get("portes_ok") or []
    if portes and porte not in portes:
        return False
    capag = (nota_capag or "").upper()[:1] or None
    exige = measure.get("exige_capag") or []
    if exige and capag not in exige:
        return False
    bloqueados = measure.get("custos_bloqueados_capag") or []
    if capag and capag in bloqueados:
        return False
    return True


def _relevance_score(
    measure: dict[str, Any],
    *,
    nivel_risco: str,
    fatores: set[str],
) -> int:
    score = 0
    niveis = measure.get("niveis_risco") or []
    if not niveis or nivel_risco in niveis:
        score += 2
    else:
        return -1
    m_fatores = set(measure.get("fatores") or [])
    if m_fatores:
        overlap = len(m_fatores & fatores)
        if overlap:
            score += 3 + overlap
        elif not fatores:
            score += 1
        else:
            score += 0
    else:
        score += 1
    if measure.get("custo") == COST_LOW:
        score += 1
    return score


def recommend_measures(
    perfil: dict[str, Any],
    *,
    nivel_risco: str = "AMARELO",
    fatores_principais: list[str] | None = None,
    bairros_alvo: list[str] | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Filtra e ranqueia medidas do catálogo para o perfil + risco atual."""
    porte = perfil.get("porte") or "pequeno"
    nota = (perfil.get("capag") or {}).get("nota")
    fatores = {str(f).lower() for f in (fatores_principais or []) if f}
    nivel = (nivel_risco or "AMARELO").upper()
    alvos = list(bairros_alvo or [])[:5]

    ranked: list[tuple[int, dict[str, Any]]] = []
    for raw in MEASURES:
        if not _measure_allowed(raw, porte, nota):
            continue
        rel = _relevance_score(raw, nivel_risco=nivel, fatores=fatores)
        if rel < 0:
            continue
        item = {
            "id": raw["id"],
            "titulo": raw["titulo"],
            "descricao": raw["descricao"],
            "tipo_risco": raw["tipo_risco"],
            "horizonte": raw["horizonte"],
            "custo": raw["custo"],
            "prioridade": raw.get("prioridade_base") or "Média",
            "orgao": raw["orgao"],
            "fonte": raw["fonte"],
            "bairros_alvo": alvos,
            "motivo": _motivo(raw, porte=porte, nota=nota, nivel=nivel, fatores=fatores),
        }
        ranked.append((rel, item))

    ranked.sort(
        key=lambda pair: (
            -pair[0],
            _PRIO_RANK.get(pair[1]["prioridade"], 9),
            _COST_RANK.get(pair[1]["custo"], 9),
        )
    )
    top = [item for _, item in ranked[: max(1, limit)]]
    # 17h.3b — cada medida leva fontes de recurso filtradas pela CAPAG
    return attach_financing_to_measures(top, nota_capag=nota)


def _motivo(
    measure: dict[str, Any],
    *,
    porte: str,
    nota: str | None,
    nivel: str,
    fatores: set[str],
) -> str:
    parts: list[str] = []
    parts.append(f"Risco {nivel}")
    parts.append(f"porte {porte}")
    if nota:
        parts.append(f"CAPAG {nota}")
    overlap = set(measure.get("fatores") or []) & fatores
    if overlap:
        parts.append("fatores: " + ", ".join(sorted(overlap)))
    if measure.get("custo") == COST_HIGH and nota in {"A", "B"}:
        parts.append("custo alto compatível com CAPAG")
    return " · ".join(parts)
