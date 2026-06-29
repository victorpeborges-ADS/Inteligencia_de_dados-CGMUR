"""Regressão do parser CAPAG — layout Tesouro muda com frequência."""

from __future__ import annotations

import pandas as pd

from app.data_connectors.capag_collector import (
    _detect_capag_columns,
    _extract_indicadores,
    _normalize_codigo,
    _normalize_indicador_nota,
    _normalize_nota,
    collect_capag_municipality,
)


def test_normalize_codigo_variants():
    assert _normalize_codigo("2611606") == "2611606"
    assert _normalize_codigo("2611606.0") == "2611606"
    assert _normalize_codigo(2611606) == "2611606"
    assert _normalize_codigo("invalid") is None


def test_normalize_nota_capag_letters():
    assert _normalize_nota("A") == "A"
    assert _normalize_nota("b+") == "B"
    assert _normalize_nota("C ") == "C"
    assert _normalize_nota("-") is None
    assert _normalize_nota(None) is None


def test_normalize_indicador_nota_plus():
    assert _normalize_indicador_nota("A+") == "A+"
    assert _normalize_indicador_nota("b") == "B"


def test_detect_capag_columns_layout_v1():
    df = pd.DataFrame(
        columns=[
            "codigo ibge",
            "nome municipio",
            "capag",
            "indicador 1",
            "nota 1",
            "indicador 2",
            "nota 2",
        ]
    )
    code_col, note_col = _detect_capag_columns(df)
    assert code_col == "codigo ibge"
    assert note_col == "capag"


def test_detect_capag_columns_layout_v2_cod_ibge():
    df = pd.DataFrame(columns=["cod_ibge", "municipio", "classificacao", "indicador 1", "nota 1"])
    code_col, note_col = _detect_capag_columns(df)
    assert code_col == "cod_ibge"
    assert note_col == "classificacao"


def test_detect_capag_columns_layout_v3_capag_ano():
    df = pd.DataFrame(columns=["codigo_municipio_ibge", "capag 2024", "nota"])
    code_col, note_col = _detect_capag_columns(df)
    assert code_col == "codigo_municipio_ibge"
    assert note_col == "capag 2024"


def test_extract_indicadores_from_row():
    df = pd.DataFrame(
        [
            {
                "codigo ibge": "2611606",
                "capag": "A",
                "indicador 1": 0.42,
                "nota 1": "A",
                "indicador 2": 0.15,
                "nota 2": "B+",
                "indicador 3": 1.8,
                "nota 3": "A",
            }
        ]
    )
    items = _extract_indicadores(df.iloc[0], df)
    assert len(items) == 3
    assert items[0]["nome"] == "Endividamento"
    assert items[0]["nota"] == "A"
    assert items[1]["nota"] == "B+"
    assert items[0]["valor"] == 0.42


def test_collect_capag_municipality_from_mocked_xlsx(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "codigo ibge": "2806701",
                "capag": "B",
                "indicador 1": 0.55,
                "nota 1": "B",
                "indicador 2": 0.12,
                "nota 2": "A",
                "indicador 3": 1.2,
                "nota 3": "B",
                "origem da nota final": "Automática",
            },
            {
                "codigo ibge": "2611606",
                "capag": "A",
                "indicador 1": 0.3,
                "nota 1": "A",
                "indicador 2": 0.2,
                "nota 2": "A",
                "indicador 3": 2.0,
                "nota 3": "A",
            },
        ]
    )

    monkeypatch.setattr(
        "app.data_connectors.capag_collector._load_capag_dataframe",
        lambda: df,
    )

    payload = collect_capag_municipality("2806701")
    assert payload["nota_capag"] == "B"
    assert payload["nota_capag_raw"] == "B"
    assert payload["data_quality"] == "oficial"
    assert len(payload["indicadores"]) == 3
    assert payload["origem_nota"] == "Automática"


def test_collect_capag_municipality_missing_row(monkeypatch):
    df = pd.DataFrame([{"codigo ibge": "2611606", "capag": "A"}])
    monkeypatch.setattr(
        "app.data_connectors.capag_collector._load_capag_dataframe",
        lambda: df,
    )
    payload = collect_capag_municipality("9999999")
    assert payload["nota_capag"] is None
    assert payload["data_quality"] == "estimado"
