"""Testes unitários Fase 21d (HAND/CN/drenagem) e 21c.1 (parser S2ID nacional)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.services.drainage_capacity_service import bairro_drainage_capacity_mm_h
from app.services.hand_service import compute_hand_raster
from app.services.scs_cn_service import bairro_cn_proxy, cn_for_class, scs_runoff_mm
from app.data_connectors.s2id_nacional_collector import iter_flood_events_from_csv
from ml.constants import FEATURE_COLUMNS, FEATURE_DEFAULTS


def test_feature_columns_include_21d():
    for col in (
        "water_proximity",
        "hand_media_m",
        "pct_hand_lt_5m",
        "curve_number",
        "capacidade_drenagem_mm_h",
        "saturacao_drenagem_40mm",
        "duracao_chuva_h",
        "intensidade_media_mm_h",
        "intensidade_pico_proxy_mm_h",
        "razao_intensidade_idf_tr2",
        "suscetibilidade_hand",
        "twi_media",
        "precip_5d",
        "precip_10d",
        "precip_30d",
        "sazonalidade_sin",
        "sazonalidade_cos",
        "tendencia_impermeabilizacao_pp_a",
        "lamina_proxy_mm",
        "escoamento_excesso_mm",
        "rede_saturada_flag",
        "area_alagada_proxy_pct",
    ):
        assert col in FEATURE_COLUMNS
        assert col in FEATURE_DEFAULTS


def test_physics_proxies_21d8_heavy_rain_saturates():
    from ml.physics_proxy import compute_flood_physics_proxies

    dry = compute_flood_physics_proxies(
        5.0, curve_number=90.0, capacidade_drenagem_mm_h=20.0, duracao_chuva_h=6.0
    )
    assert dry["rede_saturada_flag"] == 0.0
    assert dry["escoamento_excesso_mm"] == 0.0

    wet = compute_flood_physics_proxies(
        120.0,
        curve_number=92.0,
        capacidade_drenagem_mm_h=10.0,
        impermeabilizacao_pct=85.0,
        suscetibilidade_hand=0.8,
        pct_hand_lt_5m=40.0,
        duracao_chuva_h=3.0,
    )
    assert wet["lamina_proxy_mm"] > 0
    assert wet["escoamento_excesso_mm"] > 0
    assert wet["rede_saturada_flag"] == 1.0
    assert wet["area_alagada_proxy_pct"] > dry["area_alagada_proxy_pct"]


def test_suscetibilidade_hand_higher_when_low_hand():
    from ml.susceptibility import bairro_suscetibilidade, suscetibilidade_from_hand

    high = suscetibilidade_from_hand(2.0, 60.0, twi_media=12.0)
    low = suscetibilidade_from_hand(20.0, 5.0, twi_media=5.0)
    assert high > low
    dense = bairro_suscetibilidade(85.0, 0.4, 1.5, hand_media_m=3.0, pct_hand_lt_5m=50.0)
    green = bairro_suscetibilidade(20.0, 0.05, 8.0, hand_media_m=18.0, pct_hand_lt_5m=5.0)
    assert dense > green


def test_scs_cn_urban_higher_than_forest():
    assert cn_for_class("Área Urbana", "C") > cn_for_class("Vegetação / Floresta", "C")
    q = scs_runoff_mm(50.0, 90.0)
    assert q > 0
    assert scs_runoff_mm(5.0, 90.0) < q


def test_bairro_cn_and_drainage_spatialization():
    cn_dense = bairro_cn_proxy(80.0, 5.0, 0.2)
    cn_green = bairro_cn_proxy(20.0, 60.0, 0.05)
    assert cn_dense > cn_green
    cap_dense = bairro_drainage_capacity_mm_h(25.0, impermeabilizacao_pct=85.0, water_proximity=0.3)
    cap_green = bairro_drainage_capacity_mm_h(25.0, impermeabilizacao_pct=20.0, water_proximity=0.0)
    assert cap_dense < cap_green


def test_hand_stream_cells_zero():
    # Vale artificial: centro mais baixo
    elev = np.ones((20, 20), dtype=np.float64) * 50.0
    for r in range(20):
        elev[r, 10] = 40.0 - abs(r - 10) * 0.1
    mask = np.ones((20, 20), dtype=bool)
    hand, meta = compute_hand_raster(elev, mask, stream_percentile=90.0)
    assert meta["ok"]
    assert meta["stream_cells"] > 0
    stream_vals = hand[np.isfinite(hand) & (hand == 0)]
    assert len(stream_vals) >= meta["stream_cells"] * 0.5


def test_s2id_csv_parser_extracts_ibge(tmp_path: Path):
    sample = tmp_path / "s2id_sample.csv"
    sample.write_text(
        "\n".join(
            [
                "Relatório S2ID",
                "Fonte: SEDEC",
                "",
                "UF;Município;Registro;COBRADE;Data",
                "PE;Recife;PE-F-2611606-12100-20220528;12100 - Inundações;28/05/2022",
                "PE;Recife;PE-F-2611606-13214-20221230;13214 - Chuvas Intensas;30/12/2022",
                "SP;São Paulo;SP-F-3550308-11110-20220101;11110 - Terremoto;01/01/2022",
            ]
        ),
        encoding="latin-1",
    )
    events = iter_flood_events_from_csv(sample, ibge_filter=["2611606"])
    assert len(events) == 2
    assert all(e["codigo_ibge"] == "2611606" for e in events)
    assert {e["tipo"] for e in events} <= {"Inundação", "Alagamento Urbano", "Enxurrada"}
