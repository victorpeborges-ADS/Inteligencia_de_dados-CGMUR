"""Testes Ipeadata IDHM e Atlas Econômico UF."""

from app.data_connectors.constants import TARGET_IBGE_CODES
from app.data_connectors.ipeadata_collector import DEFAULT_IDHM_CSV, collect_idhm_municipality, load_idhm_csv
from app.services.atlas_economico_service import ATLAS_ACTIVITIES, build_atlas_uf_context


def test_idhm_csv_covers_priority_municipios():
    rows = load_idhm_csv(DEFAULT_IDHM_CSV)
    assert len(rows) == 61
    assert set(rows) == set(TARGET_IBGE_CODES)


def test_recife_idhm_from_seed():
    payload = collect_idhm_municipality("2611606")
    assert payload["idh"] == 0.772
    assert payload["idh_ano"] == 2010
    assert payload["idh_qualidade"] == "oficial"


def test_atlas_uf_context_pe():
    ctx = build_atlas_uf_context("PE", codigo_ibge="2611606")
    assert ctx["uf_sigla"] == "PE"
    assert ctx["uf_nome"] == "Pernambuco"
    assert ctx["atividades_economicas"] == ATLAS_ACTIVITIES
    assert ctx["escopo"] == "estadual"
    assert "ipea.gov.br/atlaseconomico" in ctx["portal_url"]
    assert len(ctx["kpis"]) == 3
