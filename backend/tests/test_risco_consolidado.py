"""Testes do mapa de risco consolidado (17h.1c)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.risco_consolidado_service import build_risco_consolidado_geojson


def test_build_risco_consolidado_geojson_merges_alert():
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"

    ranking = [
        {
            "bairro": "Centro",
            "bairro_id": 10,
            "score_sinidu": 70,
            "ivc": 0.7,
            "iri": 0.6,
            "deficit_adaptacao": 0.5,
            "componentes": {"vulnerabilidade_pct": 31.5},
            "fatores_principais": ["renda baixa"],
            "populacao": 1000,
        }
    ]
    geom_row = MagicMock()
    geom_row.id = 10
    geom_row.geojson = '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}'

    db = MagicMock()

    muni_filter = MagicMock()
    muni_filter.first.return_value = muni
    geom_filter = MagicMock()
    geom_filter.all.return_value = [geom_row]

    def query_side_effect(*args, **_kwargs):
        q = MagicMock()
        # Municipio lookup: query(Municipio)
        if len(args) == 1:
            q.filter.return_value = muni_filter
        else:
            q.filter.return_value = geom_filter
        return q

    db.query.side_effect = query_side_effect

    with (
        patch(
            "app.services.risco_consolidado_service.build_bairro_ranking",
            return_value=(ranking, {}),
        ),
        patch(
            "app.services.risco_consolidado_service.live_alert_snapshot",
            return_value={"nivel_alerta": "LARANJA"},
        ),
    ):
        fc = build_risco_consolidado_geojson(db, "2611606")

    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    props = fc["features"][0]["properties"]
    assert props["layer"] == "risco_consolidado"
    assert props["score_sinidu"] == 70
    assert props["nivel_score"] == "VERMELHO"
    assert props["alerta_vivo"] == "LARANJA"
    assert props["nivel"] == "VERMELHO"
    assert fc["meta"]["n_bairros"] == 1


def test_alerta_elevates_low_score_bairro():
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    ranking = [
        {
            "bairro": "Calmo",
            "bairro_id": 11,
            "score_sinidu": 20,
            "ivc": 0.2,
            "iri": 0.1,
            "deficit_adaptacao": 0.1,
            "componentes": {},
            "fatores_principais": [],
            "populacao": 500,
        }
    ]
    geom_row = MagicMock()
    geom_row.id = 11
    geom_row.geojson = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}

    db = MagicMock()
    muni_filter = MagicMock()
    muni_filter.first.return_value = muni
    geom_filter = MagicMock()
    geom_filter.all.return_value = [geom_row]

    def query_side_effect(*args, **_kwargs):
        q = MagicMock()
        q.filter.return_value = muni_filter if len(args) == 1 else geom_filter
        return q

    db.query.side_effect = query_side_effect

    with (
        patch(
            "app.services.risco_consolidado_service.build_bairro_ranking",
            return_value=(ranking, {}),
        ),
        patch(
            "app.services.risco_consolidado_service.live_alert_snapshot",
            return_value={"nivel_alerta": "VERMELHO"},
        ),
    ):
        fc = build_risco_consolidado_geojson(db, "2611606")

    props = fc["features"][0]["properties"]
    assert props["nivel_score"] == "VERDE"
    assert props["nivel"] == "VERMELHO"
