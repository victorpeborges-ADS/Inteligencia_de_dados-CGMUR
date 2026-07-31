"""Testes Fase 21g.2 — previsão de impacto."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.flood_impact_service import build_flood_impact


def test_build_flood_impact_population_and_measures():
    muni = MagicMock()
    muni.id = 1
    muni.populacao = 100_000
    muni.codigo_ibge = "2611606"

    b1 = MagicMock()
    b1.id = 10
    b1.nome = "Centro"
    b1.pop_censo2022 = 20_000

    b2 = MagicMock()
    b2.id = 11
    b2.nome = "Afogados"
    b2.pop_censo2022 = 15_000

    db = MagicMock()

    def query_side_effect(model):
        name = getattr(model, "__name__", str(model))
        q = MagicMock()
        if "Municipio" in name:
            q.filter.return_value.first.return_value = muni
        else:
            q.filter.return_value.all.return_value = [b1, b2]
        return q

    db.query.side_effect = query_side_effect

    neighborhoods = [
        {"bairro_id": 10, "bairro_nome": "Centro", "risk_probability": 0.8},
        {"bairro_id": 11, "bairro_nome": "Afogados", "risk_probability": 0.5},
    ]

    with patch(
        "app.services.municipal_profile_service.build_municipal_profile",
        return_value={"porte": "grande", "capag": {"nota": "B"}},
    ), patch(
        "app.services.measures_catalog.recommend_measures",
        return_value=[
            {
                "id": "microdrenagem",
                "titulo": "Microdrenagem",
                "custo": "Médio",
                "horizonte": "Curto prazo",
                "prioridade": "Alta",
                "orgao": "Obras",
                "motivo": "teste",
            }
        ],
    ):
        out = build_flood_impact(
            db,
            "2611606",
            municipal_prob=0.7,
            critical_neighborhoods=neighborhoods,
        )

    assert out["disponivel"] is True
    assert out["nivel_operacional"] == "LARANJA"
    assert out["n_bairros_prioritarios"] == 2
    # 20000*0.8 + 15000*0.5 = 16000+7500 = 23500
    assert out["populacao_exposta_estimada"] == 23500
    assert out["capag_nota"] == "B"
    assert len(out["medidas_cabiveis"]) == 1
    assert "impacto" in (out["protocol"] or "")


def test_build_flood_impact_missing_muni():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    out = build_flood_impact(db, "9999999", municipal_prob=0.5, critical_neighborhoods=[])
    assert out["disponivel"] is False
