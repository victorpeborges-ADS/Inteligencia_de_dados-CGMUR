"""Testes classificação de equipamentos Recife."""

from __future__ import annotations

from app.data_connectors.equipamentos_recife_collector import (
    classify_dependencia,
    classify_tipo,
    load_inventario_equipamentos,
    load_seed_equipamentos,
    merge_equipamentos,
)


def test_classify_dependencia_esferas():
    assert classify_dependencia("UFPE Campus Recife") == "federal"
    assert classify_dependencia("Escola Estadual Dom Bosco") == "estadual"
    assert classify_dependencia("EMEF Paulo Freire") == "municipal"
    assert classify_dependencia("UPA Imbiribeira") == "municipal"
    assert classify_dependencia("Colégio Motiva") == "privada"
    assert classify_dependencia("Real Hospital Português") == "privada"


def test_classify_tipo_equipamentos():
    assert classify_tipo("hospital", "Hospital da Restauração") == "hospital"
    assert classify_tipo("clinic", "UPA Caxangá") == "upa"
    assert classify_tipo("school", "EMEF Centro") == "escola"
    assert classify_tipo("kindergarten", "Creche Municipal Boa Vista") == "creche"
    assert classify_tipo("university", "Universidade Federal de Pernambuco") == "faculdade"
    assert classify_tipo("", "UBS Mustardinha") == "ubs"


def test_seed_recife_has_required_types():
    seed = load_seed_equipamentos()
    assert len(seed) >= 40
    tipos = {r["tipo"] for r in seed}
    for t in ("escola", "creche", "faculdade", "hospital", "upa", "ubs"):
        assert t in tipos
    deps = {r["dependencia"] for r in seed}
    assert deps >= {"federal", "estadual", "municipal", "privada"}


def test_inventario_recife_completo():
    inv = load_inventario_equipamentos()
    assert len(inv) >= 800
    tipos = {r["tipo"] for r in inv}
    for t in ("escola", "creche", "faculdade", "hospital", "upa"):
        assert t in tipos
    deps = {r["dependencia"] for r in inv}
    assert deps >= {"federal", "estadual", "municipal", "privada"}
    assert sum(1 for r in inv if r["tipo"] == "escola") >= 500
    assert sum(1 for r in inv if r["dependencia"] == "municipal") >= 300


def test_merge_prefers_curated_dependencia():
    osm = [{
        "nome": "UPA Imbiribeira",
        "tipo": "upa",
        "dependencia": "privada",
        "lat": -8.11,
        "lng": -34.90,
        "fonte": "osm",
        "osm_id": "n1",
        "data_quality": "derivado",
    }]
    seed = [{
        "nome": "UPA Imbiribeira",
        "tipo": "upa",
        "dependencia": "municipal",
        "lat": -8.11,
        "lng": -34.90,
        "fonte": "seed_curado",
        "osm_id": "SEED:UPA",
        "data_quality": "oficial_curado",
    }]
    merged = merge_equipamentos(osm, seed)
    assert len(merged) == 1
    assert merged[0]["dependencia"] == "municipal"
