# Model card — IBGE 2611606

- **model_version**: 1.5
- **model_kind**: full_below_baseline
- **algorithm**: hist_gradient_boosting
- **trained_at**: 2026-07-28T21:32:36Z
- **features**: precip_24h, precip_48h, precip_72h, precip_7d, mes_do_ano, impermeabilizacao_pct, cobertura_vegetal_pct, declividade_media, water_proximity, hand_media_m, pct_hand_lt_5m, curve_number, capacidade_drenagem_mm_h, saturacao_drenagem_40mm, duracao_chuva_h, intensidade_media_mm_h, intensidade_pico_proxy_mm_h, razao_intensidade_idf_tr2, suscetibilidade_hand, twi_media, precip_5d, precip_10d, precip_30d, sazonalidade_sin, sazonalidade_cos, tendencia_impermeabilizacao_pp_a, lamina_proxy_mm, escoamento_excesso_mm, rede_saturada_flag, area_alagada_proxy_pct, cota_rio_disponivel, cota_rio_anomalia
- **n_positive (train fit)**: 25
- **label_policy**: official_only

## Hold-out temporal (21e)
- Treino ≤ 2021 / Teste ≥ 2022
- n_train=1740 (pos=25)
- n_test=269 (pos=24)
- AUC hold-out: 0.7388
- Brier modelo: 0.1789
- Brier chuva>50.0mm: 0.0855
- Brier climatologia: 0.0861
- Calibrado: True (isotonic_cv3)
- Bate baseline chuva: False
- Bate climatologia: False
- Descartar modelo: True

## Validação espacial (21e.5)
- Disponível: True
- Fonte: evento_alagamento_observado
- Eventos com geometria: 10
- Hit-rate (pontos na zona de risco): 0.0
- Jaccard bairros: 0.0
- Acordo: baixa
- Método da zona: top_25pct_suscetibilidade_local
- Narrativa: Poucos eventos na zona preditiva (0/10).

## Limitações
- Não substitui alerta CEMADEN nem hidrodinâmica 2D.
- IDF e grupo hidrológico ainda são proxies (qualidade Estimado).
- Poucos rótulos oficiais: métricas instáveis com n_pos baixo.
- Hit-rate espacial usa pontos S2ID/eventos (±50 m), não polígonos oficiais de área afetada.
