"""Testes de hotspots recorrentes (17h.2d)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.recurring_hotspots_service import compute_recurring_hotspots


def test_compute_recurring_hotspots_filters():
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"

    b_hot = MagicMock()
    b_hot.id = 10
    b_hot.nome = "Afogados"
    b_hot.geom = object()

    b_cold = MagicMock()
    b_cold.id = 11
    b_cold.nome = "Calmo"
    b_cold.geom = object()

    db = MagicMock()
    muni_q = MagicMock()
    muni_q.filter.return_value.first.return_value = muni
    bairro_q = MagicMock()
    bairro_q.filter.return_value.all.return_value = [b_hot, b_cold]

    def query_side_effect(model, *args, **kwargs):
        name = getattr(model, "__name__", str(model))
        if "Municipio" in name:
            return muni_q
        return bairro_q

    db.query.side_effect = query_side_effect

    floods = [
        {"id": 10, "indice_risco_inundacao": 0.7, "s2id_historico_score": 0.9},
        {"id": 11, "indice_risco_inundacao": 0.2, "s2id_historico_score": 0.1},
    ]

    with (
        patch(
            "app.services.recurring_hotspots_service.AnalyticalEngine.calculate_flood_risk",
            return_value=floods,
        ),
        patch(
            "app.services.recurring_hotspots_service._count_flood_events_in_bairro",
            side_effect=lambda *_a, **_k: 3 if _a[2] is b_hot else 0,
        ),
        patch(
            "app.services.recurring_hotspots_service._affected_bairros_from_cache",
            return_value={"Afogados"},
        ),
    ):
        out = compute_recurring_hotspots(db, "2611606", limit=5)

    assert out["total"] == 1
    assert out["hotspots"][0]["bairro"] == "Afogados"
    assert out["hotspots"][0]["eventos_s2id"] == 3
    assert out["hotspots"][0]["na_mancha_sim_120mm"] is True
