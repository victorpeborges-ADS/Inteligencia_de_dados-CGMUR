"""Testes do motor de diagnóstico executivo."""

from app.services.executive_diagnostic_engine import _lacuna_label, _merge_lacunas


def test_lacuna_label_from_string():
    assert _lacuna_label("mapbiomas_oficial") == "mapbiomas_oficial"
    assert _lacuna_label("  ") is None


def test_lacuna_label_from_catalog_dict():
    item = {"id": "s2id", "nome": "S2ID — Desastres", "status": "Ausente"}
    assert _lacuna_label(item) == "S2ID — Desastres"


def test_merge_lacunas_with_dict_gaps_and_seed_strings():
    gaps = [
        {"id": "mapbiomas", "nome": "MapBiomas", "status": "Ausente"},
        {"id": "s2id", "nome": "S2ID", "status": "Em integracao"},
    ]
    seed_lacunas = ["mapbiomas_oficial", "s2id_oficial"]
    merged = _merge_lacunas(gaps, seed_lacunas)
    assert "MapBiomas" in merged
    assert "S2ID" in merged
    assert "mapbiomas_oficial" in merged
    assert len(merged) == len(set(merged))
