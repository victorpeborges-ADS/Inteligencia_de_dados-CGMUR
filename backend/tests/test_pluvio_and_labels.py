"""Fase 21b/21c — pluvio CSV CEMADEN + rótulos oficiais no ML."""

from pathlib import Path

from app.data_connectors.cemaden_pluvio_collector import parse_cemaden_csv
from ml.features import ML_LABEL_QUALITIES, _event_dates, _is_flood_type


def test_parse_cemaden_csv_basic(tmp_path: Path):
    csv_path = tmp_path / "2611606_demo.csv"
    csv_path.write_text(
        "estacao;nome;latitude;longitude;datahora;valor\n"
        "PE001;Recife Centro;-8.05;-34.88;2024-05-10 12:00:00;12.5\n"
        "PE001;Recife Centro;-8.05;-34.88;2024-05-10 12:10:00;0.2\n",
        encoding="utf-8",
    )
    rows = parse_cemaden_csv(csv_path, "2611606")
    assert len(rows) == 2
    assert rows[0]["fonte"] == "cemaden"
    assert rows[0]["data_quality"] == "oficial"
    assert rows[0]["precip_mm"] == 12.5
    assert rows[0]["estacao_id"] == "PE001"
    assert rows[0]["codigo_ibge"] == "2611606"


def test_is_flood_type_filters_landslide():
    assert _is_flood_type("Inundação")
    assert _is_flood_type("Alagamento Urbano")
    assert _is_flood_type("Enxurrada")
    assert not _is_flood_type("Deslizamento de Terra")


def test_event_dates_ignores_estimado():
    from unittest.mock import MagicMock

    db = MagicMock()
    # observed_flood_dates vazio
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.services.evento_alagamento_service.observed_flood_dates",
        return_value=set(),
    ):
        row_ok = MagicMock(
            data_ocorrencia=__import__("datetime").date(2023, 6, 15),
            tipo_desastre="Inundação",
            data_quality="oficial_curado",
        )
        row_bad = MagicMock(
            data_ocorrencia=__import__("datetime").date(2022, 3, 15),
            tipo_desastre="Inundação",
            data_quality="estimado",
        )
        db.query.return_value.filter.return_value.all.return_value = [row_ok, row_bad]
        dates = _event_dates(db, municipio_id=1, codigo_ibge="2611606")
    assert __import__("datetime").date(2023, 6, 15) in dates
    assert __import__("datetime").date(2022, 3, 15) not in dates


def test_ml_label_qualities():
    assert "oficial_curado" in ML_LABEL_QUALITIES
    assert "estimado" not in ML_LABEL_QUALITIES


def test_json_stations_to_rows_filters_ibge():
    from app.data_connectors.cemaden_pluvio_collector import json_stations_to_rows

    stations = [
        {
            "idestacao": 6536,
            "codibge": 2611606,
            "nomeestacao": "San Martin",
            "ultimovalor": 0,
            "datahoraUltimovalor": "24/07/26 20:10",
            "acc24hr": 12.5,
        },
        {
            "idestacao": 9999,
            "codibge": 2600000,
            "nomeestacao": "Outra",
            "ultimovalor": 1,
            "datahoraUltimovalor": "24/07/26 20:10",
            "acc24hr": 3.0,
        },
    ]
    rows = json_stations_to_rows(stations, "2611606")
    assert len(rows) == 1
    assert rows[0]["estacao_id"] == "6536"
    assert rows[0]["precip_mm"] == 12.5
    assert rows[0]["fonte"] == "cemaden"
    assert rows[0]["data_quality"] == "oficial"


def test_json_stations_falls_back_to_acc48_when_acc24_missing():
    from app.data_connectors.cemaden_pluvio_collector import json_stations_to_rows

    stations = [{
        "idestacao": 6536,
        "codibge": 2611606,
        "nomeestacao": "San Martin",
        "ultimovalor": 0,
        "datahoraUltimovalor": "24/07/26 20:10",
        "acc24hr": "-",
        "acc48hr": 58.28,
    }]
    rows = json_stations_to_rows(stations, "2611606")
    assert len(rows) == 1
    assert rows[0]["precip_mm"] == 58.28
    assert rows[0]["granularidade"] == "snapshot_48h"
