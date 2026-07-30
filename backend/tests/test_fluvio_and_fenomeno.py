"""Testes Fase 21c.3/21d.9 — série fluviométrica ANA (CSV) + fenômeno pluvial/fluvial/misto."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from app.data_connectors.ana_hidroweb_collector import (
    collect_fluvio_series_for_municipality,
    parse_ana_fluvio_csv,
)
from app.services.evento_alagamento_service import _fenomeno_from_tipo
from app.services.fluvio_series_service import cota_features_for_dates


def test_parse_ana_fluvio_csv_basic(tmp_path: Path):
    csv_path = tmp_path / "2611606_capibaribe.csv"
    csv_path.write_text(
        "estacao;data;cota_m;vazao_m3s;latitude;longitude\n"
        "39075000;2024-05-27;3.42;185.0;-8.05;-34.90\n"
        "39075000;2024-05-28;3.85;210.5;-8.05;-34.90\n",
        encoding="utf-8",
    )
    rows = parse_ana_fluvio_csv(csv_path, "2611606")
    assert len(rows) == 2
    assert rows[0]["fonte"] == "ana"
    assert rows[0]["data_quality"] == "oficial"
    assert rows[0]["cota_m"] == 3.42
    assert rows[0]["vazao_m3s"] == 185.0
    assert rows[0]["estacao_id"] == "39075000"
    assert rows[0]["granularidade"] == "diaria"
    assert rows[0]["lat"] == -8.05


def test_parse_ana_fluvio_csv_cota_only(tmp_path: Path):
    """Aceita CSV só com cota (sem vazão) — coluna opcional."""
    csv_path = tmp_path / "2611606_sem_vazao.csv"
    csv_path.write_text(
        "estacao;data;cota_m\n39075000;2024-05-27;3.42\n",
        encoding="utf-8",
    )
    rows = parse_ana_fluvio_csv(csv_path, "2611606")
    assert len(rows) == 1
    assert rows[0]["cota_m"] == 3.42
    assert rows[0]["vazao_m3s"] is None


def test_collect_fluvio_series_uses_csv_without_token(tmp_path: Path, monkeypatch):
    """Sem token ANA, mas com CSV depositado, a ingestão funciona (21c.3)."""
    csv_path = tmp_path / "2611606_rio.csv"
    csv_path.write_text(
        "estacao;data;cota_m\n39075000;2024-05-27;3.42\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ANA_HIDROWEB_TOKEN", raising=False)

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    captured: list[dict] = []

    def fake_upsert(_db, rows):
        captured.extend(rows)
        return len(rows)

    monkeypatch.setattr(
        "app.data_connectors.ana_hidroweb_collector.upsert_fluvio_rows",
        fake_upsert,
    )

    result = collect_fluvio_series_for_municipality(db, "2611606", directory=tmp_path)
    assert result["ok"] is True
    assert result["ingested"] == 1
    assert result["metodo"] == "csv_deposit"
    assert len(captured) == 1
    assert captured[0]["cota_m"] == 3.42


def test_collect_fluvio_series_hints_without_csv_or_token(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ANA_HIDROWEB_TOKEN", raising=False)
    db = MagicMock()
    result = collect_fluvio_series_for_municipality(db, "2611606", directory=tmp_path)
    assert result["ok"] is False
    assert result["reason"] == "sem_csv_e_sem_credencial"
    assert "hint" in result


def test_fenomeno_from_tipo_heuristic():
    assert _fenomeno_from_tipo("Inundação") == "fluvial"
    assert _fenomeno_from_tipo("Alagamento Urbano") == "pluvial"
    assert _fenomeno_from_tipo("Enxurrada") == "pluvial"
    assert _fenomeno_from_tipo("Deslizamento de Terra") == "misto"


def test_cota_features_for_dates_without_series_defaults_zero():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    df = pd.DataFrame({"date": [pd.Timestamp("2024-05-27"), pd.Timestamp("2024-05-28")]})
    out = cota_features_for_dates(db, "2611606", df)
    assert (out["cota_rio_disponivel"] == 0.0).all()
    assert (out["cota_rio_anomalia"] == 0.0).all()


def test_cota_features_for_dates_with_series_computes_zscore():
    from types import SimpleNamespace

    db = MagicMock()
    rows = [
        SimpleNamespace(observed_at=dt.datetime(2024, 5, 26), cota_m=2.0),
        SimpleNamespace(observed_at=dt.datetime(2024, 5, 27), cota_m=4.0),
        SimpleNamespace(observed_at=dt.datetime(2024, 5, 28), cota_m=6.0),
    ]
    db.query.return_value.filter.return_value.all.return_value = rows
    df = pd.DataFrame({"date": [pd.Timestamp("2024-05-27"), pd.Timestamp("2024-06-01")]})
    out = cota_features_for_dates(db, "2611606", df)
    assert out.loc[0, "cota_rio_disponivel"] == 1.0
    assert out.loc[1, "cota_rio_disponivel"] == 0.0
    assert out.loc[1, "cota_rio_anomalia"] == 0.0
