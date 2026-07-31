"""Referência GeoReDUS para lacunas locais — Fase 16d.3 (sem ingestão nacional)."""

from __future__ import annotations

import unicodedata
from typing import Any

from sqlalchemy.orm import Session

from app.api.data_catalog import coverage_for_code
from app.models import Municipio

GEOREDUS_BASE_URL = "https://www.redus.org.br/georedus"

GEOREDUS_INDICATORS: list[dict[str, Any]] = [
    {
        "id": "georedus_censo_infra",
        "label": "Déficits domiciliares (Censo 2022)",
        "group": "Dados urbanos",
        "source": "GeoReDUS / IBGE",
        "keywords": ["censo", "domicilio", "domicílio", "arborizacao", "arborização", "calcada", "calçada",
                     "iluminacao", "iluminação", "saneamento", "agua", "água", "esgoto", "infraestrutura"],
        "catalog_gap_ids": ["ibge_cidades", "sinter"],
        "sinidu_layer": "socioeconomico",
        "description": "Indicadores de infraestrutura domiciliar por setor censitário.",
    },
    {
        "id": "georedus_inep",
        "label": "Matrículas escolares (INEP)",
        "group": "Dados urbanos",
        "source": "GeoReDUS / INEP",
        "keywords": ["inep", "educacao", "educação", "escola", "matricula", "matrícula", "creche",
                     "fundamental", "medio", "médio"],
        "catalog_gap_ids": ["inep_censo_escolar"],
        "sinidu_layer": "educacao",
        "description": "Matrículas por etapa de ensino com visualização intramunicipal.",
    },
    {
        "id": "georedus_saude",
        "label": "Equipamentos de saúde",
        "group": "Saúde e segurança",
        "source": "GeoReDUS / CNES",
        "keywords": ["saude", "saúde", "ubs", "hospital", "ambulatorio", "ambulatório", "cnes"],
        "catalog_gap_ids": [],
        "sinidu_layer": None,
        "description": "Hospitais, UBS e ambulatórios georreferenciados — ainda não integrado no Sinidu.",
    },
    {
        "id": "georedus_territorios",
        "label": "Quilombos, TIs e comunidades urbanas",
        "group": "Base",
        "source": "GeoReDUS / bases oficiais",
        "keywords": ["quilombo", "terra indigena", "terra indígena", "ti", "favela", "comunidade",
                     "periferia", "aglomerado"],
        "catalog_gap_ids": ["incra_quilombos", "funai_ti", "ibge_aglomerados"],
        "sinidu_layer": "territorios_especiais",
        "description": "Complemento nacional à camada Territórios Especiais do Sinidu.",
    },
    {
        "id": "georedus_lst",
        "label": "Temperatura de superfície (LST)",
        "group": "Clima",
        "source": "GeoReDUS / satélite",
        "keywords": ["lst", "temperatura", "calor", "ilha de calor", "superficie", "superfície"],
        "catalog_gap_ids": [],
        "sinidu_layer": "lst_observada",
        "description": "Série LST por satélite — no Sinidu disponível como camada externa vinculada ao GeoReDUS.",
    },
]


def georedus_municipio_url(codigo_ibge: str) -> str:
    code = str(codigo_ibge).zfill(7)[:7]
    return f"{GEOREDUS_BASE_URL}?v=v0&municipioId={code}"


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in folded if not unicodedata.combining(c))


def _match_query_indicators(query: str | None) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return []
    q = _normalize(query.strip())
    matched: list[dict[str, Any]] = []
    for item in GEOREDUS_INDICATORS:
        haystack = _normalize(
            " ".join(
                [
                    item["label"],
                    item["group"],
                    item["source"],
                    item["description"],
                    *item["keywords"],
                ]
            )
        )
        if any(kw in haystack and kw in q for kw in (_normalize(k) for k in item["keywords"])):
            matched.append(item)
        elif q in haystack:
            matched.append(item)
    return matched


