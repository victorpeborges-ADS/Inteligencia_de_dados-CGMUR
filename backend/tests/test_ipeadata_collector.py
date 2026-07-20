"""Testes do coletor Ipeadata / IDHM."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.data_connectors.ipeadata_collector import (
    _parse_float,
    collect_idhm_municipality,
    fetch_idhm_live,
    load_idhm_csv,
)


def test_parse_float():
    assert _parse_float("0,742") == 0.742
    assert _parse_float("") is None
    assert _parse_float(None) is None
    assert _parse_float("x") is None


def test_load_idhm_csv(tmp_path: Path):
    csv_path = tmp_path / "idhm.csv"
    csv_path.write_text(
        "codigo_ibge,idh,idh_ano,fonte\n2611606,0.772,2010,Atlas\n",
        encoding="utf-8",
    )
    rows = load_idhm_csv(csv_path)
    assert rows["2611606"]["idh"] == "0.772"
    assert load_idhm_csv(tmp_path / "missing.csv") == {}


@patch("app.data_connectors.ipeadata_collector.fetch_idhm_live", return_value=(0.8, 2010))
def test_collect_idhm_falls_back_to_live(mock_live, tmp_path: Path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("codigo_ibge,idh,idh_ano,fonte\n", encoding="utf-8")
    out = collect_idhm_municipality("2611606", csv_path=csv_path)
    assert out["idh"] == 0.8
    assert out["idh_qualidade"] == "oficial"
    mock_live.assert_called_once()


def test_collect_idhm_from_csv(tmp_path: Path):
    csv_path = tmp_path / "idhm.csv"
    csv_path.write_text(
        "codigo_ibge,idh,idh_ano,fonte\n3550308,\"0,805\",2010,Atlas\n",
        encoding="utf-8",
    )
    out = collect_idhm_municipality("3550308", csv_path=csv_path)
    assert out["idh"] == 0.805
    assert out["idh_ano"] == 2010


@patch("app.data_connectors.ipeadata_collector.fetch_json")
def test_fetch_idhm_live_finds_row(mock_json):
    mock_json.return_value = {
        "value": [
            {"TERCODIGO": "2611606", "VALDATA": "2010-01-01", "VALVALOR": 0.772},
        ]
    }
    val, year = fetch_idhm_live("2611606")
    assert val == 0.772
    assert year == 2010


@patch("app.data_connectors.ipeadata_collector.fetch_json", side_effect=RuntimeError("down"))
def test_fetch_idhm_live_handles_error(mock_json):
    assert fetch_idhm_live("2611606") == (None, None)
