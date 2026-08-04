"""Pilotos PE LiDAR — Camutanga e Ilha de Itamaracá."""
from __future__ import annotations

from app.data_connectors.cemaden_pluvio_collector import PILOT_UF_BY_IBGE
from app.data_connectors.constants import TARGET_IBGE_CODES, TARGET_MUNICIPALITIES
from app.data_connectors.s2id_collector import _PILOT_EVENTS
from ml.constants import ML_TARGET_IBGE_CODES, MUNICIPALITY_SLUGS


def test_pe_lidar_in_catalog():
    assert "2603603" in TARGET_IBGE_CODES
    assert "2607604" in TARGET_IBGE_CODES
    names = {m["nome"] for m in TARGET_MUNICIPALITIES}
    assert "Camutanga" in names
    assert "Ilha de Itamaracá" in names


def test_pe_lidar_ml_and_cemaden():
    assert "2603603" in ML_TARGET_IBGE_CODES
    assert "2607604" in ML_TARGET_IBGE_CODES
    assert MUNICIPALITY_SLUGS["camutanga"] == "2603603"
    assert MUNICIPALITY_SLUGS["ilha_de_itamaraca"] == "2607604"
    assert PILOT_UF_BY_IBGE["2603603"] == "PE"
    assert PILOT_UF_BY_IBGE["2607604"] == "PE"


def test_pe_lidar_s2id_curated():
    assert len(_PILOT_EVENTS["2603603"]) >= 2
    assert len(_PILOT_EVENTS["2607604"]) >= 2
