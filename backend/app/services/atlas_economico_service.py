"""Contexto econômico estadual — Atlas Econômico IPEA/RFB (referência UF).

O Atlas Econômico opera em 27 UFs, 68 atividades e 128 produtos (base NF-e 2018).
Não há API municipal; este serviço expõe metadados honestos + link institucional.
"""

from __future__ import annotations

from typing import Any

ATLAS_PORTAL_URL = "https://www.ipea.gov.br/atlaseconomico/"
ATLAS_BASE_YEAR = 2018
ATLAS_ACTIVITIES = 68
ATLAS_PRODUCTS = 128

UF_NAMES: dict[str, str] = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}


def build_atlas_uf_context(uf_sigla: str, *, codigo_ibge: str | None = None) -> dict[str, Any]:
    uf = (uf_sigla or "").upper()[:2]
    return {
        "uf_sigla": uf,
        "uf_nome": UF_NAMES.get(uf, uf),
        "referencia_ano": ATLAS_BASE_YEAR,
        "atividades_economicas": ATLAS_ACTIVITIES,
        "produtos": ATLAS_PRODUCTS,
        "matrizes": ["MIP-IR", "MAI-IR", "TRU-IR"],
        "fonte": "Atlas Econômico IPEA / Receita Federal (NF-e)",
        "escopo": "estadual",
        "qualidade": "referencia_estadual",
        "portal_url": ATLAS_PORTAL_URL,
        "descricao": (
            f"Estrutura produtiva, multiplicadores e fluxos de investimento da UF {UF_NAMES.get(uf, uf)} "
            f"— referência {ATLAS_BASE_YEAR}. Indicadores estaduais; não substituem dados municipais."
        ),
        "codigo_ibge_municipio": codigo_ibge,
        "kpis": [
            {"label": "Atividades econômicas", "valor": str(ATLAS_ACTIVITIES)},
            {"label": "Produtos na matriz", "valor": str(ATLAS_PRODUCTS)},
            {"label": "Base de dados", "valor": f"NF-e {ATLAS_BASE_YEAR}"},
        ],
    }
