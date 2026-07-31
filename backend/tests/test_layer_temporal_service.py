"""Testes do serviço temporal de camadas."""

from unittest.mock import MagicMock

from app.services.layer_temporal_service import (
    build_tema_entry,
    temporal_options_for_municipio,
)


def test_build_tema_entry_defaults():
    entry = build_tema_entry("mapbiomas", [2023, 2022, 2021])
    assert entry["padrao"] == 2023
    assert entry["layer_id"] == "cobertura"


def test_temporal_options_structure():
    muni = MagicMock(codigo_ibge="2611606", id=1)
    db = MagicMock()
    db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = None

    payload = temporal_options_for_municipio(db, muni)
    assert payload["codigo_ibge"] == "2611606"
    assert set(payload["temas"]) == {"mapbiomas", "s2id", "inep", "lst", "pib"}
    assert payload["temas"]["lst"]["anos"] == [2025, 2024, 2023, 2022, 2021]
    assert payload["temas"]["s2id"]["padrao"] is None
    assert payload["temas"]["pib"]["context_only"] is True
