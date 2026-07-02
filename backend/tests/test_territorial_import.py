"""Testes de importação CTM GeoJSON."""

from shapely.geometry import mapping, box

from app.data_connectors.territorial_mesh_collector import _feature_bairro_name


def test_feature_bairro_name_variants():
    assert _feature_bairro_name({"nome": "Boa Viagem"}) == "Boa Viagem"
    assert _feature_bairro_name({"NM_BAIRRO": "Centro"}) == "Centro"
    assert _feature_bairro_name({"other": "x"}) is None


def test_recife_seed_count_near_ctm():
    from app.data_connectors.territorial_mesh_collector import RECIFE_BAIRRO_SEEDS

    assert len(RECIFE_BAIRRO_SEEDS) >= 90
