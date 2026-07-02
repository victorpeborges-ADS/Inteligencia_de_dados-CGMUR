"""Testes do coletor S2ID."""

from app.data_connectors.s2id_collector import RECIFE_S2ID_EVENTS, _events_for_municipality


def test_recife_pilot_has_multiple_events():
    assert len(RECIFE_S2ID_EVENTS) >= 6
    tipos = {e["tipo"] for e in RECIFE_S2ID_EVENTS}
    assert "Inundação" in tipos
    assert "Deslizamento de Terra" in tipos


def test_recife_pilot_damage_total_realistic():
    total = sum(float(e["danos"]) for e in RECIFE_S2ID_EVENTS)
    assert total >= 150_000_000


def test_recife_events_have_coordinates():
    for event in RECIFE_S2ID_EVENTS:
        assert -35 < event["lng"] < -34
        assert -8.2 < event["lat"] < -7.9
