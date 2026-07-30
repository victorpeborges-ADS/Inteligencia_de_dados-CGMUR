"""Testes das âncoras históricas e impactos operacionais de chuva."""

from app.services.rainfall_event_anchors import (
    estimate_operational_impacts,
    match_anchor,
    rainfall_anchors_for,
)


def test_recife_anchors_slider_and_maio_2022():
    cat = rainfall_anchors_for("2611606")
    assert cat["slider"]["max_mm"] >= 190
    assert len(cat["anchors"]) >= 4
    maio = match_anchor("2611606", 190)
    assert maio is not None
    assert "2022" in maio["label"]
    assert maio["url"]


def test_operational_impacts_drainage_reduces_time():
    imp = estimate_operational_impacts(
        precip_mm=150,
        max_depth_m=0.6,
        affected_area_km2=8.0,
        affected_population=10000,
        landslide_zones=3,
        drainage_cap_mm_h=20,
        drain_removed_mm=30,
        drenagem_aplicada=True,
    )
    esc = imp["escoamento"]
    assert esc["tempo_com_intervencoes_h"] < esc["tempo_sem_intervencao_h"]
    assert imp["mobilidade"]["nivel"] in {"MODERADO", "SEVERO", "CRITICO"}
    assert imp["mobilidade"]["populacao_com_ir_e_vir_impedido"] > 0
    assert imp["deslizamento"]["zonas_estimadas"] == 3
