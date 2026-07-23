"""Cruzamento guiado de camadas a partir de pergunta do gestor (17h.2c)."""

from __future__ import annotations

import re
from typing import Any

# Regras determinísticas: keywords → camadas do mapa
_RULES: list[dict[str, Any]] = [
    {
        "id": "pobre_alagamento",
        "keywords": [
            "pobre",
            "renda baixa",
            "baixa renda",
            "vulnerab",
            "alag",
            "inunda",
            "enchente",
            "gente pobre",
        ],
        "require_any": [["pobre", "renda", "vulnerab"], ["alag", "inunda", "enchente"]],
        "layers": ["bairros", "socioeconomico", "vulnerabilidade", "inundacao"],
        "rationale": "Cruza renda/vulnerabilidade com risco de inundação para achar quem está exposto ao alagamento.",
    },
    {
        "id": "escola_risco",
        "keywords": ["escola", "educa", "aluno", "matrícul", "matricula", "inep"],
        "layers": ["bairros", "educacao", "inundacao", "vulnerabilidade"],
        "rationale": "Escolas (INEP) sobre risco de inundação e vulnerabilidade climática.",
    },
    {
        "id": "saude_risco",
        "keywords": ["saúde", "saude", "ubs", "hospital", "cnes", "posto"],
        "layers": ["bairros", "saude_risco", "inundacao", "alertas"],
        "rationale": "Unidades de saúde × risco climático e alertas ativos.",
    },
    {
        "id": "alerta_agora",
        "keywords": ["alerta", "cemaden", "agora", "tempo real", "emergência", "emergencia"],
        "layers": ["bairros", "alertas", "risco_consolidado", "inundacao"],
        "rationale": "Onde está o risco agora: alertas vivos + síntese consolidada.",
    },
    {
        "id": "desastre_historico",
        "keywords": ["desastre", "s2id", "histórico", "historico", "recorrente", "hotspot"],
        "layers": ["bairros", "desastres", "inundacao", "vulnerabilidade"],
        "rationale": "Histórico S2ID cruzado com inundação e vulnerabilidade (hotspots estruturais).",
    },
    {
        "id": "calor_uhi",
        "keywords": ["calor", "ilha de calor", "temperatura", "lst", "uhi", "ondas de calor"],
        "layers": ["bairros", "lst_observada", "cobertura", "vulnerabilidade"],
        "rationale": "Temperatura de superfície e cobertura vegetal vs vulnerabilidade.",
    },
    {
        "id": "drenagem",
        "keywords": ["drenagem", "saneamento", "esgoto", "galeria", "bueiro"],
        "layers": ["bairros", "saneamento_drenagem", "inundacao", "cobertura"],
        "rationale": "Déficit de drenagem/saneamento sobre áreas de inundação.",
    },
    {
        "id": "territorio_especial",
        "keywords": ["quilombo", "indígena", "indigena", "favela", "comunidade", "território especial"],
        "layers": ["bairros", "territorios_especiais", "vulnerabilidade", "inundacao"],
        "rationale": "Territórios especiais sob vulnerabilidade e risco hídrico.",
    },
    {
        "id": "risco_consolidado",
        "keywords": ["risco consolidado", "semáforo", "semaforo", "onde está o risco", "painel de risco"],
        "layers": ["bairros", "risco_consolidado"],
        "rationale": "Mapa síntese Score Sinidu × alerta vivo.",
    },
    {
        "id": "edificacoes_3d",
        "keywords": ["edifício", "edificio", "prédio", "predio", "construção", "3d", "lod1"],
        "layers": ["bairros", "edificacoes", "inundacao"],
        "rationale": "Edificações LOD1 com contexto de inundação.",
    },
]


def _normalize(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"\s+", " ", t)
    return t


def recommend_layer_crosswalk(
    pergunta: str,
    *,
    cod_ibge: str | None = None,
) -> dict[str, Any]:
    """Sugere camadas a cruzar a partir da pergunta do gestor."""
    text = _normalize(pergunta)
    if not text.strip():
        return {
            "cod_ibge": cod_ibge,
            "recommended_layers": ["bairros", "vulnerabilidade", "inundacao"],
            "preset_id": "cruzar_riscos_default",
            "rationale": "Pergunta vazia — preset padrão Cruzar riscos.",
            "matched_rule": None,
        }

    best: dict[str, Any] | None = None
    best_score = 0
    for rule in _RULES:
        keywords = rule["keywords"]
        hits = sum(1 for k in keywords if k in text)
        require_any = rule.get("require_any")
        if require_any:
            groups_ok = all(any(k in text for k in group) for group in require_any)
            if not groups_ok:
                continue
            score = hits + 3
        else:
            if hits == 0:
                continue
            score = hits
        if score > best_score:
            best_score = score
            best = rule

    if not best:
        return {
            "cod_ibge": cod_ibge,
            "recommended_layers": ["bairros", "vulnerabilidade", "inundacao"],
            "preset_id": "cruzar_riscos_default",
            "rationale": (
                "Não reconheci um cruzamento específico — sugiro vulnerabilidade × inundação. "
                "Tente perguntar p.ex. “onde há gente pobre em área de alagamento?”."
            ),
            "matched_rule": None,
        }

    return {
        "cod_ibge": cod_ibge,
        "recommended_layers": list(best["layers"]),
        "preset_id": best["id"],
        "rationale": best["rationale"],
        "matched_rule": best["id"],
        "mensagem": f"Sugestão de cruzamento ({best['id']}): {', '.join(best['layers'])}.",
    }
