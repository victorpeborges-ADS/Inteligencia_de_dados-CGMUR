"""Testes — chart_generator Step 8."""

import matplotlib

matplotlib.use("Agg")

from app.reports.chart_generator import MESES_PT, _capag_score, _empty_chart


def test_capag_score_mapping():
    assert _capag_score("A") == 95
    assert _capag_score("D") == 25
    assert _capag_score(None) == 40


def test_empty_chart_returns_base64():
    b64 = _empty_chart("Teste")
    assert isinstance(b64, str)
    assert len(b64) > 50


def test_meses_pt_has_twelve():
    assert len(MESES_PT) == 12
