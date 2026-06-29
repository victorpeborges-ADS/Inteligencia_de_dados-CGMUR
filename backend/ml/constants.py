from __future__ import annotations

FLOOD_EVENT_TYPES = ("Inundação", "Alagamento Urbano", "Enxurrada")

# Cinco municípios com modelos dedicados (Mac Mini — treino < 5 min cada)
ML_TARGET_IBGE_CODES = [
    "2611606",  # Recife
    "2927408",  # Salvador
    "4314902",  # Porto Alegre
    "2507507",  # João Pessoa
    "4113700",  # Londrina
]

MUNICIPALITY_SLUGS: dict[str, str] = {
    "recife": "2611606",
    "salvador": "2927408",
    "porto_alegre": "4314902",
    "joao_pessoa": "2507507",
    "londrina": "4113700",
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
