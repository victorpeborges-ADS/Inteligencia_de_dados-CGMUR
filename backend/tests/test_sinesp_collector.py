"""Testes unitários do coletor SINESP (sem download de rede)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from app.data_connectors import sinesp_collector as sc


def test_normalize_code():
    assert sc._normalize_code("2611606") == "2611606"
    assert sc._normalize_code(2611606.0) == "2611606"
    assert sc._normalize_code("bad") == "0000bad"


def test_normalize_code_invalid_falls_back():
    out = sc._normalize_code(None)
    assert isinstance(out, str)
    assert len(out) == 7


def test_build_index_from_minimal_xlsx(tmp_path: Path):
    df = pd.DataFrame(
        {
            "Cód_IBGE": [2611606, 2611606, 2611606],
            "Mês/Ano": ["2024-01-01", "2024-06-01", "2024-12-01"],
            "Vítimas": [2, 3, 5],
        }
    )
    xlsx = tmp_path / "sinesp.xlsx"
    with pd.ExcelWriter(xlsx) as writer:
        df.to_excel(writer, sheet_name="PE", index=False)
        pd.DataFrame({"x": [1]}).to_excel(writer, sheet_name="XX", index=False)

    index = sc._build_index(xlsx)
    assert "2611606" in index
    assert index["2611606"]["mortes_violentas"] == 10
    assert index["2611606"]["periodo_meses"] == 3


def test_build_index_empty_when_no_uf_sheets(tmp_path: Path):
    xlsx = tmp_path / "empty.xlsx"
    pd.DataFrame({"a": [1]}).to_excel(xlsx, sheet_name="ZZ", index=False)
    assert sc._build_index(xlsx) == {}


def test_fetch_municipio_sinesp_with_index():
    sc._index = {
        "2611606": {
            "mes_ref": "2024-12",
            "mortes_violentas": 12,
            "ocorrencias_violentas": 12,
            "roubos": 0,
            "fonte": "SINESP",
            "periodo_meses": 12,
        }
    }
    try:
        row = sc.fetch_municipio_sinesp("2611606", populacao=100_000)
        assert row is not None
        assert row["mortes_violentas"] == 12
        assert row["taxa_100k"] == 12.0
        assert sc.fetch_municipio_sinesp("9999999") is None
    finally:
        sc._index = None


@patch("app.data_connectors.sinesp_collector.download_sinesp_xlsx")
def test_load_sinesp_index_uses_cache(mock_dl, tmp_path: Path):
    sc._index = None
    df = pd.DataFrame(
        {
            "Cód_IBGE": [3550308],
            "Mês/Ano": ["2024-05-01"],
            "Vítimas": [1],
        }
    )
    xlsx = tmp_path / "sp.xlsx"
    with pd.ExcelWriter(xlsx) as writer:
        df.to_excel(writer, sheet_name="SP", index=False)
    mock_dl.return_value = xlsx

    idx = sc.load_sinesp_index(force_download=True)
    assert "3550308" in idx
    # second call hits memory cache
    mock_dl.reset_mock()
    again = sc.load_sinesp_index()
    assert again is idx
    mock_dl.assert_not_called()
    sc._index = None


@patch("etl.etl_seguranca_sinesp.process_municipio", return_value=False)
def test_ensure_sinesp_loaded_process_fail(mock_proc):
    assert sc.ensure_sinesp_loaded(MagicMock(), MagicMock(codigo_ibge="2611606")) is None
    mock_proc.assert_called_once()
