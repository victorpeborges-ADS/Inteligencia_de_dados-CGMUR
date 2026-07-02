"""Metadados de fontes do catálogo — impacto, dificuldade e campos do Score."""

from __future__ import annotations

from typing import Any

FONTE_REGISTRY: dict[str, dict[str, Any]] = {
    "ibge_cidades": {
        "campos_score": ["IVC (renda/demografia)", "Score Sinidu (base territorial)"],
        "impacto_confiabilidade": 4,
        "impacto_score_pts": 3,
        "dificuldade": "Técnica",
        "requisito": "API IBGE servicodados — já disponível",
        "descricao_curta": "Dados demográficos, socioeconômicos e territoriais oficiais do IBGE.",
        "integravel_etl": True,
    },
    "snis_sinisa": {
        "campos_score": ["IRI (saneamento/drenagem)", "Capacidade adaptativa"],
        "impacto_confiabilidade": 5,
        "impacto_score_pts": 4,
        "dificuldade": "Institucional",
        "requisito": "Carga SNIS/SINISA municipal ou estimativa derivada",
        "descricao_curta": "Indicadores de saneamento básico, drenagem e gestão de resíduos.",
        "integravel_etl": True,
    },
    "s2id": {
        "campos_score": ["IRI (40% histórico S2ID)", "Comparação histórica de desastres"],
        "impacto_confiabilidade": 6,
        "impacto_score_pts": 5,
        "dificuldade": "Técnica",
        "requisito": "Sincronização S2ID/SEDEC ou base curada",
        "descricao_curta": "Histórico oficial de desastres naturais e danos materiais.",
        "integravel_etl": True,
    },
    "mapbiomas": {
        "campos_score": ["IRI (impermeabilização)", "Cobertura vegetal", "IVC"],
        "impacto_confiabilidade": 7,
        "impacto_score_pts": 6,
        "dificuldade": "Técnica",
        "requisito": "Série MapBiomas Coleção 9 ou CSV local",
        "descricao_curta": "Uso e cobertura do solo — impermeabilização e vegetação.",
        "integravel_etl": True,
    },
    "cemaden_georiscos": {
        "campos_score": ["Alertas operacionais", "Monitoramento em tempo real"],
        "impacto_confiabilidade": 5,
        "impacto_score_pts": 3,
        "dificuldade": "Técnica",
        "requisito": "Feed CEMADEN/GeoRiscos",
        "descricao_curta": "Alertas hidrológicos e de deslizamento em tempo quase real.",
        "integravel_etl": True,
    },
    "adapta_brasil": {
        "campos_score": ["Capacidade de adaptação", "IVC (clima)"],
        "impacto_confiabilidade": 4,
        "impacto_score_pts": 3,
        "dificuldade": "Técnica",
        "requisito": "API AdaptaBrasil ou proxy MapBiomas",
        "descricao_curta": "Indicadores de adaptação climática do INPE.",
        "integravel_etl": True,
    },
    "geosgb": {
        "campos_score": ["IVC (vulnerabilidade geológica)", "Risco de recalque/argila"],
        "impacto_confiabilidade": 8,
        "impacto_score_pts": 8,
        "dificuldade": "Convênio",
        "requisito": "Convênio MCID-CPRM para GeoSGB",
        "descricao_curta": "Litologia, aptidão geológica e susceptibilidade do solo.",
        "integravel_etl": True,
    },
    "sinter": {
        "campos_score": ["Indicadores socioeconômicos", "Cadastro territorial"],
        "impacto_confiabilidade": 3,
        "impacto_score_pts": 2,
        "dificuldade": "Institucional",
        "requisito": "Integração SINTER/Receita Federal",
        "descricao_curta": "Cadastro territorial e imóveis urbanos.",
        "integravel_etl": False,
    },
    "munic": {
        "campos_score": ["Capacidade institucional", "Planejamento urbano"],
        "impacto_confiabilidade": 4,
        "impacto_score_pts": 3,
        "dificuldade": "Institucional",
        "requisito": "Pesquisa MUNIC/IBGE",
        "descricao_curta": "Gestão municipal e capacidade administrativa.",
        "integravel_etl": False,
    },
    "sirene": {
        "campos_score": ["Emissões / pressão urbana", "IVC indireto"],
        "impacto_confiabilidade": 4,
        "impacto_score_pts": 4,
        "dificuldade": "Institucional",
        "requisito": "Convênio MCTI/SIRENE",
        "descricao_curta": "Inventário nacional de emissões antrópicas.",
        "integravel_etl": True,
    },
    "inde": {
        "campos_score": ["Infraestrutura de dados espaciais", "Qualidade da malha"],
        "impacto_confiabilidade": 3,
        "impacto_score_pts": 2,
        "dificuldade": "Técnica",
        "requisito": "Metadados INDE/IDE municipal",
        "descricao_curta": "Infraestrutura de dados espaciais municipais.",
        "integravel_etl": False,
    },
    "brasil_mais": {
        "campos_score": ["Monitoramento territorial", "Score de confiabilidade"],
        "impacto_confiabilidade": 5,
        "impacto_score_pts": 5,
        "dificuldade": "Técnica",
        "requisito": "Integração Brasil MAIS / MCID",
        "descricao_curta": "Monitoramento territorial e indicadores MCID.",
        "integravel_etl": True,
    },
}

RADAR_AXES: dict[str, list[str]] = {
    "IBGE": ["ibge_cidades", "munic"],
    "Clima": ["mapbiomas", "adapta_brasil"],
    "Fiscal": ["sinter"],
    "Geoespacial": ["geosgb", "inde"],
    "Riscos": ["s2id", "cemaden_georiscos"],
    "Institucional": ["snis_sinisa", "sirene", "brasil_mais"],
}

STATUS_SCORE = {
    "Integrado": 1.0,
    "Estimado": 0.6,
    "Em integracao": 0.35,
    "Ausente": 0.0,
}
