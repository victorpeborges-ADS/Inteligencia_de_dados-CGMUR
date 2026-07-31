"""Testes 17g.2e (selo) e 17g.2a (validação S2ID)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.simulation_confidence_service import (
    build_confidence_seal,
    enrich_simulation_confidence,
    validate_against_s2id,
)


def test_stamp_simulation_geojson_quality():
    from app.services.simulation_confidence_service import stamp_simulation_geojson_quality

    fc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"layer_type": "flood_band"}, "geometry": None},
            {"type": "Feature", "properties": {"layer_type": "other"}, "geometry": None},
        ],
    }
    stamp_simulation_geojson_quality(fc, qualidade="Estimado")
    assert fc["features"][0]["properties"]["qualidade_dado"] == "Estimado"
    assert "qualidade_dado" not in fc["features"][1]["properties"]
    seal = build_confidence_seal(
        {
            "dem_available": True,
            "dem_source": "LiDAR/DSM local",
            "dem_resolution_m": 5.0,
            "vertical_accuracy_m": 1.5,
            "method": "dem_pluvial_d8_twi",
            "model_version": "2.4",
        }
    )
    assert seal["selo_qualidade"] == "Observado"
    assert seal["nivel_confianca"] == "alta"
    assert seal["vertical_accuracy_m"] == 1.5


def test_seal_srtm_media():
    seal = build_confidence_seal(
        {
            "dem_available": True,
            "dem_source": "SRTM 30m",
            "dem_resolution_m": 30.0,
            "vertical_accuracy_m": 16.0,
            "method": "dem_pluvial_d8_twi",
        }
    )
    assert seal["selo_qualidade"] == "Estimado"
    assert seal["nivel_confianca"] == "baixa"  # resolução > 15 m


def test_seal_heuristic_baixa():
    seal = build_confidence_seal(
        {"dem_available": False, "method": "heuristic"}
    )
    assert seal["selo_qualidade"] == "Derivado"
    assert seal["nivel_confianca"] == "baixa"


def test_validate_s2id_hit_rate():
    muni = MagicMock()
    muni.id = 1

    ev_hit = MagicMock()
    ev_hit.id = 10
    ev_hit.tipo_desastre = "Inundação"
    ev_hit.geom = MagicMock()

    ev_miss = MagicMock()
    ev_miss.id = 11
    ev_miss.tipo_desastre = "Alagamento Urbano"
    ev_miss.geom = MagicMock()

    geojsons = iter(
        [
            '{"type":"Point","coordinates":[0.0,0.0]}',
            '{"type":"Point","coordinates":[10.0,10.0]}',
        ]
    )

    db = MagicMock()

    def scalar_side_effect(_expr):
        return next(geojsons)

    db.scalar.side_effect = scalar_side_effect

    events_q = MagicMock()
    events_q.filter.return_value.all.return_value = [ev_hit, ev_miss]
    bairros_q = MagicMock()
    bairros_q.filter.return_value.all.return_value = []

    def query_side_effect(model):
        name = getattr(model, "__name__", str(model))
        if "Bairro" in name:
            return bairros_q
        return events_q

    db.query.side_effect = query_side_effect

    flood_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"layer_type": "flood_band"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-0.01, -0.01], [0.01, -0.01], [0.01, 0.01], [-0.01, 0.01], [-0.01, -0.01]]
                    ],
                },
            }
        ],
    }

    result = validate_against_s2id(db, muni, flood_geometry=flood_fc, affected_bairros=["Centro"])
    assert result["eventos_com_geometria"] == 2
    assert result["eventos_na_mancha"] == 1
    assert result["hit_rate"] == 0.5
    assert result["acordo"] == "media"
    assert result["qualidade"] == "Oficial"


def test_enrich_attaches_both():
    muni = MagicMock()
    muni.id = 7
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    with patch(
        "app.services.simulation_confidence_service.validate_against_s2id",
        return_value={
            "disponivel": True,
            "acordo": "alta",
            "hit_rate": 0.8,
            "narrativa": "ok",
            "fonte": "S2ID",
            "qualidade": "Oficial",
            "eventos_inundacao_total": 5,
            "eventos_com_geometria": 4,
            "eventos_na_mancha": 3,
            "bairros_historicos": [],
            "bairros_simulados": [],
            "bairros_em_comum": [],
            "jaccard_bairros": None,
            "limitacao": "",
        },
    ):
        meta = enrich_simulation_confidence(
            db,
            muni,
            {
                "dem_available": True,
                "dem_source": "LiDAR/DSM local",
                "dem_resolution_m": 4.0,
                "vertical_accuracy_m": 1.0,
                "method": "dem_pluvial_d8_twi",
            },
            flood_geometry=None,
            affected_bairros=[],
        )
    assert meta["selo_confianca"]["selo_qualidade"] == "Observado"
    assert meta["validacao_s2id"]["acordo"] == "alta"
