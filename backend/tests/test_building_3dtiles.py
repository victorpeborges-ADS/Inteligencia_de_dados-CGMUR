"""Testes 17c.1 — export 3D Tiles LOD1."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

from shapely.geometry import box, mapping

from app.services.building_3dtiles_service import (
    _extrude_polygon,
    _pack_glb,
    build_3dtiles_for_municipality,
    status_3dtiles,
)


def test_extrude_polygon_has_walls_and_roof():
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)]
    verts, idx = _extrude_polygon(ring, 12.0)
    assert verts.shape[0] == 8  # 4 base + 4 top
    assert idx.size >= 12  # teto+piso+paredes
    assert float(verts[:, 1].max()) == 12.0


def test_pack_glb_magic():
    ring = [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0)]
    verts, idx = _extrude_polygon(ring, 6.0)
    glb = _pack_glb(verts, idx)
    assert glb[:4] == b"glTF"
    version, length = struct.unpack_from("<II", glb, 4)
    assert version == 2
    assert length == len(glb)


def test_build_3dtiles_writes_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.building_3dtiles_service.tiles3d_base_dir",
        lambda: tmp_path,
    )

    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    muni.geom = MagicMock()

    building = MagicMock()
    building.id = 1
    building.altura_m = 18
    building.fonte_altura = "osm_levels"
    building.geom = MagicMock()

    from app.models import Edificacao, Municipio

    edif_filter = MagicMock()
    edif_filter.count.return_value = 1
    edif_filter.limit.return_value.all.return_value = [building]
    # chain: filter().filter().limit().all() OR filter().limit — our code uses .filter(...).limit().all()
    edif_q = MagicMock()
    edif_q.filter.return_value = edif_filter
    # second filter for geom
    edif_filter.limit.return_value = edif_filter
    edif_filter.all.return_value = [building]

    def query_side(model):
        q = MagicMock()
        if model is Municipio:
            q.filter.return_value.first.return_value = muni
        elif model is Edificacao:
            # count path: query.filter.count
            # rows path: query.filter.filter.limit.all — we only have one filter call in code
            fq = MagicMock()
            fq.count.return_value = 1
            fq.limit.return_value.all.return_value = [building]
            # also support filter().filter()
            fq.filter.return_value = fq
            q.filter.return_value = fq
        return q

    db = MagicMock()
    db.query.side_effect = query_side
    db.scalar.side_effect = [
        json.dumps({"type": "Point", "coordinates": [-34.88, -8.06]}),
        json.dumps(mapping(box(-34.881, -8.061, -34.880, -8.060))),
    ]

    out = build_3dtiles_for_municipality(db, "2611606", force=True, ensure_buildings=False, limit=10)
    assert out["disponivel"] is True
    assert out["edificios"] == 1
    assert (tmp_path / "2611606" / "tileset.json").exists()
    assert (tmp_path / "2611606" / "content.glb").exists()
    tileset = json.loads((tmp_path / "2611606" / "tileset.json").read_text())
    assert tileset["asset"]["version"] == "1.0"
    assert tileset["root"]["content"]["uri"] == "content.glb"
    assert "region" in tileset["root"]["boundingVolume"]

    st = status_3dtiles("2611606")
    assert st["disponivel"] is True
    assert "tileset.json" in (st.get("tileset_url") or "")
