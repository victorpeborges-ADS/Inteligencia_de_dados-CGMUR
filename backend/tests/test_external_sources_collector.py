"""Testes do coletor de fontes externas."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.data_connectors.external_sources_collector import (
    _adapta_indicators,
    _geosgb_indicators,
    _quality_label,
    _sirene_indicators,
    catalog_status_from_quality,
)


def test_catalog_status_from_quality_mapping():
    assert catalog_status_from_quality("referencia_derivada") == "Integrado"
    assert catalog_status_from_quality("estimado") == "Estimado"
    assert catalog_status_from_quality("lacuna") == "Em integracao"
    assert catalog_status_from_quality("ausente") == "Ausente"


def test_catalog_status_oficial():
    assert catalog_status_from_quality("oficial") == "Integrado"


def test_quality_label_bands():
    assert _quality_label(None) == "ausente"
    assert _quality_label(0.8) == "referencia_derivada"
    assert _quality_label(0.4) == "estimado"
    assert _quality_label(0.1) == "lacuna"


def test_adapta_indicators_ausente_sem_dados():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    out = _adapta_indicators(db, None, "2611606")
    assert out["quality"] == "ausente"
    assert out["score"] is None


def test_adapta_indicators_from_stats():
    db = MagicMock()
    stat = MagicMock(vegetacao_pct=40.0, floresta_pct=None)
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [stat]
    out = _adapta_indicators(db, None, "2611606")
    assert out["score"] is not None
    assert out["indicadores"]["vegetacao_pct"] == 40.0


def test_geosgb_indicators_ausente_sem_muni():
    assert _geosgb_indicators(MagicMock(), None)["quality"] == "ausente"


@patch("app.services.analytical_engine.AnalyticalEngine.calculate_flood_risk", return_value=[{"indice_risco_inundacao": 0.4}])
@patch("app.services.analytical_engine.AnalyticalEngine.calculate_climate_vulnerability", return_value=[{"indice_vulnerabilidade": 0.5}])
def test_geosgb_indicators_from_engine(mock_ivc, mock_iri):
    muni = MagicMock(id=1)
    out = _geosgb_indicators(MagicMock(), muni)
    assert out["score"] is not None
    assert out["quality"] in {"referencia_derivada", "estimado", "lacuna"}


def test_brasil_mais_ausente():
    from app.data_connectors.external_sources_collector import _brasil_mais_indicators

    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    out = _brasil_mais_indicators(db, "2611606")
    assert out["quality"] in {"ausente", "lacuna", "estimado"}


def test_sirene_indicators_from_population():
    db = MagicMock()
    ibge = MagicMock(populacao=100_000, area_km2=50.0)
    db.query.return_value.filter.return_value.first.return_value = ibge
    out = _sirene_indicators(db, "2611606", None)
    assert out["score"] is not None
    assert out["emissoes_tco2"] == 180_000.0


@patch("app.data_connectors.external_sources_collector._brasil_mais_indicators")
@patch("app.data_connectors.external_sources_collector._sirene_indicators")
@patch("app.data_connectors.external_sources_collector._geosgb_indicators")
@patch("app.data_connectors.external_sources_collector._adapta_indicators")
def test_collect_and_sync_batch(mock_adapta, mock_geo, mock_sirene, mock_bm):
    from app.data_connectors.external_sources_collector import (
        collect_external_sources,
        sync_external_sources_batch,
    )

    stub = {"score": 0.7, "indicadores": {}, "quality": "estimado", "emissoes_tco2": 1.0}
    mock_adapta.return_value = stub
    mock_geo.return_value = stub
    mock_sirene.return_value = stub
    mock_bm.return_value = stub

    db = MagicMock()
    muni = MagicMock(id=1)
    # first() for Municipio, then None for FonteExterna (create new)
    db.query.return_value.filter.return_value.first.side_effect = [muni, None]
    out = collect_external_sources(db, "2611606")
    assert out["codigo_ibge"] == "2611606"
    assert db.add.called

    db2 = MagicMock()
    with patch(
        "app.data_connectors.external_sources_collector.collect_external_sources",
        return_value=out,
    ) as mock_collect:
        batch = sync_external_sources_batch(db2, codigos=["2611606", "2800308"])
    assert batch["processed"] == 2
    assert batch["errors"] == []
    assert mock_collect.call_count == 2
