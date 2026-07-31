"""Testes do catálogo ativo — Step 5."""

from app.services.catalog_impact_service import rank_lacunas, _deterministic_explanation
from app.services.catalog_source_registry import FONTE_REGISTRY


def test_rank_lacunas_by_impact():
    bases = [
        {"id": "geosgb", "nome": "GeoSGB / CPRM", "status": "Ausente"},
        {"id": "sirene", "nome": "SIRENE / MCTI", "status": "Ausente"},
        {"id": "mapbiomas", "nome": "MapBiomas", "status": "Integrado"},
    ]
    ranked = rank_lacunas(bases)
    assert len(ranked) == 2
    assert ranked[0]["id"] == "geosgb"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["impacto_estimado"] >= ranked[1]["impacto_estimado"]


def test_deterministic_explanation_geosgb():
    meta = FONTE_REGISTRY["geosgb"]
    text = _deterministic_explanation("geosgb", meta, "Ausente")
    assert "GeoSGB" in text
    assert "±8" in text
    assert "Convênio" in text


def test_fonte_registry_has_all_catalog_ids():
    expected = {
        "ibge_cidades", "snis_sinisa", "s2id", "mapbiomas", "cemaden_georiscos",
        "adapta_brasil", "geosgb", "sinter", "munic", "sirene", "inde", "brasil_mais",
        "ibge_singedlab_rs", "inep_censo_escolar", "incra_quilombos", "funai_ti",
        "ibge_aglomerados", "gemeo_digital_3d",
    }
    assert expected == set(FONTE_REGISTRY.keys())
