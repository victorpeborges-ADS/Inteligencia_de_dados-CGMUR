from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.report_generator import MunicipalReportGenerator, _format_currency, build_bairro_ranking


def test_format_currency():
    assert _format_currency(1500000) == "R$ 1.500.000"
    assert _format_currency(None) == "—"


@patch("weasyprint.HTML")
@patch("app.services.report_generator.render_municipality_map", return_value="aGVsbG8=")
@patch("app.services.report_generator.fetch_precipitation_series", return_value=[])
@patch("app.services.report_generator.MitigationPlanner.build_rainfall_plan")
def test_generate_report_persists_record(mock_plan, _precip, _map, mock_html, tmp_path):
    mock_plan.return_value = {
        "severidade": "Alta",
        "acoes_tecnicas_padrao": [],
        "capacidade_investimento": {"fontes_financiamento_sugeridas": ["FCP"]},
    }
    mock_html.return_value.write_pdf = MagicMock()

    db = MagicMock()
    muni = MagicMock()
    muni.id = 1
    muni.codigo_ibge = "2611606"
    muni.nome = "Recife"
    muni.uf = "PE"
    muni.populacao = 1000
    muni.area_km2 = 100
    muni.geom = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = muni
    db.scalar.return_value = '{"type":"Point","coordinates":[-34.9,-8.05]}'

    with patch("app.services.report_generator.settings") as settings_mock:
        settings_mock.REPORTS_DIR = str(tmp_path)
        with patch.object(MunicipalReportGenerator, "_build_context", return_value={"footer_date": "24/06/2026"}):
            with patch.object(MunicipalReportGenerator, "_render_html", return_value="<html></html>"):
                generator = MunicipalReportGenerator(db)
                record = generator.generate(1)

    assert record.status == "concluido"
    assert record.codigo_ibge == "2611606"
    db.commit.assert_called()
