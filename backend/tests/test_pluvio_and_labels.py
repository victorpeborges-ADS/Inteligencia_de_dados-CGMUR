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


def test_parse_inmet_bdmep_csv_basic(tmp_path: Path):
    from app.data_connectors.inmet_bdmep_collector import parse_inmet_bdmep_csv

    csv_path = tmp_path / "2611606_bdmep.csv"
    csv_path.write_text(
        "CD_ESTACAO;DC_NOME;DT_MEDICAO;CHUVA;VL_LATITUDE;VL_LONGITUDE\n"
        "A301;RECIFE;2022-05-27;145.2;-8.05;-34.95\n"
        "A301;RECIFE;2022-05-28;12.0;-8.05;-34.95\n",
        encoding="utf-8",
    )
    rows = parse_inmet_bdmep_csv(csv_path, "2611606")
    assert len(rows) == 2
    assert rows[0]["fonte"] == "inmet"
    assert rows[0]["data_quality"] == "oficial"
    assert rows[0]["precip_mm"] == 145.2
    assert rows[0]["estacao_id"] == "A301"
    assert rows[0]["granularidade"] == "diaria"
    assert rows[0]["lat"] == -8.05


def test_merge_grib_url_and_row_builder():
    import datetime as dt

    from app.data_connectors.merge_cptec_collector import build_merge_row, merge_grib_url

    url = merge_grib_url(dt.date(2024, 5, 27))
    assert url.endswith("/2024/05/MERGE_CPTEC_20240527.grib2")
    assert "MERGE/GPM/DAILY" in url

    row = build_merge_row(
        codigo_ibge="2611606",
        municipio_id=1,
        day=dt.date(2024, 5, 27),
        lat=-8.05,
        lng=-34.88,
        precip_mm=2.375,
        nest=2.0,
        arquivo="MERGE_CPTEC_20240527.grib2",
    )
    assert row["fonte"] == "merge"
    assert row["data_quality"] == "reanalise"
    assert row["granularidade"] == "diaria"
    assert row["estacao_id"] == "merge:2611606"
    assert row["precip_mm"] == 2.375
    assert row["raw_payload"]["nest"] == 2.0


def test_sample_precip_mm_from_grib(tmp_path: Path):
    """Se houver GRIB de fixture no host/cache, valida amostragem Recife."""
    import shutil

    from app.data_connectors.merge_cptec_collector import sample_precip_mm

    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / "scripts/merge_cptec/downloads/MERGE_CPTEC_20240527.grib2",
        Path("/data/merge_cptec/MERGE_CPTEC_20240527.grib2"),
    ]
    src = next((p for p in candidates if p.exists() and p.stat().st_size > 0), None)
    if src is None:
        import pytest

        pytest.skip("GRIB MERGE de fixture ausente")
    dest = tmp_path / src.name
    shutil.copy(src, dest)
    precip, nest = sample_precip_mm(dest, -34.88, -8.05)
    assert precip is not None and precip >= 0
    assert nest is not None and nest >= 0


def test_materialize_cemaden_daily_from_snapshots():
    """Último snapshot_24h do dia civil vira linha diaria por estação."""
    import datetime as dt
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from app.services.pluvio_series_service import materialize_cemaden_daily_from_snapshots

    day = dt.date(2026, 7, 28)
    early = SimpleNamespace(
        codigo_ibge="2611606",
        municipio_id=1,
        estacao_id="9035",
        estacao_nome="RECIFE - APAC",
        lat=None,
        lng=None,
        observed_at=dt.datetime(2026, 7, 28, 8, 0),
        precip_mm=3.0,
        granularidade="snapshot_24h",
        fonte="cemaden",
    )
    late = SimpleNamespace(
        codigo_ibge="2611606",
        municipio_id=1,
        estacao_id="9035",
        estacao_nome="RECIFE - APAC",
        lat=None,
        lng=None,
        observed_at=dt.datetime(2026, 7, 28, 20, 30),
        precip_mm=12.5,
        granularidade="snapshot_24h",
        fonte="cemaden",
    )
    other = SimpleNamespace(
        codigo_ibge="2611606",
        municipio_id=1,
        estacao_id="9999",
        estacao_nome="Outra",
        lat=None,
        lng=None,
        observed_at=dt.datetime(2026, 7, 27, 18, 0),
        precip_mm=1.0,
        granularidade="snapshot_24h",
        fonte="cemaden",
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        early,
        late,
        other,
    ]
    captured: list[dict] = []

    def fake_upsert(_db, rows):
        captured.extend(rows)
        return len(rows)

    with patch(
        "app.services.pluvio_series_service.upsert_pluvio_rows",
        side_effect=fake_upsert,
    ):
        n = materialize_cemaden_daily_from_snapshots(db, "2611606")

    assert n == 2
    assert len(captured) == 2
    by_est = {r["estacao_id"]: r for r in captured}
    assert by_est["9035"]["precip_mm"] == 12.5
    assert by_est["9035"]["observed_at"] == dt.datetime.combine(day, dt.time(0, 0))
    assert by_est["9035"]["granularidade"] == "diaria"
    assert by_est["9035"]["data_quality"] == "oficial"
    assert by_est["9035"]["raw_payload"]["origem"] == "snapshot_24h_materializado"
    assert by_est["9999"]["precip_mm"] == 1.0
