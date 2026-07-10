"""Testes do coletor INEP Censo Escolar."""

from unittest.mock import MagicMock

from app.data_connectors.inep_educacao_collector import (
    fetch_school_rows,
    load_seed_rows,
    matriculas_por_etapa,
    upsert_escolas,
)


def test_load_seed_rows_recife():
    rows = load_seed_rows("2611606")
    assert len(rows) >= 10
    assert all(r["codigo_ibge"] == "2611606" for r in rows)
    assert rows[0]["matriculas_total"] > 0


def test_matriculas_por_etapa():
    escola = MagicMock(
        matriculas_total=100,
        matriculas_infantil=20,
        matriculas_fundamental=60,
        matriculas_medio=20,
    )
    assert matriculas_por_etapa(escola, "infantil") == 20
    assert matriculas_por_etapa(escola, "fundamental") == 60
    assert matriculas_por_etapa(escola, "todas") == 100


def test_upsert_escolas_creates_records():
    muni = MagicMock(id=1, codigo_ibge="2611606")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    rows = fetch_school_rows("2611606")[:3]
    updated = upsert_escolas(db, muni, rows)
    assert updated == 3
    assert db.add.call_count == 3
