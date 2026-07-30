# Model card — IBGE 2611606

- **model_version**: 1.1
- **model_kind**: full_bairro_below_baseline
- **algorithm**: hist_gradient_boosting
- **trained_at**: 2026-07-28T21:33:46Z
- **features**: precip_24h, precip_48h, precip_72h, precip_7d, mes_do_ano, impermeabilizacao_pct, cobertura_vegetal_pct, declividade_media, water_proximity, hand_media_m, pct_hand_lt_5m, curve_number, capacidade_drenagem_mm_h, saturacao_drenagem_40mm, duracao_chuva_h, intensidade_media_mm_h, intensidade_pico_proxy_mm_h, razao_intensidade_idf_tr2, suscetibilidade_hand, twi_media, precip_5d, precip_10d, precip_30d, sazonalidade_sin, sazonalidade_cos, tendencia_impermeabilizacao_pp_a, lamina_proxy_mm, escoamento_excesso_mm, rede_saturada_flag, area_alagada_proxy_pct, cota_rio_disponivel, cota_rio_anomalia
- **n_positive (train fit)**: 140
- **label_policy**: official_spatial_or_susc_quartile

## Hold-out temporal (21e)
- Treino ≤ 2021 / Teste ≥ 2022
- n_train=3757 (pos=140)
- n_test=533 (pos=25)
- AUC hold-out: 0.7003
- Brier modelo: 0.0609
- Brier chuva>50.0mm: 0.0563
- Brier climatologia: 0.0503
- Calibrado: True (isotonic_cv3)
- Bate baseline chuva: False
- Bate climatologia: False
- Descartar modelo: True

## Validação espacial (21e.5)
- Disponível: None
- Fonte: —
- Eventos com geometria: None
- Hit-rate (pontos na zona de risco): None
- Jaccard bairros: None
- Acordo: None
- Método da zona: None
- Narrativa: —

## Limitações
- Não substitui alerta CEMADEN nem hidrodinâmica 2D.
- IDF e grupo hidrológico ainda são proxies (qualidade Estimado).
- Poucos rótulos oficiais: métricas instáveis com n_pos baixo.
- Hit-rate espacial usa pontos S2ID/eventos (±50 m), não polígonos oficiais de área afetada.
