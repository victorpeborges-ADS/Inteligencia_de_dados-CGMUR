"""Testes LOD2-lite (18b.1) — mesh de telhado sem DB/rasterio obrigatórios."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from app.services.building_lod2_mesh_service import (
    LOD2_VERSION,
    _lod2_mesh_from_samples,
    lod2_dir,
    status_lod2,
)


def test_lod2_mesh_creates_peak_above_eaves():
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)]
    samples = [
        (0.0, 0.0, 4.0),
        (10.0, 0.0, 4.2),
        (10.0, 8.0, 4.1),
        (0.0, 8.0, 4.0),
        (5.0, 4.0, 7.5),  # pico
    ]
    verts, idx = _lod2_mesh_from_samples(ring, samples, fallback_h=6.0)
    assert verts.shape[0] == 9  # 4 bottom + 4 eaves + peak
    assert idx.size >= 18
    assert float(verts[:, 1].max()) >= 7.0


def test_lod2_mesh_falls_back_to_extrusion_when_flat():
    ring = [(0.0, 0.0), (6.0, 0.0), (6.0, 6.0), (0.0, 6.0)]
    samples = [(x, y, 5.0) for x, y in [(0, 0), (6, 0), (6, 6), (0, 6), (3, 3)]]
    verts, idx = _lod2_mesh_from_samples(ring, samples, fallback_h=5.0)
    # LOD1 extrusion: 8 verts
    assert verts.shape[0] == 8
    assert float(verts[:, 1].max()) >= 5.0


def test_lod2_mesh_empty_ring():
    verts, idx = _lod2_mesh_from_samples([], [], 6.0)
    assert verts.size == 0
    assert idx.size == 0


def test_status_lod2_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.building_lod2_mesh_service.tiles3d_muni_dir",
        lambda code: tmp_path / code,
    )
    st = status_lod2("2611606")
    assert st["disponivel"] is False
    assert st["codigo_ibge"] == "2611606"


def test_status_lod2_available(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.building_lod2_mesh_service.tiles3d_muni_dir",
        lambda code: tmp_path / code,
    )
    d = lod2_dir("2611606")
    (d / "tileset.json").write_text('{"asset":{"version":"1.0"}}', encoding="utf-8")
    (d / "content.glb").write_bytes(b"glTF" + b"\x00" * 8)
    (d / "meta.json").write_text(
        json.dumps({"versao": LOD2_VERSION, "edificios": 3}),
        encoding="utf-8",
    )
    st = status_lod2("2611606")
    assert st["disponivel"] is True
    assert st["content_url"].endswith("/lod2/content.glb")
    assert st["meta"]["edificios"] == 3


def test_pack_glb_magic_from_lod2_mesh():
    from app.services.building_3dtiles_service import _pack_glb

    ring = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
    samples = [(2.0, 2.0, 8.0), (0.0, 0.0, 3.0), (4.0, 0.0, 3.2), (4.0, 4.0, 3.1), (0.0, 4.0, 3.0)]
    verts, idx = _lod2_mesh_from_samples(ring, samples, 6.0)
    glb = _pack_glb(verts, idx)
    assert glb[:4] == b"glTF"
    assert len(glb) > 100


@patch("app.services.building_lod2_mesh_service._open_ndsm_sampler")
def test_build_lod2_empty_bbox(mock_ndsm, tmp_path, monkeypatch):
    from app.services import building_lod2_mesh_service as svc

    monkeypatch.setattr(svc, "tiles3d_muni_dir", lambda code: tmp_path / code)
    mock_ndsm.return_value = (None, {"status": "sem_ndsm"})

    muni = MagicMock(id=1, codigo_ibge="2611606", geom=None)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = muni
    db.query.return_value.filter.return_value.count.return_value = 0
    db.execute.return_value.fetchall.return_value = []

    out = svc.build_lod2_for_bbox(
        db,
        "2611606",
        west=-34.878,
        south=-8.068,
        east=-34.868,
        north=-8.058,
        force=True,
        ensure_buildings=False,
    )
    assert out["status"] == "vazio"
    assert (tmp_path / "2611606" / "lod2" / "tileset.json").exists()
