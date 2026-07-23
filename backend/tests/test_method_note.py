"""17g.2g — Nota metodológica publicável."""

from app.services.method_note_service import build_method_note, render_method_note_markdown


def test_build_method_note_includes_seal_and_markdown():
    meta = {
        "method": "dem_pluvial_d8_twi",
        "model_version": "2.5",
        "dem_available": True,
        "dem_source": "SRTM",
        "dem_resolution_m": 30,
        "vertical_accuracy_m": 16,
        "precipitation_mm": 120,
        "precision_note": "DEM SRTM (~30 m).",
        "selo_confianca": {
            "selo_qualidade": "Estimado",
            "nivel_confianca": "media",
            "interpretacao": "Adequado a priorização.",
            "fatores": ["DEM: SRTM"],
        },
    }
    nota = build_method_note(
        meta,
        tipo="chuva",
        municipio={"codigo_ibge": "2611606", "nome": "Recife", "uf": "PE"},
    )
    assert "Nota metodológica" in nota["titulo"]
    assert nota["municipio"] and "Recife" in nota["municipio"]
    ids = {s["id"] for s in nota["secoes"]}
    assert "metodo" in ids
    assert "confianca" in ids
    assert "limitacoes" in ids
    assert "markdown" in nota
    assert "# " in nota["markdown"]
    md = render_method_note_markdown(nota)
    assert "Referências" in md
