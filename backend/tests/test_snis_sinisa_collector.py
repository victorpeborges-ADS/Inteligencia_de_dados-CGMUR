"""Regressão do conector SNIS/SINISA."""

from __future__ import annotations

import pandas as pd

from app.data_connectors.snis_sinisa_collector import (
    _collect_from_dataframe,
    _detect_snis_columns,
    _normalize_codigo,
    _parse_pct,
    collect_snis_municipality,
    snis_status_label,
)


def test_normalize_codigo_snis():
    assert _normalize_codigo("2806701") == "2806701"
    assert _normalize_codigo(2806701) == "2806701"
    assert _normalize_codigo("invalid") is None


def test_parse_pct_variants():
    assert _parse_pct("97,2") == 97.2
    assert _parse_pct("55%") == 55.0
    assert _parse_pct("-") is None
    assert _parse_pct(None) is None


def test_detect_snis_columns_layout():
    df = pd.DataFrame(
        columns=[
            "codigo ibge",
            "municipio",
            "IN055 - cobertura agua",
            "IN056 - cobertura esgoto",
            "IN089 perdas agua",
            "IN063 tratamento esgoto",
        ]
    )
    cols = _detect_snis_columns(df)
    assert cols["codigo"] == "codigo ibge"
    assert cols["agua"] is not None
    assert cols["esgoto"] is not None


def test_collect_from_dataframe_municipal():
    df = pd.DataFrame(
        [
            {
                "codigo ibge": "2611606",
                "IN055 - cobertura agua": 97.2,
                "IN056 - cobertura esgoto": 67.8,
                "IN089 perdas agua": 42.1,
                "IN063 tratamento esgoto": 45.3,
            }
        ]
    )
    payload = _collect_from_dataframe(df, "2611606")
    assert payload is not None
    assert payload["cobertura_agua_pct"] == 97.2
    assert payload["data_quality"] == "oficial"


def test_collect_snis_municipality_recife_oficial():
    payload = collect_snis_municipality("2611606")
    assert payload["data_quality"] == "oficial"
    assert payload["cobertura_agua_pct"] == 97.2
    assert payload["cobertura_esgoto_pct"] == 67.8
    assert payload["ano_referencia"] == 2022


def test_collect_snis_municipality_sao_cristovao_oficial():
    payload = collect_snis_municipality("2806701")
    assert payload["data_quality"] == "oficial"
    assert payload["cobertura_esgoto_pct"] == 22.3


def test_collect_snis_municipality_uf_proxy():
    payload = collect_snis_municipality("2604106")  # Caruaru — sem entrada municipal direta
    assert payload["data_quality"] == "estimado"
    assert payload["cobertura_agua_pct"] is not None
    assert "UF" in payload["fonte"]


def test_snis_status_label():
    assert snis_status_label("oficial") == "Integrado"
    assert snis_status_label("estimado") == "Estimado"
    assert snis_status_label("lacuna") == "Ausente"
