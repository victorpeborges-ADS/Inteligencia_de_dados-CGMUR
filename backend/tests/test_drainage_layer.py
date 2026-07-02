"""Testes de score de drenagem e prioridade."""

from app.api.indicators import _drainage_class, _drainage_risk_score, _percentile, _relative_tertile_class


def test_drainage_class_thresholds():
    assert _drainage_class(0.70) == "CRITICA"
    assert _drainage_class(0.50) == "ATENCAO"
    assert _drainage_class(0.20) == "MONITORAMENTO"


def test_drainage_risk_uses_territorial_components():
    flood = {
        "indice_risco_inundacao": 0.8,
        "impermeabilizacao_score": 0.9,
        "hidrografia_proximidade_score": 1.0,
    }
    score, explanation = _drainage_risk_score(flood, snis_deficit=0.2, has_snis=True)
    assert score >= 0.66
    assert "SNIS" in explanation


def test_relative_tertile_splits_three_classes():
    vals = [0.39, 0.42, 0.45, 0.48, 0.51, 0.54, 0.57, 0.60]
    ordered = sorted(vals)
    p33 = _percentile(ordered, 0.33)
    p66 = _percentile(ordered, 0.66)
    classes = {_relative_tertile_class(v, p33, p66) for v in vals}
    assert classes == {"ALTA", "MEDIA", "BAIXA"}


def test_security_intensity_spreads_by_income_stress():
    """Renda menor deve elevar intensidade relativa no mesmo baseline municipal."""
    baseline = min(1.0, 120.0 / 450.0)
    rich = min(1.0, baseline * 0.22 + max(0.0, 1.0 - 4000 / 4500) * 0.32 + 0.3 * 0.26)
    poor = min(1.0, baseline * 0.22 + max(0.0, 1.0 - 1200 / 4500) * 0.32 + 0.5 * 0.26)
    assert poor > rich
