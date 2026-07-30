"""Testes IDF / período de retorno (17g.1a / 20h.4)."""

import json

from app.services.idf_rainfall_service import (
    idf_curve_catalog,
    reload_idf_overrides,
    resolve_idf_precipitacao,
)


def test_resolve_recife_tr100_60min_official_override():
    """2611606.json (20h.4) sobrepõe a tabela interna Estimado para Recife."""
    reload_idf_overrides()
    r = resolve_idf_precipitacao("2611606", 100, duracao_min=60)
    assert r["periodo_retorno_anos"] == 100
    assert r["duracao_min"] == 60
    assert r["precipitacao_mm"] == 150.0
    assert r["intensidade_mm_h"] == 150.0
    assert r["escopo"] == "municipio"
    assert r["qualidade"] == "Oficial"
    assert r["fonte"] == "APAC/plano_diretor_drenagem_recife"
    assert r["referencia"] == "Curva IDF municipal curada (piloto 20h.4)"


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
    assert len(cat["curvas"]) == 12  # 4 TR × 3 durações (60/120/1440 min)


def test_catalog_reports_official_quality_for_recife():
    reload_idf_overrides()
    cat = idf_curve_catalog("2611606", uf="PE")
    assert cat["qualidade"] == "Oficial"
    assert cat["fonte"] == "APAC/plano_diretor_drenagem_recife"


def test_official_override_precedes_embedded_table(tmp_path, monkeypatch):
    """Um override oficial para Aracaju (não versionado) deve vencer a tabela interna."""
    override_dir = tmp_path / "idf_overrides"
    override_dir.mkdir()
    payload = {
        "fonte": "teste_oficial_aracaju",
        "qualidade": "Oficial",
        "referencia": "Curva de teste 20h.4",
        "curvas": {"60": {"100": 999.0}},
    }
    (override_dir / "2800308.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setenv("IDF_DIR", str(override_dir))
    reload_idf_overrides()
    try:
        r = resolve_idf_precipitacao("2800308", 100, duracao_min=60)
        assert r["qualidade"] == "Oficial"
        assert r["precipitacao_mm"] == 999.0
        assert r["fonte"] == "teste_oficial_aracaju"
        assert r["referencia"] == "Curva de teste 20h.4"
    finally:
        monkeypatch.delenv("IDF_DIR", raising=False)
        reload_idf_overrides()


def test_no_override_dir_falls_back_to_estimado(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty_idf"
    empty_dir.mkdir()
    monkeypatch.setenv("IDF_DIR", str(empty_dir))
    reload_idf_overrides()
    try:
        r = resolve_idf_precipitacao("2611606", 100, duracao_min=60)
        assert r["qualidade"] == "Estimado"
        assert r["precipitacao_mm"] == 145.0
        assert "piloto" in r["fonte"]
    finally:
        monkeypatch.delenv("IDF_DIR", raising=False)
        reload_idf_overrides()
