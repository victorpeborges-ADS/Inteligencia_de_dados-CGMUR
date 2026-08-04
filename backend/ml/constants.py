from __future__ import annotations

FLOOD_EVENT_TYPES = ("Inundação", "Alagamento Urbano", "Enxurrada")

# Modelos dedicados alinhados ao catálogo piloto (8 municípios).
ML_TARGET_IBGE_CODES = [
    "2611606",  # Recife
    "2800308",  # Aracaju
    "2927408",  # Salvador
    "3550308",  # São Paulo
    "3304557",  # Rio de Janeiro
    "5300108",  # Brasília
    "2603603",  # Camutanga
    "2607604",  # Ilha de Itamaracá
]

MUNICIPALITY_SLUGS: dict[str, str] = {
    "recife": "2611606",
    "aracaju": "2800308",
    "salvador": "2927408",
    "sao_paulo": "3550308",
    "rio_de_janeiro": "3304557",
    "brasilia": "5300108",
    "camutanga": "2603603",
    "ilha_de_itamaraca": "2607604",
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
    # Fase 21d — variáveis físicas
    "water_proximity",
    "hand_media_m",
    "pct_hand_lt_5m",
    "curve_number",
    "capacidade_drenagem_mm_h",
    "saturacao_drenagem_40mm",
    # Fase 21d.1 — duração / intensidade
    "duracao_chuva_h",
    "intensidade_media_mm_h",
    "intensidade_pico_proxy_mm_h",
    "razao_intensidade_idf_tr2",
    # Fase 21d.5 — suscetibilidade HAND/TWI
    "suscetibilidade_hand",
    "twi_media",
    # Fase 21d.6 — estado antecedente + sazonalidade + tendência impermeab.
    "precip_5d",
    "precip_10d",
    "precip_30d",
    "sazonalidade_sin",
    "sazonalidade_cos",
    "tendencia_impermeabilizacao_pp_a",
    # Fase 21d.8 — proxies físicos (SCS + rede) ligados à simulação
    "lamina_proxy_mm",
    "escoamento_excesso_mm",
    "rede_saturada_flag",
    "area_alagada_proxy_pct",
    # Fase 21d.9 — cota de rio (ANA); 0 se série ausente
    "cota_rio_disponivel",
    "cota_rio_anomalia",
]

# Defaults quando o artefato antigo não tem a feature no meta.terrain
FEATURE_DEFAULTS: dict[str, float] = {
    "water_proximity": 0.1,
    "hand_media_m": 12.0,
    "pct_hand_lt_5m": 15.0,
    "curve_number": 85.0,
    "capacidade_drenagem_mm_h": 18.0,
    "saturacao_drenagem_40mm": 0.5,
    "duracao_chuva_h": 6.0,
    "intensidade_media_mm_h": 0.0,
    "intensidade_pico_proxy_mm_h": 0.0,
    "razao_intensidade_idf_tr2": 0.0,
    "suscetibilidade_hand": 0.35,
    "twi_media": 8.0,
    "precip_5d": 0.0,
    "precip_10d": 0.0,
    "precip_30d": 0.0,
    "sazonalidade_sin": 0.0,
    "sazonalidade_cos": 1.0,
    "tendencia_impermeabilizacao_pp_a": 0.0,
    "lamina_proxy_mm": 0.0,
    "escoamento_excesso_mm": 0.0,
    "rede_saturada_flag": 0.0,
    "area_alagada_proxy_pct": 0.0,
    "cota_rio_disponivel": 0.0,
    "cota_rio_anomalia": 0.0,
}

# Hold-out temporal (21e.1): treinar até este ano; validar anos seguintes
HOLDOUT_TRAIN_END_YEAR = 2021
HOLDOUT_TEST_START_YEAR = 2022

# 21d.7 — rótulo positivo se evento em [D-LABEL_LAG_BEFORE, D+LABEL_LAG_AFTER]
LABEL_LAG_BEFORE_DAYS = 3
LABEL_LAG_AFTER_DAYS = 1

MODEL_VERSION = "1.5"
BAIRRO_MODEL_VERSION = "1.1"

# 21f.1 — algoritmo padrão de produção (HistGradientBoosting via sklearn)
ML_ALGORITHM = "hist_gradient_boosting"

# 21f.2 — model_kind do artefato por bairro
BAIRRO_PRODUCTION_MODEL_KINDS = frozenset({"full_bairro", "full_bairro_no_holdout"})

# Colunas de terreno que vêm do parquet por bairro (o resto é precip/municipal)
BAIRRO_TERRAIN_FEATURE_KEYS = (
    "impermeabilizacao_pct",
    "cobertura_vegetal_pct",
    "declividade_media",
    "water_proximity",
    "curve_number",
    "capacidade_drenagem_mm_h",
    "saturacao_drenagem_40mm",
    "suscetibilidade_hand",  # preenchido com suscetibilidade_local
)

RF_PARAMS = {
    "n_estimators": 100,
    "max_depth": 10,
    "random_state": 42,
    "n_jobs": 2,
    "class_weight": "balanced",
}

# Mac mini 2018 / CPU: poucas iterações, early stopping, profundidade moderada
HGB_PARAMS = {
    "max_iter": 120,
    "max_depth": 6,
    "learning_rate": 0.08,
    "min_samples_leaf": 20,
    "l2_regularization": 0.1,
    "early_stopping": True,
    "validation_fraction": 0.15,
    "n_iter_no_change": 12,
    "random_state": 42,
}
