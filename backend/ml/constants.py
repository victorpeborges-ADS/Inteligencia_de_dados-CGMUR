from __future__ import annotations

FLOOD_EVENT_TYPES = ("Inundação", "Alagamento Urbano", "Enxurrada")

# Modelos dedicados alinhados ao catálogo piloto (6 municípios).
ML_TARGET_IBGE_CODES = [
    "2611606",  # Recife
    "2800308",  # Aracaju
    "2927408",  # Salvador
    "3550308",  # São Paulo
    "3304557",  # Rio de Janeiro
    "5300108",  # Brasília
]

MUNICIPALITY_SLUGS: dict[str, str] = {
    "recife": "2611606",
    "aracaju": "2800308",
    "salvador": "2927408",
    "sao_paulo": "3550308",
    "rio_de_janeiro": "3304557",
    "brasilia": "5300108",
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
