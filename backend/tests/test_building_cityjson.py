"""Testes 17c.2 — export CityJSON / CityGML LOD1."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from shapely.geometry import box, mapping

from app.services.building_cityjson_service import (
    _extrude_solid_boundaries,
    build_citymodel_for_municipality,
    status_citymodel,
)


def test_extrude_solid_boundaries_shell():
    vertices: list[list[int]] = []
    translate = (-34.88, -8.06, 0.0)
    ring = [(-34.881, -8.061), (-34.880, -8.061), (-34.880, -8.060), (-34.881, -8.060)]
    surfaces = _extrude_solid_boundaries(ring, 12.0, translate, vertices)
    assert surfaces is not None
    # ground + roof + 4 walls
    assert len(surfaces) == 6
    assert len(vertices) == 8  # 4 base + 4 top


def test_build_cityjson_and_citygml(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.building_cityjson_service.citymodel_base_dir",
        lambda: tmp_path,
    )

    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    muni.nome = "Recife"
    muni.geom = MagicMock()

    building = MagicMock()
    building.id = 42
    building.altura_m = 15
    building.pavimentos = 5
    building.fonte_altura = "osm_levels"
    building.qualidade = "Estimado"
    building.osm_id = "way/42"
    building.uso = "apartments"
    building.nome = "Torre Teste"
    building.geom = MagicMock()

    from app.models import Edificacao, Municipio

    def query_side(model):
        q = MagicMock()
        if model is Municipio:
            q.filter.return_value.first.return_value = muni
        elif model is Edificacao:
            fq = MagicMock()
            fq.count.return_value = 1
            fq.limit.return_value.all.return_value = [building]
            fq.filter.return_value = fq
            q.filter.return_value = fq
        return q

    db = MagicMock()
    db.query.side_effect = query_side
    db.scalar.side_effect = [
        json.dumps({"type": "Point", "coordinates": [-34.88, -8.06]}),
        json.dumps(mapping(box(-34.881, -8.061, -34.880, -8.060))),
    ]

    out = build_citymodel_for_municipality(
        db, "2611606", force=True, ensure_buildings=False, limit=10
    )
    assert out["disponivel"] is True
    assert out["edificios"] == 1

    cj_path = tmp_path / "2611606" / "model.city.json"
    gml_path = tmp_path / "2611606" / "model.gml"
    assert cj_path.exists()
    assert gml_path.exists()

    doc = json.loads(cj_path.read_text(encoding="utf-8"))
    assert doc["type"] == "CityJSON"
    assert doc["version"] == "2.0"
    assert "transform" in doc
    assert "B_42" in doc["CityObjects"]
    assert doc["CityObjects"]["B_42"]["type"] == "Building"
    geom = doc["CityObjects"]["B_42"]["geometry"][0]
    assert geom["type"] == "Solid"
    assert geom["lod"] == "1"
    assert len(doc["vertices"]) >= 8

    gml = gml_path.read_text(encoding="utf-8")
    assert "Building" in gml
    assert "lod1Solid" in gml
    assert "Torre Teste" in gml

    st = status_citymodel("2611606")
    assert st["disponivel"] is True
    assert "model.city.json" in (st.get("cityjson_url") or "")
