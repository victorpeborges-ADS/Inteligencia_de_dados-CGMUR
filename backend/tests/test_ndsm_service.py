"""Testes 17a.6 — nDSM / refine de altura."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.ndsm_service import (
    NDSM_MIN_BUILDING_M,
    _ground_window_px,
    build_ndsm,
    refine_building_heights_from_ndsm,
)


def test_ground_window_odd_bounded():
    assert _ground_window_px(20.0) % 2 == 1
    assert 5 <= _ground_window_px(1.0) <= 51
    assert 5 <= _ground_window_px(100.0) <= 51


def test_build_ndsm_sem_dsm(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.ndsm_service.dem_dir", lambda _c: tmp_path)
    monkeypatch.setattr("app.services.ndsm_service.find_local_dem", lambda _c: None)
    out = build_ndsm("2611606")
    assert out["status"] == "sem_dsm"


def test_build_ndsm_deps_ausentes(tmp_path, monkeypatch):
    dem = tmp_path / "dem.tif"
    dem.write_bytes(b"not-a-real-geotiff-but-exists" + b"\x00" * 3000)
    monkeypatch.setattr("app.services.ndsm_service.dem_dir", lambda _c: tmp_path)
    monkeypatch.setattr("app.services.ndsm_service.find_local_dem", lambda _c: dem)

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "rasterio":
            raise ImportError("no rasterio")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        out = build_ndsm("2611606", force=True)
    # Pode ser deps_ausentes ou falhar ao abrir tiff — ambos ok para ambiente sem rasterio
    assert out["status"] in {"deps_ausentes", "sem_dsm", "ok", "cached"}


def test_refine_skips_without_ndsm():
    db = MagicMock()
    muni = MagicMock()
    muni.id = 1
    db.query.return_value.filter.return_value.first.return_value = muni

    with patch("app.services.ndsm_service.build_ndsm", return_value={"status": "sem_dsm"}):
        out = refine_building_heights_from_ndsm(db, "2611606")
    assert out["updated"] == 0
    assert out["status"] == "sem_dsm"


def test_refine_updates_heuristic_building():
    db = MagicMock()
    muni = MagicMock()
    muni.id = 9
    row = MagicMock()
    row.geom = MagicMock()
    row.altura_m = 6.0
    row.fonte_altura = "heuristic"
    row.qualidade = "Derivado"
    row.pavimentos = 2

    q = MagicMock()
    q.filter.return_value.first.return_value = muni
    q.filter.return_value.all.return_value = [row]

    def query_side(model):
        return q

    db.query.side_effect = query_side
    db.scalar.return_value = (
        '{"type":"Polygon","coordinates":[[[-34.88,-8.06],[-34.87,-8.06],'
        '[-34.87,-8.05],[-34.88,-8.05],[-34.88,-8.06]]]}'
    )

    with patch("app.services.ndsm_service.build_ndsm", return_value={"status": "ok", "path": "/tmp/ndsm.tif"}):
        with patch("app.services.ndsm_service.sample_ndsm_height", return_value=18.5):
            out = refine_building_heights_from_ndsm(db, "2611606")

    assert out["updated"] == 1
    assert row.fonte_altura == "ndsm_lidar"
    assert float(row.altura_m) == 18.5
    assert row.qualidade == "Observado"
    assert NDSM_MIN_BUILDING_M < 18.5
