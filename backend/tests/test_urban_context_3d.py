"""Testes contexto urbano 3D (17f.6)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.urban_context_3d_service import build_urban_context_geojson


def test_urban_context_empty_muni():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    out = build_urban_context_geojson(db, "2611606")
    assert out["features"] == []
    assert out["meta"]["erro"] == "municipio_nao_encontrado"


def test_urban_context_recife_hydro_fallback_and_vias():
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    muni.nome = "Recife"
    muni.uf = "PE"

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = muni

    via_feat = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[-34.88, -8.1], [-34.9, -8.12]]},
        "properties": {"contexto": "via", "nome": "Av. Teste", "_stroke": "#fff"},
    }

    with (
        patch(
            "app.services.urban_context_3d_service._hidrografia_features",
            return_value=[
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-34.9, -8.05], [-34.88, -8.06]],
                    },
                    "properties": {"contexto": "hidrografia", "nome": "Rio Capibaribe"},
                }
            ],
        ),
        patch(
            "app.services.urban_context_3d_service._vias_features",
            return_value=[via_feat],
        ),
        patch(
            "app.services.urban_context_3d_service._curvas_features",
            return_value=[],
        ),
    ):
        out = build_urban_context_geojson(
            db,
            "2611606",
            include_hidrografia=True,
            include_vias=True,
            include_curvas=True,
        )

    contextos = {f["properties"]["contexto"] for f in out["features"]}
    assert "via" in contextos
    assert "hidrografia" in contextos
    assert out["meta"]["count"] == 2
    assert out["meta"]["por_contexto"]["via"] == 1
    assert out["meta"]["por_contexto"]["hidrografia"] == 1
    assert out["meta"]["por_contexto"]["curva"] == 0


def test_recife_fallback_when_no_mapbiomas_water():
    from app.services.urban_context_3d_service import _hidrografia_features

    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"

    db = MagicMock()
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = []

    feats = _hidrografia_features(db, muni)
    assert len(feats) >= 2
    assert all(f["properties"]["contexto"] == "hidrografia" for f in feats)
