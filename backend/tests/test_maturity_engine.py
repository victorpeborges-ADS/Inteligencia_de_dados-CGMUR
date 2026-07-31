from unittest.mock import MagicMock, patch

from app.services.maturity_engine import (
    STATUS_WEIGHT,
    _default_recommendation,
    _eval_bairros,
    _eval_capag,
    _eval_clima,
    _eval_ibge,
    _eval_mapbiomas,
    _eval_plano_diretor,
    _eval_s2id,
    _eval_siconfi,
    _eval_snis,
    _source_result,
    classify_tier,
    compute_maturity,
    persist_maturity,
)


def test_classify_tier():
    assert classify_tier(0) == "Bronze"
    assert classify_tier(25) == "Bronze"
    assert classify_tier(26) == "Prata"
    assert classify_tier(50) == "Prata"
    assert classify_tier(51) == "Ouro"
    assert classify_tier(75) == "Ouro"
    assert classify_tier(76) == "Platina"
    assert classify_tier(100) == "Platina"


def test_status_weights():
    assert STATUS_WEIGHT["OFICIAL"] == 1.0
    assert STATUS_WEIGHT["LACUNA"] == 0.0


def test_source_result_and_recommendations():
    row = _source_result("ibge", "IBGE", "Demo", "OFICIAL", detail="ok")
    assert row["pontos"] > 0
    assert "Manter" in _default_recommendation("OFICIAL", "IBGE")
    assert "Substituir" in _default_recommendation("ESTIMADO", "X")
    assert "Integrar" in _default_recommendation("LACUNA", "Y")


def test_eval_ibge_siconfi_capag_paths():
    db = MagicMock()
    # IBGE oficial
    ibge = MagicMock(populacao=1000, area_km2=10.0)
    db.query.return_value.filter.return_value.first.return_value = ibge
    assert _eval_ibge(db, "2611606")["status"] == "OFICIAL"

    # SICONFI parcial
    fiscal = MagicMock(receita_corrente_liquida=None, nota_capag=None, exercicio=2024)
    db.query.return_value.filter.return_value.first.return_value = fiscal
    assert _eval_siconfi(db, "2611606")["status"] == "ESTIMADO"
    assert _eval_capag(db, "2611606")["status"] == "LACUNA"

    fiscal.nota_capag = "A"
    fiscal.receita_corrente_liquida = 1.0
    assert _eval_capag(db, "2611606")["status"] == "OFICIAL"
    assert _eval_siconfi(db, "2611606")["status"] == "OFICIAL"


def test_eval_s2id_lacuna_sem_muni():
    assert _eval_s2id(MagicMock(), None, None)["status"] == "LACUNA"


def test_eval_s2id_estimado_e_oficial():
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 3
    muni = MagicMock(id=1)
    seed = MagicMock(lacunas=["s2id_oficial"], integration_steps={})
    assert _eval_s2id(db, muni, seed)["status"] == "ESTIMADO"
    seed2 = MagicMock(lacunas=[], integration_steps={})
    assert _eval_s2id(db, muni, seed2)["status"] == "OFICIAL"


def test_eval_mapbiomas_paths():
    assert _eval_mapbiomas(MagicMock(), None)["status"] == "LACUNA"
    db = MagicMock()
    muni = MagicMock(id=1, codigo_ibge="2611606")
    # chain: stats count, official count, cobertura count
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value.count.side_effect = [8, 8, 0]
    assert _eval_mapbiomas(db, muni)["status"] == "OFICIAL"

    q.filter.return_value.count.side_effect = [8, 0, 0]
    assert _eval_mapbiomas(db, muni)["status"] == "DERIVADO"

    q.filter.return_value.count.side_effect = [0, 0, 2]
    assert _eval_mapbiomas(db, muni)["status"] == "DERIVADO"

    q.filter.return_value.count.side_effect = [0, 0, 1]
    assert _eval_mapbiomas(db, muni)["status"] == "ESTIMADO"

    q.filter.return_value.count.side_effect = [0, 0, 0]
    assert _eval_mapbiomas(db, muni)["status"] == "LACUNA"


