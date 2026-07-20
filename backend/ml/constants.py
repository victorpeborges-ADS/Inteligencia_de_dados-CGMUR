from __future__ import annotations

FLOOD_EVENT_TYPES = ("Inundação", "Alagamento Urbano", "Enxurrada")

# Municípios com modelos dedicados (baseline em artifacts; treino full via ETL).
# Expansão jul/2026: 5 → 10 (capitals/piloto com risco pluvial relevante).
ML_TARGET_IBGE_CODES = [
    "2611606",  # Recife
    "2927408",  # Salvador
    "4314902",  # Porto Alegre
    "2507507",  # João Pessoa
    "4113700",  # Londrina
    "2800308",  # Aracaju (boot priority)
    "2304400",  # Fortaleza
    "1501402",  # Belém
    "4106902",  # Curitiba
    "3304557",  # Rio de Janeiro
]

MUNICIPALITY_SLUGS: dict[str, str] = {
    "recife": "2611606",
    "salvador": "2927408",
    "porto_alegre": "4314902",
    "joao_pessoa": "2507507",
    "londrina": "4113700",
    "aracaju": "2800308",
    "fortaleza": "2304400",
    "belem": "1501402",
    "curitiba": "4106902",
    "rio_de_janeiro": "3304557",
}

SLUG_BY_IBGE = {v: k for k, v in MUNICIPALITY_SLUGS.items()}

FEATURE_COLUMNS = [
    "precip_24h",
    "precip_48h",
    "precip_72h",
    "precip_7d",
    "mes_do_ano",
    "impermeabilizacao_pct",
    "cobertura_vegetal_pct",
    "declividade_media",
]

MODEL_VERSION = "1.0"

RF_PARAMS = {
    "n_estimators": 100,
    "max_depth": 10,
    "random_state": 42,
    "n_jobs": 2,
    "class_weight": "balanced",
}
