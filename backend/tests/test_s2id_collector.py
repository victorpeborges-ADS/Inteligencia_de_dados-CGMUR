"""Testes do coletor S2ID."""

from unittest.mock import MagicMock, patch

from app.data_connectors.s2id_collector import (
    RECIFE_S2ID_EVENTS,
    _SYNTHETIC_PLACEHOLDER_DANOS,
    _events_for_municipality,
    collect_s2id_municipality,
    ensure_s2id_loaded,
    needs_s2id_refresh,
    s2id_quality_label,
)


def test_recife_pilot_has_multiple_events():
    assert len(RECIFE_S2ID_EVENTS) >= 10
    tipos = {e["tipo"] for e in RECIFE_S2ID_EVENTS}
    assert "Inundação" in tipos
    assert "Deslizamento de Terra" in tipos
    assert all(e.get("descricao") for e in RECIFE_S2ID_EVENTS)
    assert all(e.get("link_noticia") for e in RECIFE_S2ID_EVENTS)


def test_recife_pilot_damage_total_realistic():
    total = sum(float(e["danos"]) for e in RECIFE_S2ID_EVENTS)
    assert total >= 200_000_000


def test_enrich_s2id_feature_props_recife():
    from app.data_connectors.s2id_collector import (
        build_s2id_enrichment_index,
        enrich_s2id_feature_props,
    )
    import datetime

    idx = build_s2id_enrichment_index("2611606")
    props = enrich_s2id_feature_props(
        tipo_desastre="Deslizamento de Terra",
        data_ocorrencia=datetime.date(2022, 5, 28),
        populacao_afetada=12000,
        danos_materiais=45_000_000,
        referencia="Morros do Ibura",
        data_quality="oficial_curado",
        fonte="s2id_curado",
        enrichment=idx,
        eventos_municipio=11,
    )
    assert props["mortos"] == 51
    assert props["descricao"]
    assert props["medidas"]
    assert "g1.globo.com" in (props["link_noticia"] or "")
    assert props["detalhe_completo"] is True


def test_events_for_recife_uses_curated():
    muni = MagicMock(codigo_ibge="2611606", id=1)
    events = _events_for_municipality(MagicMock(), muni, risk="inundacao")
    assert len(events) == len(RECIFE_S2ID_EVENTS)


def test_needs_s2id_refresh_when_empty():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    assert needs_s2id_refresh(db, MagicMock(id=1, codigo_ibge="9999999")) is True


def test_s2id_quality_label_returns_string():
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 2
    label = s2id_quality_label(db, MagicMock(id=1, codigo_ibge="9999999"))
    assert label in {"oficial", "estimado", "derivado"}


def test_needs_s2id_refresh_placeholder():
    db = MagicMock()
    row = MagicMock(danos_materiais=_SYNTHETIC_PLACEHOLDER_DANOS)
    db.query.return_value.filter.return_value.all.return_value = [row]
    assert needs_s2id_refresh(db, MagicMock(id=1, codigo_ibge="9999999")) is True


def test_needs_s2id_refresh_pilot_incomplete():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [MagicMock(danos_materiais=1.0)]
    assert needs_s2id_refresh(db, MagicMock(id=1, codigo_ibge="2611606")) is True


def test_s2id_quality_oficial_for_recife_pilot():
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = len(RECIFE_S2ID_EVENTS)
    assert s2id_quality_label(db, MagicMock(id=1, codigo_ibge="2611606")) == "oficial"


def test_collect_s2id_municipio_nao_encontrado():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    out = collect_s2id_municipality(db, "0000000")
    assert out["skipped"] is True
    assert out["reason"] == "municipio_nao_encontrado"


@patch("app.data_connectors.s2id_collector.needs_s2id_refresh", return_value=False)
def test_collect_s2id_skips_when_fresh(mock_needs):
    db = MagicMock()
    muni = MagicMock(id=1, codigo_ibge="2611606")
    db.query.return_value.filter.return_value.first.return_value = muni
    db.query.return_value.filter.return_value.count.return_value = 8
    out = collect_s2id_municipality(db, "2611606", force=False)
    assert out["skipped"] is True
    assert out["records"] == 8


@patch("app.data_connectors.s2id_collector.collect_s2id_municipality", return_value={"ok": True})
@patch("app.data_connectors.s2id_collector.needs_s2id_refresh", return_value=True)
def test_ensure_s2id_loaded_triggers_collect(mock_needs, mock_collect):
    out = ensure_s2id_loaded(MagicMock(), MagicMock(codigo_ibge="2611606"))
    assert out == {"ok": True}
    mock_collect.assert_called_once()


@patch("app.data_connectors.s2id_collector.needs_s2id_refresh", return_value=False)
def test_ensure_s2id_loaded_noop(mock_needs):
    assert ensure_s2id_loaded(MagicMock(), MagicMock()) is None