def _gap_catalog_ids(gaps: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for gap in gaps:
        gid = gap.get("id")
        if gid:
            ids.add(str(gid))
    return ids


def _indicators_from_gaps(gap_ids: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in GEOREDUS_INDICATORS:
        if gap_ids.intersection(item.get("catalog_gap_ids") or []):
            out.append(item)
    return out


def _dedupe_indicators(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        iid = item["id"]
        if iid in seen:
            continue
        seen.add(iid)
        out.append(item)
    return out


def _public_indicator(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "label": item["label"],
        "group": item["group"],
        "source": item["source"],
        "description": item["description"],
        "sinidu_layer": item.get("sinidu_layer"),
    }


def build_georedus_referencia(
    db: Session,
    codigo_ibge: str,
    *,
    tema: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """Mapeia lacunas locais → indicadores GeoReDUS + deep link (sem ingestão)."""
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        return {"error": "Município não encontrado"}

    maturidade, bases, gaps = coverage_for_code(codigo_ibge, db)
    lacunas = [g.get("nome") or g.get("id") for g in gaps]
    gap_ids = _gap_catalog_ids(gaps)

    search_text = " ".join(filter(None, [tema, query]))
    from_query = _match_query_indicators(search_text)
    from_gaps = _indicators_from_gaps(gap_ids)

    indicadores = _dedupe_indicators(from_query + from_gaps)
    if not indicadores and lacunas:
        indicadores = [_public_indicator(GEOREDUS_INDICATORS[0])]

    url = georedus_municipio_url(codigo_ibge)
    tem_lacunas = bool(lacunas)

    instrucao = (
        f"Para dados não disponíveis localmente em {muni.nome}/{muni.uf}, oriente o gestor a consultar "
        f"o GeoReDUS (catálogo nacional ReDUS/CEM-USP) em: {url}. "
        "Não invente valores do GeoReDUS — cite apenas o link e os indicadores sugeridos abaixo."
    )

    return {
        "codigo_ibge": codigo_ibge,
        "municipio": {"nome": muni.nome, "uf": muni.uf},
        "georedus_url": url,
        "maturidade_percentual": maturidade,
        "lacunas_locais": lacunas[:8],
        "indicadores_sugeridos": [_public_indicator(i) for i in indicadores[:6]],
        "tem_lacunas": tem_lacunas,
        "instrucao_agente": instrucao,
        "nota": "Referência externa — o Sinidu não duplica a ingestão nacional do GeoReDUS.",
    }


def georedus_summary_for_context(
    db: Session,
    codigo_ibge: str,
) -> dict[str, Any]:
    """Resumo compacto para contexto municipal / prompt RAG."""
    ref = build_georedus_referencia(db, codigo_ibge)
    if ref.get("error"):
        return {}
    lines = [
        f"GeoReDUS (referência externa): {ref['georedus_url']}",
        "Use quando dados locais estiverem ausentes ou parciais — não invente valores do GeoReDUS.",
    ]
    if ref.get("lacunas_locais"):
        lines.append(f"Lacunas locais: {', '.join(ref['lacunas_locais'][:5])}.")
    if ref.get("indicadores_sugeridos"):
        labels = ", ".join(i["label"] for i in ref["indicadores_sugeridos"][:4])
        lines.append(f"Indicadores GeoReDUS sugeridos: {labels}.")
    return {
        "georedus_url": ref["georedus_url"],
        "georedus_indicadores": ref.get("indicadores_sugeridos") or [],
        "georedus_summary": "\n".join(lines),
        "tem_lacunas": ref.get("tem_lacunas", False),
    }


def detect_georedus_source_url(message: str, answer: str, georedus_url: str | None) -> str | None:
    """Retorna URL GeoReDUS quando resposta ou pergunta indicam lacuna externa."""
    if not georedus_url:
        return None
    combined = _normalize(f"{message} {answer}")
    if "georedus" in combined or "redus.org.br" in combined:
        return georedus_url
    external_topics = (
        "saude", "saúde", "ubs", "cnes", "hospital",
        "matricula", "matrícula", "inep", "educacao", "educação",
        "quilombo", "terra indigena", "comunidade urbana",
        "nao esta disponivel", "não está disponível", "nao disponivel", "não disponível",
        "lacuna", "ausente", "parcial",
    )
    if any(t in combined for t in external_topics):
        return georedus_url
    return None
