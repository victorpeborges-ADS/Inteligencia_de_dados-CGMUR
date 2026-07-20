"""Testes do panorama nacional de lacunas institucionais."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.institutional_gaps_service import (
    INSTITUTIONAL_GAP_IDS,
    build_institutional_gaps_summary,
)


def _mock_db_chain(*, muni=None, seed=None, bairro_count=0):
    db = MagicMock()

    def query_side_effect(model):
        chain = MagicMock()
        chain.filter.return_value.first.return_value = muni if getattr(model, "__name__", "") == "Municipio" else seed
        chain.filter.return_value.count.return_value = bairro_count
        return chain

    db.query.side_effect = query_side_effect
    return db


def test_build_summary_returns_six_gaps(monkeypatch):
    db = _mock_db_chain()

    def fake_resolve(_db, _code, fonte_id, **kwargs):
        if fonte_id == "geosgb":
            return "Em integracao"
        if fonte_id == "adapta_brasil":
            return "Estimado"
        return "Ausente"

    monkeypatch.setattr(
        "app.services.institutional_gaps_service.resolve_catalog_status",
        fake_resolve,
    )

    summary = build_institutional_gaps_summary(db, ["2611606", "2927408"])
    assert summary["total_municipios"] == 2
    assert len(summary["gaps"]) == len(INSTITUTIONAL_GAP_IDS) + 1

    geosgb = next(row for row in summary["gaps"] if row["fonte_id"] == "geosgb")
    assert geosgb["lacuna_municipios"] == 2
    assert geosgb["integrado_count"] == 0
    assert geosgb["progress_label"] == "0/2 Integrado"

    adapta = next(row for row in summary["gaps"] if row["fonte_id"] == "adapta_brasil")
    assert adapta["proxy_ativo"] is True

    ctm = next(row for row in summary["gaps"] if row["fonte_id"] == "ctm_utb")
    assert ctm["rank"] == 6
    assert ctm["etl_ready"] is True


def test_ctm_gap_counts_official_mesh(monkeypatch):
    muni = MagicMock()
    muni.id = 1
    seed = MagicMock()
    seed.malha_fonte = "prefeitura_oficial"
    db = _mock_db_chain(muni=muni, seed=seed, bairro_count=42)

    monkeypatch.setattr(
        "app.services.institutional_gaps_service.resolve_catalog_status",
        lambda *_a, **_k: "Ausente",
    )

    summary = build_institutional_gaps_summary(db, ["5208707"])
    ctm = next(row for row in summary["gaps"] if row["fonte_id"] == "ctm_utb")
    assert ctm["importado_prefeitura_count"] == 1
    assert ctm["integrado_count"] == 1
    assert ctm.get("ctm_sem_fonte_count", 0) >= 0


def test_build_ctm_operational_summary(monkeypatch):
    muni = MagicMock()
    muni.id = 1
    seed = MagicMock()
    seed.malha_fonte = "prefeitura_oficial"
    db = _mock_db_chain(muni=muni, seed=seed, bairro_count=42)
    monkeypatch.setattr(
        "app.services.institutional_gaps_service.resolve_catalog_status",
        lambda *_a, **_k: "Ausente",
    )
    from app.services.institutional_gaps_service import build_ctm_operational_summary

    ops = build_ctm_operational_summary(db)
    assert ops["total_alvo"] == 24
    assert ops["fontes_cadastradas"] >= 1
    assert ops["importado_prefeitura"] >= 1
    assert "progress_label" in ops
