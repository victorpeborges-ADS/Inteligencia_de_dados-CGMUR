"""Testes do coletor IBGE SINGED Lab RS 2024."""

from app.data_connectors.constants import TARGET_IBGE_CODES, TARGET_MUNICIPALITIES
from app.data_connectors.singedlab_rs_collector import (
    DEFAULT_CSV,
    RS_IBGE_CODES,
    catalog_status_for_row,
    load_csv_rows,
)


def test_seed_csv_covers_all_priority_municipios():
    rows = load_csv_rows(DEFAULT_CSV)
    codes = {row["codigo_ibge"] for row in rows}
    assert len(rows) == 61
    assert codes == set(TARGET_IBGE_CODES)


def test_rs_municipios_in_pilot():
    rs_in_pilot = {m["codigo_ibge"] for m in TARGET_MUNICIPALITIES if m["uf"] == "RS"}
    assert rs_in_pilot == RS_IBGE_CODES
    assert len(RS_IBGE_CODES) == 6


def test_non_rs_rows_marked_nao_aplicavel():
    rows = {r["codigo_ibge"]: r for r in load_csv_rows(DEFAULT_CSV)}
    recife = rows["2611606"]
    assert recife["escopo"] == "nao_aplicavel"
    assert recife["data_quality"] == "nao_aplicavel"


def test_canoas_and_porto_alegre_have_partial_launch_metrics():
    rows = {r["codigo_ibge"]: r for r in load_csv_rows(DEFAULT_CSV)}
    canoas = rows["4304606"]
    poa = rows["4314902"]
    assert canoas["populacao_area_afetada"] == "160677"
    assert canoas["domicilios_area_afetada"] == "69196"
    assert poa["populacao_area_afetada"] == "152258"
    assert poa["domicilios_area_afetada"] == "85123"


class _FakeRow:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_catalog_status_mapping():
    assert catalog_status_for_row(None) == "Ausente"
    assert catalog_status_for_row(_FakeRow(escopo="nao_aplicavel", data_quality="nao_aplicavel")) == "Nao aplicavel"
    assert catalog_status_for_row(_FakeRow(escopo="aplicavel", data_quality="oficial")) == "Integrado"
    assert catalog_status_for_row(
        _FakeRow(escopo="aplicavel", data_quality="parcial_lancamento_ibge", populacao_area_afetada=1)
    ) == "Estimado"
    assert catalog_status_for_row(_FakeRow(escopo="aplicavel", data_quality="pendente_import")) == "Em integracao"
