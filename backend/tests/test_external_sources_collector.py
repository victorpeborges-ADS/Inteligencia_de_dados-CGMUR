"""Testes do coletor de fontes externas."""

from __future__ import annotations

from app.data_connectors.external_sources_collector import catalog_status_from_quality


def test_catalog_status_from_quality_mapping():
    assert catalog_status_from_quality("referencia_derivada") == "Integrado"
    assert catalog_status_from_quality("estimado") == "Estimado"
    assert catalog_status_from_quality("lacuna") == "Em integracao"
    assert catalog_status_from_quality("ausente") == "Ausente"


def test_catalog_status_oficial():
    assert catalog_status_from_quality("oficial") == "Integrado"
