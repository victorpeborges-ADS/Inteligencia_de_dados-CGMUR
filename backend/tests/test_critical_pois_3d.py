"""Testes POIs críticos 3D (17f.3)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.models import (
    ContingencyPlan,
    EscolaInep,
    EstabelecimentoSaude,
    InfraestruturaUrbana,
    Municipio,
)
from app.services import critical_pois_3d_service as mod
from app.services.critical_pois_3d_service import build_critical_pois_geojson


def test_build_critical_pois_empty_muni():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    out = build_critical_pois_geojson(db, "2611606")
    assert out["features"] == []
    assert out["meta"]["erro"] == "municipio_nao_encontrado"


def test_build_critical_pois_with_escola_and_saude():
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    muni.nome = "Recife"
    muni.uf = "PE"

    escola = MagicMock()
    escola.nome = "Escola Teste"
    escola.codigo_inep = "123"
    escola.dependencia = "Municipal"
    escola.matriculas_total = 400
    escola.geom = object()

    saude = MagicMock()
    saude.nome = "UBS Centro"
    saude.tipo = "UBS"
    saude.cnes_codigo = "999"
    saude.leitos_sus = 0
    saude.esf = True
    saude.geom = object()

    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model is Municipio:
            q.filter.return_value.first.return_value = muni
        elif model is EscolaInep:
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [escola]
        elif model is EstabelecimentoSaude:
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [saude]
        elif model is ContingencyPlan:
            q.filter.return_value.order_by.return_value.first.return_value = None
        elif model is InfraestruturaUrbana:
            q.filter.return_value.limit.return_value.all.return_value = []
        return q

    db.query.side_effect = query_side_effect

    original = mod._point_xy
    mod._point_xy = lambda _geom: (-34.88, -8.05)
    try:
        out = build_critical_pois_geojson(
            db,
            "2611606",
            include_abrigos=True,
            include_equipamentos=False,
        )
    finally:
        mod._point_xy = original

    cats = {f["properties"]["categoria"] for f in out["features"]}
    assert "escola" in cats
    assert "saude" in cats
    assert out["meta"]["count"] == 2
    assert out["features"][0]["properties"]["label"]
