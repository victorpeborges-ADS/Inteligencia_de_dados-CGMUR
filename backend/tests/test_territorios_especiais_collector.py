"""Testes do coletor de territórios especiais."""

from unittest.mock import MagicMock

from app.data_connectors.territorios_especiais_collector import (
    fetch_territory_rows,
    load_seed_rows,
    normalize_tipo,
    territorio_matches_tipo,
    tipo_label,
    upsert_territorios,
)


def test_load_seed_rows_recife():
    rows = load_seed_rows("2611606")
    assert len(rows) >= 8
    tipos = {r["tipo"] for r in rows}
    assert "comunidade_urbana" in tipos


def test_normalize_tipo_aliases():
    assert normalize_tipo("favela") == "comunidade_urbana"
    assert normalize_tipo("ti") == "terra_indigena"


def test_territorio_matches_tipo():
    record = MagicMock(tipo="quilombo")
    assert territorio_matches_tipo(record, "todas")
    assert territorio_matches_tipo(record, "quilombo")
    assert not territorio_matches_tipo(record, "comunidade_urbana")


def test_tipo_label():
    assert tipo_label("terra_indigena") == "Terra indígena"


def test_upsert_territorios():
    muni = MagicMock(id=1, codigo_ibge="2611606")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    rows = fetch_territory_rows("2611606")[:2]
    updated = upsert_territorios(db, muni, rows)
    assert updated == 2
    assert db.add.call_count == 2
