"""Testes do registry e inventário CTM."""

from app.data_connectors.ctm_registry import (
    CTM_BY_CODE,
    CTM_TARGET_CODES,
    ctm_registry_stats,
)


def test_ctm_registry_stats_counts():
    stats = ctm_registry_stats()
    assert stats["total_alvo"] == len(CTM_TARGET_CODES) == 24
    assert stats["fontes_cadastradas"] == len([c for c in CTM_TARGET_CODES if c in CTM_BY_CODE])
    assert stats["sem_fonte"] == stats["total_alvo"] - stats["fontes_cadastradas"]
    assert stats["fontes_cadastradas"] == 24
    assert stats["sem_fonte"] == 0
    assert stats["por_kind"]["ibge_setores_individuais"] == 7
    assert stats["por_kind"]["geojson_file"] == 1
    assert stats["por_kind"]["geoserver_wfs"] >= 2
