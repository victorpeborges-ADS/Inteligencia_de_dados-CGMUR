"""Metadados estáticos das camadas do mapa — fonte, descrição e vínculo ao catálogo."""

from __future__ import annotations

from typing import Any

from app.services.catalog_coverage import BASE_CATALOG
from app.services.catalog_source_registry import FONTE_REGISTRY

FONTE_NOMES = {item["id"]: item["nome"] for item in BASE_CATALOG}

# Camada → fontes do catálogo (reutiliza catalog_coverage / FONTE_REGISTRY)
LAYER_FONTE_IDS: dict[str, list[str]] = {
    "municipio": ["ibge_cidades", "inde"],
    "bairros": ["ibge_cidades"],
    "infraestrutura": [],
    "educacao": ["inep_censo_escolar"],
    "territorios_especiais": ["incra_quilombos", "funai_ti", "ibge_aglomerados"],
    "socioeconomico": ["ibge_cidades", "sinter"],
    "cobertura": ["mapbiomas"],
    "lst_observada": [],
    "vulnerabilidade": ["mapbiomas", "geosgb", "s2id"],
    "inundacao": ["s2id", "cemaden_georiscos"],
    "alertas": ["cemaden_georiscos"],
    "desastres": ["s2id", "ibge_singedlab_rs"],
    "saneamento_drenagem": ["snis_sinisa"],
    "adaptacao_climatica": ["adapta_brasil", "mapbiomas"],
    "prioridade_planejamento": ["munic"],
    "lacunas_dados": ["brasil_mais", "inde"],
    "saude_risco": ["ibge_cidades"],
    "seguranca_publica": [],
    "vulnerabilidade_multidimensional": ["mapbiomas", "s2id"],
}

LAYER_DESCRICOES: dict[str, str] = {
    "municipio": "Limite territorial oficial do município selecionado, base para recorte e contexto regional.",
    "bairros": "Malha de bairros ou setores censitários — oficial (IBGE/Censo 2022) ou estimada (Voronoi Sinidu+Clima).",
    "infraestrutura": "Equipamentos urbanos e redes viárias mapeados via OpenStreetMap e bases locais curadas.",
    "educacao": (
        "Escolas de educação básica com matrículas por etapa (infantil, fundamental, médio) — "
        "INEP Censo Escolar. Marcadores proporcionais ao volume de matrículas."
    ),
    "territorios_especiais": (
        "Quilombos certificados (INCRA), terras indígenas (FUNAI) e comunidades urbanas "
        "(aglomerados subnormais IBGE) — base para vulnerabilidade multidimensional e planejamento."
    ),
    "socioeconomico": (
        "Indicadores socioeconômicos por setor censitário: renda relativa e déficits domiciliares "
        "(arborização, calçada, iluminação, água, esgoto, lixo, alfabetização) do Censo 2022."
    ),
    "cobertura": "Uso e cobertura do solo municipal derivado do MapBiomas com partição espacial Sinidu+Clima.",
    "lst_observada": (
        "Temperatura de superfície terrestre (LST) observada por satélite Landsat 8/9 (média máxima 2021–2025). "
        "Referência GeoReDUS — complementa a simulação exploratória de calor Sinidu."
    ),
    "vulnerabilidade": "Índice de Vulnerabilidade Climática (IVC) composto: demografia IBGE, cobertura MapBiomas e histórico S2ID.",
    "inundacao": "Risco de inundação territorial (IRI) a partir de hidrografia, impermeabilização e eventos S2ID.",
    "alertas": "Alertas hidrológicos e de deslizamento em tempo quase real — CEMADEN / GeoRiscos.",
    "desastres": "Histórico oficial de desastres naturais registrados no S2ID/SEDEC e exposição SINGED Lab quando disponível.",
    "saneamento_drenagem": "Indicadores de saneamento (SNIS/SINISA) combinados com risco de drenagem territorial Sinidu+Clima.",
    "adaptacao_climatica": "Capacidade de adaptação climática municipal — AdaptaBrasil/INPE e proxies MapBiomas.",
    "prioridade_planejamento": "Priorização de intervenções urbanas com base em planos locais e score Sinidu+Clima.",
    "lacunas_dados": "Radar de maturidade e lacunas de integração de fontes oficiais no município.",
    "saude_risco": "Cruzamento de unidades de saúde (CNES/DataSUS) com manchas de risco climático territorial.",
    "seguranca_publica": "Indicadores de criminalidade municipal (SINESP/dados.gov.br) para contexto de vulnerabilidade urbana.",
    "vulnerabilidade_multidimensional": (
        "Vulnerabilidade multidimensional (VM) Sinidu+Clima — renda, exposição a riscos, cobertura vegetal e desastres."
    ),
}

LAYER_GRUPOS: dict[str, str] = {
    "municipio": "Base",
    "bairros": "Base",
    "infraestrutura": "Dados urbanos",
    "educacao": "Dados urbanos",
    "socioeconomico": "Dados urbanos",
    "cobertura": "Clima e riscos",
    "lst_observada": "Clima e riscos",
    "vulnerabilidade": "Clima e riscos",
    "inundacao": "Clima e riscos",
    "alertas": "Clima e riscos",
    "desastres": "Clima e riscos",
    "saneamento_drenagem": "Planejamento",
    "adaptacao_climatica": "Planejamento",
    "prioridade_planejamento": "Planejamento",
    "lacunas_dados": "Planejamento",
    "saude_risco": "Saúde e segurança",
    "seguranca_publica": "Saúde e segurança",
    "vulnerabilidade_multidimensional": "Saúde e segurança",
}


def _fonte_labels(fonte_ids: list[str]) -> list[dict[str, str]]:
    labels: list[dict[str, str]] = []
    for fid in fonte_ids:
        meta = FONTE_REGISTRY.get(fid, {})
        labels.append({
            "id": fid,
            "nome": FONTE_NOMES.get(fid, fid),
            "descricao_curta": meta.get("descricao_curta", ""),
        })
    return labels


def base_layer_entry(layer_id: str) -> dict[str, Any]:
    fonte_ids = LAYER_FONTE_IDS.get(layer_id, [])
    return {
        "descricao": LAYER_DESCRICOES.get(layer_id, ""),
        "grupo": LAYER_GRUPOS.get(layer_id, ""),
        "fontes_catalogo": _fonte_labels(fonte_ids),
    }


def merge_layers_meta(dynamic_layers: dict[str, Any]) -> dict[str, Any]:
    """Mescla metadados estáticos do registro com overrides dinâmicos da API."""
    merged: dict[str, Any] = {}
    all_ids = set(LAYER_DESCRICOES) | set(dynamic_layers)
    for layer_id in sorted(all_ids):
        base = base_layer_entry(layer_id)
        patch = dynamic_layers.get(layer_id) or {}
        if not isinstance(patch, dict):
            patch = {}
        entry = {**base, **patch}
        if not entry.get("descricao"):
            entry["descricao"] = base["descricao"]
        merged[layer_id] = entry
    return merged
