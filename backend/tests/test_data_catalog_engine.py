"""Testes do catálogo dinâmico de dados."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.data_catalog_engine import resolve_catalog_status


def test_mapbiomas_ausente_sem_municipio():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.count.return_value = 0
    assert resolve_catalog_status(db, "9999999", "mapbiomas", muni=None, seed=None) == "Ausente"
