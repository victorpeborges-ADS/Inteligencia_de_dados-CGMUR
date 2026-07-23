"""Testes dos fatores explicados do ranking (17h.2a)."""

from app.services.report_generator import _build_fatores_explicados


def test_build_fatores_principais_ordenados_por_contribuicao():
    item = {
        "indice_vulnerabilidade": 0.7,
        "renda_media": 1200,
        "densidade_hab_km2": 9000,
        "income_score": 0.83,
        "density_score": 0.6,
        "s2id_desastres_count": 4,
        "exposicao": 0.7,
        "capacidade_adaptacao": 0.2,
    }
    flood = {
        "indice_risco_inundacao": 0.65,
        "s2id_historico_score": 0.9,
        "impermeabilizacao_score": 0.8,
        "hidrografia_proximidade_score": 0.5,
    }
    fatores, principais = _build_fatores_explicados(item, flood, adaptation_gap=0.8)
    assert len(fatores) >= 5
    assert principais
    # Principais devem ser os de maior contribuição
    contrib = {f["id"]: f["contribuicao"] for f in fatores}
    assert contrib[principais[0]] >= contrib[principais[-1]]
    ids = {f["id"] for f in fatores}
    assert "renda" in ids
    assert "impermeabilizacao" in ids
    assert "s2id" in ids
