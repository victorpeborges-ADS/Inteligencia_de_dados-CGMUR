"""Testes 17b.1 / 17b.2 / 17b.5 — exposição inundação × edifício + população."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from shapely.geometry import box, mapping

from app.services.building_exposure_service import (
    _flood_band_features,
    _worst_band_for_geom,
    allocate_population_by_weight,
    building_population_weight,
    compute_flood_building_exposure,
    enrich_simulation_building_exposure,
)


def _flood_fc():
    poly = box(-34.88, -8.07, -34.86, -8.05)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "layer_type": "flood_band",
                    "depth_band": "critica",
                    "depth_min_m": 0.8,
                    "depth_max_m": 1.4,
                },
                "geometry": mapping(poly),
            }
        ],
    }


def test_flood_band_features_filters_landslide():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"layer_type": "landslide"},
                "geometry": mapping(box(0, 0, 1, 1)),
            },
            {
                "type": "Feature",
                "properties": {"layer_type": "flood_band", "depth_band": "moderada"},
                "geometry": mapping(box(0, 0, 1, 1)),
            },
        ],
    }
    bands = _flood_band_features(fc)
    assert len(bands) == 1
    assert bands[0]["band"] == "moderada"


def test_worst_band_prefers_critica():
    building = box(0.2, 0.2, 0.4, 0.4)
    bands = [
        {"band": "superficial", "geom": box(0, 0, 1, 1), "props": {}},
        {"band": "critica", "geom": box(0, 0, 1, 1), "props": {"depth_min_m": 0.9, "depth_max_m": 1.2}},
    ]
    band, depth = _worst_band_for_geom(building, bands)
    assert band == "critica"
    assert depth == 1.05


def test_allocate_population_by_weight_sums():
    members = [
        {"id": 1, "weight": 1.0},
        {"id": 2, "weight": 3.0},
    ]
    out = allocate_population_by_weight(members, 100)
    assert sum(out.values()) == 100
    assert out[2] > out[1]


def test_building_population_weight_uses_floors():
    g = box(0, 0, 0.001, 0.001)
    w1 = building_population_weight(g, 2, 6.0)
    w2 = building_population_weight(g, 4, 12.0)
    assert w2 == w1 * 2


def test_compute_exposure_no_flood():
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0
    out = compute_flood_building_exposure(db, muni, None, affected_population=100)
    assert out["disponivel"] is False
    assert out["populacao_exposta"] == 100
    assert out["populacao_edificios_estimada"] == 0


def test_compute_exposure_with_building():
    """Cruza footprint com mancha usando mocks de query PostGIS."""
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"

    building = MagicMock()
    building.id = 42
    building.osm_id = "way/1"
    building.nome = "Torre Teste"
    building.uso = "apartments"
    building.altura_m = 24
    building.pavimentos = 8
    building.fonte_altura = "osm_levels"
    building.qualidade = "Estimado"
    building.geom = MagicMock()

    escola = MagicMock()
    escola.nome = "Escola A"
    escola.matriculas_total = 200

    from app.models import Edificacao, EscolaInep, EstabelecimentoSaude, SetorCensitario

    edif_filter = MagicMock()
    edif_filter.count.return_value = 1
    edif_filter.all.return_value = [building]

    esc_filter = MagicMock()
    esc_filter.all.return_value = [escola]

    saude_filter = MagicMock()
    saude_filter.all.return_value = []

    setor_filter = MagicMock()
    setor_filter.all.return_value = []  # força fallback 17b.2

    def query_side(model):
        q = MagicMock()
        if model is Edificacao:
            q.filter.return_value = edif_filter
        elif model is EscolaInep:
            q.filter.return_value = esc_filter
        elif model is EstabelecimentoSaude:
            q.filter.return_value = saude_filter
        elif model is SetorCensitario:
            q.filter.return_value = setor_filter
        return q

    db = MagicMock()
    db.query.side_effect = query_side
    db.scalar.return_value = (
        '{"type":"Polygon","coordinates":[[[-34.875,-8.06],[-34.865,-8.06],'
        '[-34.865,-8.055],[-34.875,-8.055],[-34.875,-8.06]]]}'
    )

    out = compute_flood_building_exposure(
        db, muni, _flood_fc(), affected_population=1500, precipitacao_mm=120
    )
    assert out["disponivel"] is True
    assert out["edificios_expostos"] == 1
    assert out["por_faixa"]["critica"] == 1
    assert out["escolas_expostas"]["n"] == 1
    assert out["escolas_expostas"]["matriculas"] == 200
    assert out["populacao_exposta"] == 1500
    assert out["populacao_edificios_estimada"] == 1500
    assert out["populacao_metodo"] == "cenario_territorial_repartido"
    assert out["amostra"][0]["populacao_estimada"] == 1500
    assert len(out["geojson"]["features"]) == 1


def test_enrich_attaches_keys():
    muni = MagicMock()
    muni.id = 3
    db = MagicMock()
    with patch(
        "app.services.building_exposure_service.compute_flood_building_exposure",
        return_value={
            "disponivel": True,
            "edificios_total": 10,
            "edificios_expostos": 2,
            "por_faixa": {"superficial": 0, "moderada": 1, "critica": 1},
            "populacao_exposta": 50,
            "populacao_edificios_estimada": 40,
            "escolas_expostas": {"n": 0, "matriculas": 0},
            "saude_exposta": {"n": 0, "ubs": 0, "hospital": 0},
            "amostra": [],
            "geojson": {"type": "FeatureCollection", "features": [{"type": "Feature"}]},
        },
    ), patch(
        "app.services.building_exposure_service.compute_landslide_building_exposure",
        return_value={
            "disponivel": False,
            "motivo": "Sem zonas",
            "edificios_total": 10,
            "edificios_expostos": 0,
            "por_faixa": {"moderada": 0, "alta": 0, "critica": 0},
            "populacao_edificios_estimada": 0,
            "amostra": [],
            "geojson": {"type": "FeatureCollection", "features": []},
        },
    ):
        meta = enrich_simulation_building_exposure(
            db, muni, {"dem_available": True}, flood_geometry=_flood_fc(), affected_population=50
        )
    assert meta["exposicao_cenario"]["edificios_expostos"] == 2
    assert meta["exposicao_cenario"]["populacao_edificios_estimada"] == 40
    assert "geojson" not in meta["exposicao_cenario"]
    assert meta["buildings_exposed"]["features"]
    assert "exposicao_deslizamento" in meta


def test_landslide_building_exposure():
    from app.services.building_exposure_service import compute_landslide_building_exposure
    from app.models import Edificacao, SetorCensitario

    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"

    building = MagicMock()
    building.id = 7
    building.osm_id = "way/7"
    building.nome = "Casa Encosta"
    building.uso = "residential"
    building.altura_m = 6
    building.pavimentos = 2
    building.fonte_altura = "heuristic"
    building.qualidade = "Derivado"
    building.geom = MagicMock()

    edif_filter = MagicMock()
    edif_filter.count.return_value = 1
    edif_filter.all.return_value = [building]
    setor_filter = MagicMock()
    setor_filter.all.return_value = []

    def query_side(model):
        q = MagicMock()
        if model is Edificacao:
            q.filter.return_value = edif_filter
        elif model is SetorCensitario:
            q.filter.return_value = setor_filter
        return q

    db = MagicMock()
    db.query.side_effect = query_side
    db.scalar.return_value = (
        '{"type":"Polygon","coordinates":[[[-34.875,-8.06],[-34.865,-8.06],'
        '[-34.865,-8.055],[-34.875,-8.055],[-34.875,-8.06]]]}'
    )

    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "layer_type": "landslide",
                    "slope_threshold_deg": 22.0,
                    "mean_slope_deg": 35.0,
                },
                "geometry": mapping(box(-34.88, -8.07, -34.86, -8.05)),
            }
        ],
    }
    out = compute_landslide_building_exposure(db, muni, fc, affected_population=200, precipitacao_mm=120)
    assert out["disponivel"] is True
    assert out["edificios_expostos"] == 1
    assert out["por_faixa"]["alta"] == 1
    assert out["amostra"][0]["mean_slope_deg"] == 35.0


def test_heat_building_exposure():
    from app.services.building_exposure_service import compute_heat_building_exposure
    from app.models import Edificacao, SetorCensitario

    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"

    building = MagicMock()
    building.id = 9
    building.osm_id = "way/9"
    building.nome = "Torre Quente"
    building.uso = "office"
    building.altura_m = 30
    building.pavimentos = 10
    building.fonte_altura = "osm_levels"
    building.qualidade = "Estimado"
    building.geom = MagicMock()

    edif_filter = MagicMock()
    edif_filter.count.return_value = 1
    edif_filter.all.return_value = [building]
    setor_filter = MagicMock()
    setor_filter.all.return_value = []

    def query_side(model):
        q = MagicMock()
        if model is Edificacao:
            q.filter.return_value = edif_filter
        elif model is SetorCensitario:
            q.filter.return_value = setor_filter
        return q

    db = MagicMock()
    db.query.side_effect = query_side
    db.scalar.return_value = (
        '{"type":"Polygon","coordinates":[[[-34.875,-8.06],[-34.865,-8.06],'
        '[-34.865,-8.055],[-34.875,-8.055],[-34.875,-8.06]]]}'
    )

    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "layer_type": "heat_band",
                    "heat_band": "severa",
                    "temp_increase_celsius": 3.8,
                    "temp_local_celsius": 37.8,
                },
                "geometry": mapping(box(-34.88, -8.07, -34.86, -8.05)),
            }
        ],
    }
    out = compute_heat_building_exposure(db, muni, fc, affected_population=800, temperatura_pico_c=34)
    assert out["disponivel"] is True
    assert out["edificios_expostos"] == 1
    assert out["por_faixa"]["severa"] == 1
    assert out["amostra"][0]["delta_t_c"] == 3.8
    assert out["amostra"][0]["temp_local_c"] == 37.8
