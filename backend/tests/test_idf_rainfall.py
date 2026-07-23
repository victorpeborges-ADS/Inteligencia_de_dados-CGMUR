"""Testes IDF / período de retorno (17g.1a)."""

from app.services.idf_rainfall_service import idf_curve_catalog, resolve_idf_precipitacao


def test_resolve_recife_tr100_60min():
    r = resolve_idf_precipitacao("2611606", 100, duracao_min=60)
    assert r["periodo_retorno_anos"] == 100
    assert r["duracao_min"] == 60
    assert r["precipitacao_mm"] == 145.0
    assert r["intensidade_mm_h"] == 145.0
    assert r["escopo"] == "municipio"
    assert "piloto" in r["fonte"]


def test_tr_monotonic_with_return_period():
    mm = [
        resolve_idf_precipitacao("2611606", tr, duracao_min=60)["precipitacao_mm"]
        for tr in (2, 10, 25, 100)
    ]
    assert mm == sorted(mm)
    assert mm[0] < mm[-1]


def test_fallback_nacional():
    r = resolve_idf_precipitacao("9999999", 25, duracao_min=60, uf="XX")
    assert r["escopo"] == "brasil"
    assert r["precipitacao_mm"] > 0


def test_uf_fallback_pe():
    r = resolve_idf_precipitacao("2600000", 10, duracao_min=60, uf="PE")
    assert r["escopo"] == "uf"
    assert r["fonte"].endswith("PE")


def test_catalog_has_trs():
    cat = idf_curve_catalog("2611606", uf="PE")
    assert cat["default_duracao_min"] == 60
    labels = {c["label"] for c in cat["curvas"]}
    assert "TR100 · 60 min" in labels
    assert len(cat["curvas"]) == 8  # 4 TR × 2 durações
