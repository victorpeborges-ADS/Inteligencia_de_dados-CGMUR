from unittest.mock import MagicMock, patch

import pytest

from app.services.onboarding_engine import (
    ONBOARDING_TO_CARGA,
    _completeness_from_steps,
    _maturity_from_scores,
    _step,
    _tier_from_score,
    list_onboarding_statuses,
    validate_ibge_code,
)


def test_validate_ibge_rejects_invalid():
    with pytest.raises(ValueError):
        validate_ibge_code("abc")


@patch("app.services.onboarding_engine.requests.get")
def test_validate_ibge_ok(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "id": 2611606,
        "nome": "Recife",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "PE", "regiao": {"nome": "Nordeste"}}}},
    }
    result = validate_ibge_code("2611606")
    assert result["nome"] == "Recife"
    assert result["uf"] == "PE"
    assert result["valido"] is True


def test_completeness_from_steps():
    steps = {
        "geometria": _step("ok"),
        "ibge_indicadores": _step("parcial"),
        "capag": _step("falha"),
    }
    score = _completeness_from_steps(steps)
    assert score == 20 + 15 * 0.5  # geometria ok + ibge parcial


def test_tier_and_maturity_helpers():
    assert _tier_from_score(None) is None
    assert _tier_from_score(85) == "Platina"
    assert _maturity_from_scores(100, 80) >= 80
    assert ONBOARDING_TO_CARGA["concluido"] == "carregado"


@patch("app.services.onboarding_engine.onboarding_status_dict", return_value={"status": "concluido"})
@patch("app.services.onboarding_engine.ensure_seed_row")
@patch("app.services.onboarding_engine.validate_ibge_code")
def test_run_onboarding_skips_when_concluido(mock_validate, mock_seed, mock_status):
    from app.services.onboarding_engine import run_onboarding

    mock_validate.return_value = {"codigo_ibge": "2611606", "nome": "Recife", "uf": "PE"}
    seed = MagicMock(onboarding_status="concluido", codigo_ibge="2611606")
    mock_seed.return_value = seed
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = MagicMock()
    out = run_onboarding(db, "2611606", force=False)
    assert out["status"] == "concluido"
    mock_status.assert_called_once()


@patch("app.services.onboarding_engine.run_onboarding")
@patch("app.services.onboarding_engine.upsert_seed_rows")
def test_run_batch_onboarding(mock_upsert, mock_run):
    from app.services.onboarding_engine import run_batch_onboarding

    seed = MagicMock(codigo_ibge="2611606", prioridade=1, nome="Recife")
    db = MagicMock()
    db.query.return_value.order_by.return_value.filter.return_value.limit.return_value.all.return_value = [seed]
    mock_run.return_value = {"codigo_ibge": "2611606", "status": "parcial"}
    out = run_batch_onboarding(db, limit=5, status_filter="pendente")
    assert out["processed"] == 1
    assert out["requested"] == 1
    mock_run.assert_called_once()


@patch("app.services.onboarding_engine.upsert_seed_rows")
def test_list_onboarding_statuses_empty(mock_upsert):
    db = MagicMock()
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    assert list_onboarding_statuses(db, limit=10) == []
    mock_upsert.assert_called_once_with(db)


@patch("app.services.onboarding_engine.generate_executive_diagnostic", create=True)
@patch("app.services.onboarding_engine.persist_maturity")
@patch("app.services.onboarding_engine.compute_initial_score", return_value=72.0)
@patch("app.services.onboarding_engine.ensure_s2id_mapbiomas_layers", create=True)
@patch("app.services.onboarding_engine.collect_capag_municipality", create=True)
@patch("app.services.onboarding_engine.IntegrationOrchestrator")
@patch("app.services.onboarding_engine.load_municipio_from_seed")
@patch("app.services.onboarding_engine.fetch_ibge_geometry", return_value=({}, "oficial"))
@patch("app.services.onboarding_engine.ensure_seed_row")
@patch("app.services.onboarding_engine.validate_ibge_code")
def test_run_onboarding_happy_path(
    mock_validate,
    mock_seed_row,
    mock_geom,
    mock_load,
    mock_orch_cls,
    mock_capag,
    mock_etl,
    mock_score,
    mock_maturity,
    mock_diag,
):
    from app.services import onboarding_engine as ob

    mock_validate.return_value = {
        "codigo_ibge": "2611606",
        "nome": "Recife",
        "uf": "PE",
        "valido": True,
    }
    seed = MagicMock()
    seed.onboarding_status = "pendente"
    seed.uf = "PE"
    seed.criterio = "piloto"
    seed.lacunas = []
    seed.codigo_ibge = "2611606"
    mock_seed_row.return_value = seed

    muni = MagicMock(id=9, codigo_ibge="2611606")
    mock_load.return_value = muni

    orch = MagicMock()
    orch._sync_ibge.return_value = True
    orch._sync_siconfi.return_value = True
    mock_orch_cls.return_value = orch

    with patch(
        "app.data_connectors.capag_collector.collect_capag_municipality",
        return_value={"nota_capag": "B"},
    ), patch(
        "app.services.territorial_etl.ensure_s2id_mapbiomas_layers",
        return_value={
            "s2id_count": 3,
            "created_s2id": 0,
            "mapbiomas_count": 5,
            "created_mapbiomas": 0,
            "mapbiomas_quality": "oficial",
            "mapbiomas_records": 2,
        },
    ), patch(
        "app.services.executive_diagnostic_engine.generate_executive_diagnostic",
        return_value=None,
    ):
        mock_maturity.return_value = {"score": 70.0, "completeness_score": 90.0}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = muni
        result = ob.run_onboarding(db, "2611606", force=True)

    assert seed.onboarding_status in {"concluido", "parcial"}
    assert result is not None
    orch._sync_ibge.assert_called()
    orch._sync_siconfi.assert_called()
