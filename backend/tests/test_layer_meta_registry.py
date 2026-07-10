"""Testes do registro de metadados de camadas."""

from app.services.layer_meta_registry import (
    LAYER_DESCRICOES,
    base_layer_entry,
    merge_layers_meta,
)


def test_base_layer_entry_includes_descricao_and_fontes():
    entry = base_layer_entry("socioeconomico")
    assert "renda" in entry["descricao"] or "socioeconômicos" in entry["descricao"]
    assert len(entry["fontes_catalogo"]) >= 1
    assert entry["grupo"] == "Dados urbanos"


def test_merge_layers_meta_preserves_dynamic_overrides():
    dynamic = {
        "bairros": {
            "quality": "Estimado",
            "source": "Voronoi teste",
            "count": 42,
        },
    }
    merged = merge_layers_meta(dynamic)
    assert merged["bairros"]["source"] == "Voronoi teste"
    assert merged["bairros"]["count"] == 42
    assert merged["bairros"]["descricao"] == LAYER_DESCRICOES["bairros"]
    assert "lst_observada" in merged
    assert "GeoReDUS" in merged["lst_observada"]["descricao"]


def test_merge_layers_meta_fills_all_known_layers():
    merged = merge_layers_meta({})
    assert len(merged) == len(LAYER_DESCRICOES)
    for layer_id, desc in LAYER_DESCRICOES.items():
        assert merged[layer_id]["descricao"] == desc