def test_eval_bairros_and_snis_and_plano():
    assert _eval_bairros(MagicMock(), None, None)["status"] == "LACUNA"
    db = MagicMock()
    muni = MagicMock(id=1)
    db.query.return_value.filter.return_value.all.return_value = [
        MagicMock(nome="Centro"),
        MagicMock(nome="Boa Viagem"),
        MagicMock(nome="Casa Amarela"),
        MagicMock(nome="Recife"),
    ]
    assert _eval_bairros(db, muni, None)["status"] == "DERIVADO"

    db_empty = MagicMock()
    db_empty.query.return_value.filter.return_value.first.return_value = None
    assert _eval_snis(db_empty, "2611606")["status"] == "LACUNA"
    db2 = MagicMock()
    row = MagicMock(data_quality="oficial", cobertura_agua_pct=90, cobertura_esgoto_pct=70)
    db2.query.return_value.filter.return_value.first.return_value = row
    assert _eval_snis(db2, "2611606")["status"] == "OFICIAL"
    row.data_quality = "estimado"
    assert _eval_snis(db2, "2611606")["status"] == "ESTIMADO"

    assert _eval_plano_diretor("2611606")["status"] in {"OFICIAL", "LACUNA"}
    assert _eval_plano_diretor("0000000")["status"] == "LACUNA"


def test_eval_clima_paths():
    db = MagicMock()
    weather = MagicMock(precip_24h_mm=40)
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = weather
    assert _eval_clima(db, "2611606", MagicMock(id=1))["status"] == "DERIVADO"

    db2 = MagicMock()
    db2.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db2.query.return_value.filter.return_value.count.return_value = 2
    assert _eval_clima(db2, "2611606", MagicMock(id=1))["status"] == "ESTIMADO"

    db3 = MagicMock()
    db3.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    assert _eval_clima(db3, "2611606", None)["status"] == "LACUNA"


@patch("app.services.maturity_engine._eval_clima", return_value=_source_result("dados_climaticos", "Clima", "Clima", "LACUNA"))
@patch("app.services.maturity_engine._eval_plano_diretor", return_value=_source_result("plano_diretor", "PD", "P", "LACUNA"))
@patch("app.services.maturity_engine._eval_bairros", return_value=_source_result("bairros", "B", "T", "LACUNA"))
@patch("app.services.maturity_engine._eval_snis", return_value=_source_result("snis", "S", "S", "LACUNA"))
@patch("app.services.maturity_engine._eval_mapbiomas", return_value=_source_result("mapbiomas", "M", "U", "LACUNA"))
@patch("app.services.maturity_engine._eval_s2id", return_value=_source_result("s2id", "S2", "D", "LACUNA"))
@patch("app.services.maturity_engine._eval_capag", return_value=_source_result("capag", "C", "F", "LACUNA"))
@patch("app.services.maturity_engine._eval_siconfi", return_value=_source_result("siconfi", "SI", "F", "LACUNA"))
@patch("app.services.maturity_engine._eval_ibge", return_value=_source_result("ibge", "IBGE", "D", "OFICIAL"))
def test_compute_maturity(*_mocks):
    db = MagicMock()
    muni = MagicMock(codigo_ibge="2611606", nome="Recife", uf="PE")
    seed = MagicMock(codigo_ibge="2611606", lacunas=[], nome="Recife", uf="PE")
    db.query.return_value.filter.return_value.first.side_effect = [muni, seed]
    result = compute_maturity(db, "2611606")
    assert result["codigo_ibge"] == "2611606"
    assert result["classificacao"] in {"Bronze", "Prata", "Ouro", "Platina"}
    assert len(result["fontes"]) == 9


@patch(
    "app.services.maturity_engine.compute_maturity",
    return_value={
        "codigo_ibge": "2611606",
        "score": 40.0,
        "completeness_score": 20.0,
        "fontes_faltantes": [{"id": "s2id", "nome": "S2ID", "recomendacao": "x"}],
    },
)
def test_persist_maturity(mock_compute):
    db = MagicMock()
    seed = MagicMock(lacunas=[])
    db.query.return_value.filter.return_value.first.return_value = seed
    out = persist_maturity(db, "2611606")
    assert out["score"] == 40.0
    assert "fonte_s2id" in seed.lacunas
    db.commit.assert_called_once()
    mock_compute.assert_called_once()
