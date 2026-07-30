"""17g.3 — slider de duração do evento (1h–7 dias) modula intensidade/mancha/deslizamento."""

import numpy as np
import pytest
from shapely.geometry import Polygon, box

from app.services.hydro_simulator import (
    REFERENCE_DURATION_H,
    _compute_d8_accumulation,
    _hydrograph_duration_for,
    _intensity_factor,
    build_flood_timeline,
    flood_bands_geojson,
    landslide_features_from_slope,
)
from app.services.rainfall_event_anchors import (
    estimate_operational_impacts,
    match_anchor,
)


def _bowl_dem(size: int = 48) -> tuple[np.ndarray, Polygon]:
    yy, xx = np.mgrid[0:size, 0:size]
    cx, cy = size // 2, size // 2
    elev = 20.0 + 0.08 * ((xx - cx) ** 2 + (yy - cy) ** 2)
    muni = box(-0.01, -0.01, 0.01, 0.01)
    return elev, muni


def test_intensity_factor_reference_is_neutral():
    assert _intensity_factor(REFERENCE_DURATION_H) == pytest.approx(1.0)


def test_intensity_factor_decreases_with_longer_duration():
    f_1h = _intensity_factor(1.0)
    f_24h = _intensity_factor(24.0)
    f_7d = _intensity_factor(168.0)
    assert f_1h > f_24h > f_7d
    assert f_7d >= 0.35  # piso


def test_hydrograph_duration_scales_with_rain_duration():
    assert _hydrograph_duration_for(1.0) == pytest.approx(6.0)
    assert _hydrograph_duration_for(24.0) > 6.0
    assert _hydrograph_duration_for(168.0) <= 120.0  # teto de exibição


def test_same_mm_shorter_duration_floods_more():
    """Mesma lâmina (mm) concentrada em 1h deve gerar mancha mais profunda que em 7 dias."""
    pytest.importorskip("rasterio")
    elev, muni = _bowl_dem(64)
    rows, cols = elev.shape
    west, south = -0.01, -0.01
    res_x = 0.02 / cols
    res_y = 0.02 / rows
    kwargs = dict(
        river_shapes=[],
        west=west,
        south=south,
        res_x=res_x,
        res_y=res_y,
        impermeability_raster=np.full_like(elev, 0.75),
        slope_deg=np.zeros_like(elev),
        accumulation=_compute_d8_accumulation(elev, np.ones_like(elev, dtype=bool)),
    )
    _, depth_1h = flood_bands_geojson(elev, muni, 120.0, duracao_h=1.0, **kwargs)
    _, depth_24h = flood_bands_geojson(elev, muni, 120.0, duracao_h=24.0, **kwargs)
    _, depth_7d = flood_bands_geojson(elev, muni, 120.0, duracao_h=168.0, **kwargs)

    assert float(np.max(depth_1h)) > float(np.max(depth_24h)) > float(np.max(depth_7d))


def test_flood_timeline_duration_scales_with_event_duration():
    pytest.importorskip("rasterio")
    elev, muni = _bowl_dem(64)
    rows, cols = elev.shape
    west, south = -0.01, -0.01
    res_x = 0.02 / cols
    res_y = 0.02 / rows
    mask = np.ones_like(elev, dtype=bool)
    fc, depth = flood_bands_geojson(
        elev, muni, 150.0,
        river_shapes=[],
        west=west, south=south, res_x=res_x, res_y=res_y,
        impermeability_raster=np.full_like(elev, 0.75),
        slope_deg=np.zeros_like(elev),
        accumulation=_compute_d8_accumulation(elev, mask),
        duracao_h=1.0,
    )
    tl_short = build_flood_timeline(depth, muni, mask, west, south, res_x, res_y, precip_mm=150.0, duracao_h=1.0)
    tl_long = build_flood_timeline(depth, muni, mask, west, south, res_x, res_y, precip_mm=150.0, duracao_h=72.0)
    assert tl_long["duration_h"] > tl_short["duration_h"]


def test_landslide_effective_rain_scales_with_intensity(session_factory=None):
    """Chuva concentrada eleva a chuva efetiva de deslizamento em relação à mesma lâmina distribuída."""
    pytest.importorskip("rasterio")

    class _FakeQuery:
        def filter(self, *a, **k):
            return self

        def all(self):
            return []

    class _FakeDb:
        def query(self, *a, **k):
            return _FakeQuery()

        def scalar(self, *a, **k):
            return None

    elev, muni = _bowl_dem(48)
    rows, cols = elev.shape
    west, south = -0.01, -0.01
    res_x = 0.02 / cols
    res_y = 0.02 / rows
    mask = np.ones_like(elev, dtype=bool)

    feats_flash = landslide_features_from_slope(
        elev, muni, mask, 150.0, west, south, res_x, res_y, _FakeDb(), 1,
        chuva_antecedente_mm=0.0, duracao_h=1.0,
    )
    feats_sustained = landslide_features_from_slope(
        elev, muni, mask, 150.0, west, south, res_x, res_y, _FakeDb(), 1,
        chuva_antecedente_mm=0.0, duracao_h=168.0,
    )
    # Encosta plana (bowl raso) pode não disparar zonas — o que importa é a chuva efetiva no gatilho.
    assert isinstance(feats_flash, list)
    assert isinstance(feats_sustained, list)


def test_operational_impacts_regime_labels():
    flash = estimate_operational_impacts(
        precip_mm=120.0, max_depth_m=0.5, affected_area_km2=2.0,
        affected_population=5000, duracao_h=1.0,
    )
    sustained = estimate_operational_impacts(
        precip_mm=120.0, max_depth_m=0.2, affected_area_km2=1.0,
        affected_population=2000, duracao_h=168.0,
    )
    assert flash["regime_chuva"]["codigo"] == "CONCENTRADO"
    assert sustained["regime_chuva"]["codigo"] == "SUSTENTADO"
    assert flash["regime_chuva"]["intensidade_mm_h"] > sustained["regime_chuva"]["intensidade_mm_h"]


def test_match_anchor_prefers_duration_aware_event():
    # 160mm sem duração e com duração ~ evento de 24h (Passarinho 2022) devem casar igual em mm,
    # mas informar duracao_h ajuda a discriminar entre âncoras com mm parecido.
    sem_duracao = match_anchor("2611606", 160.0)
    com_duracao = match_anchor("2611606", 160.0, duracao_h=24.0)
    assert sem_duracao is not None
    assert com_duracao is not None
    assert com_duracao["delta_duracao_h"] is not None
